import boto3
import paramiko
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()


AWS_REGION = os.getenv("AWS_REGION")
KEY_NAME = os.getenv("KEY_NAME")
REP_USER = os.getenv("REP_USER")
REP_PASS = os.getenv("REP_PASS")

ec2 = boto3.resource('ec2', region_name=AWS_REGION)


def get_infra_info():
    instances = ec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])

    manager_ip = None
    worker_ips = []
    proxy_ip = None

    for instance in instances:
        name = ''

        for tag in instance.tags or []:
            if tag['Key'] == 'Name':
                name = tag['Value']

        if 'Manager' in name:
            manager_ip = instance.private_ip_address
        elif 'Worker' in name:
            worker_ips.append(instance.private_ip_address)
        elif 'Proxy' in name:
            proxy_ip = instance.public_ip_address # Needed for SSH access
        
    return manager_ip, worker_ips, proxy_ip


def deploy():
    manager_pvt, workers_pvt, proxy_pub = get_infra_info()

    if not proxy_pub:
        print("Proxy instance not found.")
        return
    
    print(f" Manager (private): {manager_pvt}")
    print(f" Workers (private): {workers_pvt}")
    print(f" Proxy (public): {proxy_pub}")

    print("Configuring proxy/app.py...")
    with open('proxy/app.py', 'r') as file:
        code = file.read()

    
    code = code.replace('MANAGER_IP = ""', f'MANAGER_IP = "{manager_pvt}"')
    code = code.replace('WORKER_IPS = []', f'WORKER_IPS = {workers_pvt}')
    code = code.replace('DB_USER = "replica_user"', f'DB_USER = "{REP_USER}"')
    code = code.replace('DB_PASS = "replica_secure_pass"', f'DB_PASS = "{REP_PASS}"')

    with open('proxy/app.py', 'w') as file:
        file.write(code)

    print("nm Uploading code to proxy instance...")
    key = paramiko.RSAKey.from_private_key_file(f"{KEY_NAME}.pem")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(hostname=proxy_pub, username='ubuntu', pkey=key)
        sftp = ssh.open_sftp()
        sftp.put('proxy/app.py', '/home/ubuntu/proxy/app.py')
        sftp.put('proxy/requirements.txt', '/home/ubuntu/proxy/requirements.txt')
        sftp.close()

        print("Installing dependencies on proxy instance...")
        commands = """
        sudo apt-get install -y python3-pip python3-venv
        python3 -m venv /home/ubuntu/proxy/venv
        /home/ubuntu/proxy/venv/bin/pip install -r /home/ubuntu/proxy/requirements.txt
        # kill existing proxy if any
        pkill -f 'python3 /home/ubuntu/proxy/app.py' || true
        # Start the proxy
        nohup /home/ubuntu/proxy/venv/bin/python3 /home/ubuntu/proxy/app.py > /home/ubuntu/proxy/proxy.log 2>&1 &
        """

        stdin, stdout, stderr = ssh.exec_command(commands)
        stdout.channel.recv_exit_status()  # Wait for command to complete
        time.sleep(5)  # Give some time for the proxy to start
        
    except Exception as e:
        print(f"Error deploying to proxy instance: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    deploy()
