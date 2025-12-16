#!/bin/bash

# source .env file
if [ -f .env ]; then
    source .env
else
    echo ".env file not found!"
    exit 1
fi

# Warn that all EC2 instances will be terminated

echo "WARNING: This script will terminate all EC2 instances in region: $AWS_REGION"
read -p "Are you sure you want to proceed? (y/N): " REPLY
echo    # move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operation cancelled."
    exit 1
fi

# Find instances associated with the key pair
INSTANCE_IDS=$(aws ec2 describe-instances \
    --region "$AWS_REGION" \
    --filters "Name=key-name,Values=$KEY_NAME" \
    --query "Reservations[].Instances[].InstanceId" \
    --output text)

if [ -z "$INSTANCE_IDS" ]; then
    echo "No EC2 instances found with key pair: $KEY_NAME"
    exit 0
fi

echo "Terminating the following EC2 instances: $INSTANCE_IDS"
# Terminate instances
aws ec2 terminate-instances \
    --region "$AWS_REGION" \
    --instance-ids $INSTANCE_IDS

echo "Waiting for instances to terminate..."
aws ec2 wait instance-terminated \
    --region "$AWS_REGION" \
    --instance-ids $INSTANCE_IDS
echo "All specified EC2 instances have been terminated."


# Delete security group
echo "Deleting security group: $SG_NAME"
count=0
while true; do
    aws ec2 delete-security-group \
        --region "$AWS_REGION" \
        --group-name "$SG_NAME" && break

    count=$((count + 1))
    if [ $count -ge 5 ]; then
        echo "Failed to delete security group after multiple attempts."
        exit 1
    fi
    echo "Retrying to delete security group in 5 seconds..."
    sleep 5
done

# Delete key pair
echo "Deleting key pair: $KEY_NAME"
aws ec2 delete-key-pair \
    --region "$AWS_REGION" \
    --key-name "$KEY_NAME"
rm -f "${KEY_NAME}.pem"
echo "Key pair deleted."

echo "Cleanup completed successfully."
