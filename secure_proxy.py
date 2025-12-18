import boto3
import os
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
SG_NAME = os.getenv("SG_NAME")

ec2_client = boto3.client('ec2', region_name=AWS_REGION)

def secure_proxy():
    # Get cluster security group
    try:
        cluster_sg_response = ec2_client.describe_security_groups(GroupNames=[SG_NAME])
        cluster_sg_id = cluster_sg_response['SecurityGroups'][0]['GroupId']
    except Exception as e:
        print(f"Error finding cluster security group: {e}")
        return

    # Get gatekeeper security group
    try:
        gatekeeper_sg_response = ec2_client.describe_security_groups(GroupNames=['gatekeeper-sg'])
        gatekeeper_sg_id = gatekeeper_sg_response['SecurityGroups'][0]['GroupId']
    except Exception as e:
        print(f"Error finding gatekeeper security group: {e}")
        return

    print(f"Cluster SG: {cluster_sg_id}")
    print(f"Gatekeeper SG: {gatekeeper_sg_id}")

    # Remove public access to port 5000
    try:
        ec2_client.revoke_security_group_ingress(
            GroupId=cluster_sg_id,
            IpPermissions=[
                {'IpProtocol': 'tcp', 'FromPort': 5000, 'ToPort': 5000, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
            ]
        )
        print("Removed public access to port 5000")
    except Exception as e:
        print(f"Could not remove public access (may not exist): {e}")

    # Add access only from gatekeeper
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=cluster_sg_id,
            IpPermissions=[
                {'IpProtocol': 'tcp', 'FromPort': 5000, 'ToPort': 5000,
                 'UserIdGroupPairs': [{'GroupId': gatekeeper_sg_id}]}
            ]
        )
        print("Added port 5000 access only from gatekeeper")
    except Exception as e:
        print(f"Error adding gatekeeper access: {e}")

    print("Proxy is now secured - only accessible from gatekeeper")

if __name__ == "__main__":
    secure_proxy()
