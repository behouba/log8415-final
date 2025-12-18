import boto3
import paramiko
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
KEY_NAME = os.getenv("KEY_NAME")

ec2 = boto3.resource('ec2', region_name=AWS_REGION)

def get_infra_info():
    instances = ec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])

    proxy_pvt = None
    gatekeeper_pub = None

    for instance in instances:
        name = ''
        for tag in instance.tags or []:
            if tag['Key'] == 'Name':
                name = tag['Value']

        if 'Proxy' in name:
            proxy_pvt = instance.private_ip_address
        elif 'Gatekeeper' in name:
            gatekeeper_pub = instance.public_ip_address

    return proxy_pvt, gatekeeper_pub

def deploy():
    proxy_pvt, gatekeeper_pub = get_infra_info()

    if not gatekeeper_pub:
        print("Gatekeeper instance not found.")
        return

    if not proxy_pvt:
        print("Proxy instance not found.")
        return

    print(f" Proxy (private): {proxy_pvt}")
    print(f" Gatekeeper (public): {gatekeeper_pub}")

    print("Configuring gatekeeper/app.py...")
    with open('gatekeeper/app.py', 'r') as file:
        code = file.read()

    code = code.replace('PROXY_HOST = ""', f'PROXY_HOST = "{proxy_pvt}"')

    with open('gatekeeper/app.py', 'w') as file:
        file.write(code)

    print("Uploading code to gatekeeper instance...")
    key = paramiko.RSAKey.from_private_key_file(f"{KEY_NAME}.pem")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(hostname=gatekeeper_pub, username='ubuntu', pkey=key)
        sftp = ssh.open_sftp()
        sftp.put('gatekeeper/app.py', '/home/ubuntu/gatekeeper/app.py')
        sftp.put('gatekeeper/requirements.txt', '/home/ubuntu/gatekeeper/requirements.txt')
        sftp.close()

        print("Installing dependencies on gatekeeper instance...")
        commands = """
        sudo apt-get install -y python3-pip python3-venv
        python3 -m venv /home/ubuntu/gatekeeper/venv
        /home/ubuntu/gatekeeper/venv/bin/pip install -r /home/ubuntu/gatekeeper/requirements.txt
        pkill -f 'python3 /home/ubuntu/gatekeeper/app.py' || true
        nohup /home/ubuntu/gatekeeper/venv/bin/python3 /home/ubuntu/gatekeeper/app.py > /home/ubuntu/gatekeeper/gatekeeper.log 2>&1 &
        """

        stdin, stdout, stderr = ssh.exec_command(commands)
        stdout.channel.recv_exit_status()
        err = stderr.read().decode().strip()
        if err:
            print(f"Error during gatekeeper setup: {err}")
            return
        time.sleep(5)
        print("Gatekeeper deployed and started successfully.")

    except Exception as e:
        print(f"Error deploying to gatekeeper instance: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    deploy()
