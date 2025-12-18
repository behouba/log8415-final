import boto3
import os
import subprocess
import sys
import time
import paramiko
from dotenv import load_dotenv

load_dotenv()

REGION = os.getenv("AWS_REGION")
KEY_NAME = os.getenv("KEY_NAME")
REP_USER = os.getenv("REP_USER")
REP_PASS = os.getenv("REP_PASS")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")

if not all([REGION, KEY_NAME, REP_USER, REP_PASS, DB_USER, DB_PASS, DB_NAME]):
    print("One or more required environment variables are missing.")
    sys.exit(1)

ec2 = boto3.resource('ec2', region_name=REGION)

def get_instances():
    instances = ec2.instances.filter(
        Filters=[{'Name': 'instance-state-name', 'Values': ['running']},
                 {'Name': 'key-name', 'Values': [KEY_NAME]},]
    )

    manager = None
    workers = []

    for instance in instances:
        name = ''
        for tag in instance.tags or []:
            if tag['Key'] == 'Name':
                name = tag['Value']
                
        if 'Manager' in name:
            manager = instance
        elif 'Worker' in name:
            workers.append(instance)

    return manager, workers

def execute_ssh_command(instance, command):
    key_file = f"{KEY_NAME}.pem"

    if not os.path.exists(key_file):
        print(f"Key file '{key_file}' not found.")
        return None
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        k = paramiko.RSAKey.from_private_key_file(key_file)
        ssh.connect(hostname=instance.public_ip_address, username='ubuntu', pkey=k)

        stdin, stdout, stderr = ssh.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()

        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()

        ssh.close()

        if exit_status != 0:
            print(f"Error executing command on {instance.id}: {err}")
            return None
        return out
    except Exception as e:
        print(f"SSH connection error to {instance.id}: {e}")
        return None
    
def configure_node(instance, server_id):
    ip = instance.public_ip_address
    print(f"Configuring node {instance.id} with IP {ip} and server_id {server_id}...")

    bin_log_config = ""
    if server_id == 1:
        bin_log_config = f"""
        sudo sed -i '/log_bin/d' /etc/mysql/mysql.conf.d/mysqld.cnf
        echo 'log_bin = /var/log/mysql/mysql-bin.log' | sudo tee -a /etc/mysql/mysql.conf.d/mysqld.cnf
        """
    command = f"""
    sudo sed -i 's/^bind-address.*/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf
    sudo sed -i '/server-id/d' /etc/mysql/mysql.conf.d/mysqld.cnf
    echo 'server-id = {server_id}' | sudo tee -a /etc/mysql/mysql.conf.d/mysqld.cnf
    {bin_log_config}
    sudo systemctl restart mysql
    """
    execute_ssh_command(instance, command)


def setup_master(manager):
    ip = manager.public_ip_address
    print(f"Setting up master on {manager.id} with IP {ip}...")

    create_user_cmd = f"""
    sudo mysql -e "CREATE USER IF NOT EXISTS '{REP_USER}'@'%' IDENTIFIED WITH mysql_native_password BY '{REP_PASS}';"
    sudo mysql -e "GRANT REPLICATION SLAVE ON *.* TO '{REP_USER}'@'%';"
    sudo mysql -e "CREATE USER IF NOT EXISTS '{DB_USER}'@'%' IDENTIFIED BY '{DB_PASS}';"
    sudo mysql -e "GRANT ALL PRIVILEGES ON {DB_NAME}.* TO '{DB_USER}'@'%';"
    sudo mysql -e "FLUSH PRIVILEGES;"
    """

    execute_ssh_command(manager, create_user_cmd)

    print(" Getting Binary Log Coordinates...")

    status_output = execute_ssh_command(manager, "sudo mysql -e 'SHOW MASTER STATUS\\G'")

    if not status_output:
        print("Failed to get master status.")
        sys.exit(1)

    file_name = None
    position = None

    lines = status_output.split('\\n')
    for line in lines:
        if 'File:' in line:
            file_name = line.split(':')[1].strip()
        elif 'Position:' in line:
            position = line.split(':')[1].strip()


    if file_name and position:
        print(f" Master Log File: {file_name}, Position: {position}")
        return file_name, position
    else:
        print("Failed to parse master status.")
        sys.exit(1)


def setup_slave(worker, master_ip, log_file, log_pos):
    ip = worker.public_ip_address
    print(f"Setting up slave on {worker.id} with IP {ip}...")

    # Create users on worker for proxy access
    create_user_cmd = f"""
    sudo mysql -e "CREATE USER IF NOT EXISTS '{DB_USER}'@'%' IDENTIFIED BY '{DB_PASS}';"
    sudo mysql -e "GRANT ALL PRIVILEGES ON {DB_NAME}.* TO '{DB_USER}'@'%';"
    sudo mysql -e "FLUSH PRIVILEGES;"
    """
    execute_ssh_command(worker, create_user_cmd)

    # Configure replication
    change_master_cmd = f"""
    sudo mysql -e "CHANGE MASTER TO MASTER_HOST='{master_ip}', MASTER_USER='{REP_USER}', MASTER_PASSWORD='{REP_PASS}', MASTER_LOG_FILE='{log_file}', MASTER_LOG_POS={log_pos};"
    sudo mysql -e "START SLAVE;"
    """

    execute_ssh_command(worker, change_master_cmd)


def verify_replication(instances):
    print("Verifying replication status...")

    ok = True

    for instance in instances:
        ip = instance.public_ip_address

        cmd = 'sudo mysql -e "SHOW SLAVE STATUS\\G" | grep "Running: Yes"'
        res = execute_ssh_command(instance, cmd)

        if res and "IO_Running: Yes" in res and "SQL_Running: Yes" in res:
            print(f" Instance {instance.id} replication is running.")
        else:
            print(f" Instance {instance.id} replication is NOT running.")
            ok = False
            debug = execute_ssh_command(instance, 'sudo mysql -e "SHOW REPLICA STATUS\\G"')
            print(f" Debug info:\\n{debug}")
        
    return ok


if __name__ == "__main__":
    manager, workers = get_instances()

    if not manager:
        print("Manager instance not found.")
        sys.exit(1)

    if not workers:
        print("No worker instances found.")
        sys.exit(1)

    print(f" Manager: {manager.public_ip_address}, (Private IP: {manager.private_ip_address})")
    print(f" Workers: {[w.public_ip_address for w in workers]}")

    configure_node(manager, server_id=1)

    s_id = 2

    for worker in workers:
        configure_node(worker, server_id=s_id)
        s_id += 1

    print("Waiting for MySQL services to restart...")
    time.sleep(10)

    log_file, log_pos = setup_master(manager)

    for worker in workers:
        setup_slave(worker, manager.private_ip_address, log_file, log_pos)
    
    if verify_replication(workers):
        print("Replication setup successfully!")
    else:
        print("Replication setup encountered issues.")
