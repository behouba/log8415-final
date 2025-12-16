import boto3
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

try:
    REGION = os.getenv("AWS_REGION")
    AMI_ID = os.getenv("AMI_ID")
    INSTANCE_TYPE = os.getenv("INSTANCE_TYPE", "t2.micro")
    KEY_NAME = os.getenv("KEY_NAME")
    SECURITY_GROUP_NAME = os.getenv("SECURITY_GROUP_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASS = os.getenv("DB_PASS")
    DB_NAME = os.getenv("DB_NAME")

    if not all([REGION, AMI_ID, KEY_NAME, SECURITY_GROUP_NAME, DB_USER, DB_PASS, DB_NAME]):
        raise ValueError("One or more required environment variables are missing.")
except Exception as e:
    print(f"Error loading environment variables: {e}")
    sys.exit(1)

# Set up boto3 EC2 client
print("Setting up EC2 client...")
ec2_resource = boto3.resource('ec2', region_name=REGION)
ec2_client = boto3.client('ec2', region_name=REGION)

def create_key_pair():
    try:
        # check if key exists remotely
        ec2_client.describe_key_pairs(KeyNames=[KEY_NAME])
        print(f"Key pair '{KEY_NAME}' already exists.")
    except ec2_client.exceptions.ClientError as e:
        # create key
        key_pair = ec2_client.create_key_pair(KeyName=KEY_NAME)
        filename = f"{KEY_NAME}.pem"
        with open(filename, 'w') as file:
            file.write(key_pair['KeyMaterial'])

        # set read-only for owner
        os.chmod(filename, 0o400)
        print(f"Created and saved key pair '{KEY_NAME}' to '{filename}'.")


def create_security_group():
    try:
        # check if security group exists
        response = ec2_client.describe_security_groups(GroupNames=[SECURITY_GROUP_NAME])
        sg_id = response['SecurityGroups'][0]['GroupId']
        print(f"Security group '{SECURITY_GROUP_NAME}' already exists with ID '{sg_id}'.")
        return sg_id
    except ec2_client.exceptions.ClientError as e:
        vpc_response = ec2_client.describe_vpcs()
        vpc_id = vpc_response['Vpcs'][0]['VpcId']

        sg_response = ec2_client.create_security_group(
            GroupName=SECURITY_GROUP_NAME,
            Description='Cluster Acccess, SSH, MySQL, ICMP',
            VpcId=vpc_id
        )
        sg_id = sg_response['GroupId']

        # Define rules
        permissions = [
            { 'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}] }, # SSH
            { 'IpProtocol': 'tcp', 'FromPort': 3306, 'ToPort': 3306, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}] }, # MySQL
            { 'IpProtocol': 'icmp', 'FromPort': -1, 'ToPort': -1, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}] } # ICMP
        ]

        ec2_client.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=permissions
        )
        return sg_id
    

def prepare_user_data():
    try:
        with open('scripts/install_mysql.sh', 'r') as file:
            script_content = file.read()
        
        # Replace placeholders with actual values
        script_content = script_content.replace('{{DB_USER}}', DB_USER)
        script_content = script_content.replace('{{DB_PASS}}', DB_PASS)
        script_content = script_content.replace('{{DB_NAME}}', DB_NAME)
        return script_content
    except Exception as e:
        print(f"Error preparing user data script: {e}")
        sys.exit(1)

def launch_instance(sg_id, user_data_script):
    print(f"Launching EC2 {INSTANCE_TYPE} instance using AMI {AMI_ID}...")

    instances = ec2_resource.create_instances(
        ImageId=AMI_ID,
        InstanceType=INSTANCE_TYPE,
        KeyName=KEY_NAME,
        MinCount=3,
        MaxCount=3,
        SecurityGroupIds=[sg_id],
        UserData=user_data_script,
        TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key': 'Name', 'Value': 'ClusterNode'}]}]
    )

    # Sleep to allow instance initialization
    print("Waiting for instances to initialize...")
    time.sleep(10)

    # Tag instances

    manager_assigned = False
    worker_count = 1

    for instance in instances:
        instance.wait_until_running()
        instance.reload() # Refresh instance attributes
        if not manager_assigned:
            name = 'ManagerNode'
            manager_assigned = True
        else:
            name = f'WorkerNode{worker_count}'
            worker_count += 1
        
        instance.create_tags(Tags=[{'Key': 'Name', 'Value': name}])
        print(f"Launched instance '{name}' with ID '{instance.id}' and public IP '{instance.public_ip_address}'.")
    print("All instances launched successfully.")
    return instances


if __name__ == "__main__":
    create_key_pair()
    sg_id = create_security_group()
    user_data_script = prepare_user_data()
    launch_instance(sg_id, user_data_script)
    