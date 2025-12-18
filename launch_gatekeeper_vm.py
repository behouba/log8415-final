import boto3
import os
import sys
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
KEY_NAME = os.getenv("KEY_NAME")
AMI_ID = os.getenv("AMI_ID")

GATEKEEPER_TYPE = "t2.large"

ec2 = boto3.resource('ec2', region_name=AWS_REGION)
ec2_client = boto3.client('ec2', region_name=AWS_REGION)

def create_gatekeeper_security_group():
    vpc_response = ec2_client.describe_vpcs()
    vpc_id = vpc_response['Vpcs'][0]['VpcId']

    sg_name = "gatekeeper-sg"

    try:
        response = ec2_client.describe_security_groups(GroupNames=[sg_name])
        sg_id = response['SecurityGroups'][0]['GroupId']
        print(f"Security group '{sg_name}' already exists with ID '{sg_id}'.")
        return sg_id
    except ec2_client.exceptions.ClientError:
        pass

    sg_response = ec2_client.create_security_group(
        GroupName=sg_name,
        Description='Gatekeeper - Internet facing',
        VpcId=vpc_id
    )
    sg_id = sg_response['GroupId']

    # Only SSH and port 5000 from internet
    permissions = [
        {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
        {'IpProtocol': 'tcp', 'FromPort': 5000, 'ToPort': 5000, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
    ]

    ec2_client.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=permissions)
    print(f"Created security group '{sg_name}' with ID '{sg_id}'.")
    return sg_id

def launch_gatekeeper():
    sg_id = create_gatekeeper_security_group()

    user_data = """#!/bin/bash
    sudo apt-get update -y
    sudo apt-get install -y python3-pip python3-venv
    mkdir -p /home/ubuntu/gatekeeper
    chown ubuntu:ubuntu /home/ubuntu/gatekeeper
    """

    print(f"Launching gatekeeper {GATEKEEPER_TYPE} instance...")

    instances = ec2.create_instances(
        ImageId=AMI_ID,
        InstanceType=GATEKEEPER_TYPE,
        KeyName=KEY_NAME,
        MinCount=1,
        MaxCount=1,
        SecurityGroupIds=[sg_id],
        UserData=user_data,
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': 'Gatekeeper'}]
            }
        ]
    )

    instance = instances[0]
    print(f"Waiting for gatekeeper instance {instance.id} to be running...")
    instance.wait_until_running()
    instance.reload()

    print(f"Gatekeeper Launched! Instance ID: {instance.id}")
    print(f"Public IP Address: {instance.public_ip_address}")
    print(f"Private IP Address: {instance.private_ip_address}")

    with open("gatekeeper_ip.txt", "w") as f:
        f.write(instance.public_ip_address)

    return instance

if __name__ == "__main__":
    launch_gatekeeper()
