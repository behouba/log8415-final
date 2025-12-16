import boto3
import os
import time
import sys
from dotenv import load_dotenv

load_dotenv()


AWS_REGION = os.getenv("AWS_REGION")
KEY_NAME = os.getenv("KEY_NAME")
AMI_ID = os.getenv("AMI_ID")
SG_NAME = os.getenv("SG_NAME")

if not all([AWS_REGION, KEY_NAME, AMI_ID, SG_NAME]):
    print("One or more required environment variables are missing.")
    sys.exit(1)

PROXY_TYPE = "t2.large"

ec2 = boto3.resource('ec2', region_name=AWS_REGION)
ec2_client = boto3.client('ec2', region_name=AWS_REGION)


def get_security_group_id():
    try:
        response = ec2_client.describe_security_groups(GroupNames=[SG_NAME])
        return response['SecurityGroups'][0]['GroupId']
    except ec2_client.exceptions.ClientError as e:
        print(f"Error retrieving security group '{SG_NAME}': {e}")
        sys.exit(1)

def launch_proxy():
    sg_id = get_security_group_id()

    user_data = """#!/bin/bash
    sudo apt-get update -y
    sudo apt-get install -y python3-pip python3-venv mysql-client
    mkdir -p /home/ubuntu/proxy
    chown ubuntu:ubuntu /home/ubuntu/proxy
    """

    print(f"Launching proxy {PROXY_TYPE} instance...")

    instances = ec2.create_instances(
        ImageId=AMI_ID,
        InstanceType=PROXY_TYPE,
        KeyName=KEY_NAME,
        MinCount=1,
        MaxCount=1,
        SecurityGroupIds=[sg_id],
        UserData=user_data,
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': 'Proxy'}]
            }
        ]
    )

    instance = instances[0]
    print(f"Waiting for proxy instance {instance.id} to be running...")
    instance.wait_until_running()
    instance.reload()

    print(f"Proxy Launched! Instance ID: {instance.id}")
    print(f"Public IP Address: {instance.public_ip_address}")
    print(f"Private IP Address: {instance.private_ip_address}")

    # save ip to file for later use
    with open("proxy_ip.txt", "w") as f:
        f.write(instance.public_ip_address)

    return instance

if __name__ == "__main__":
    launch_proxy()
