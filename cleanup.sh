#!/bin/bash

if [ -f .env ]; then
    source .env
else
    echo ".env file not found!"
    exit 1
fi

echo "WARNING: This script will terminate all EC2 instances in region: $AWS_REGION"
read -p "Are you sure you want to proceed? (y/N): " REPLY
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operation cancelled."
    exit 1
fi

# Find all instances with the key pair (all states)
ALL_INSTANCE_IDS=$(aws ec2 describe-instances \
    --region "$AWS_REGION" \
    --filters "Name=key-name,Values=$KEY_NAME" \
    --query "Reservations[].Instances[].InstanceId" \
    --output text)

if [ -z "$ALL_INSTANCE_IDS" ]; then
    echo "No instances found with key pair: $KEY_NAME"
else
    # Find instances that are not already terminated
    RUNNING_INSTANCE_IDS=$(aws ec2 describe-instances \
        --region "$AWS_REGION" \
        --filters "Name=key-name,Values=$KEY_NAME" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
        --query "Reservations[].Instances[].InstanceId" \
        --output text)

    if [ -n "$RUNNING_INSTANCE_IDS" ]; then
        echo "Terminating instances: $RUNNING_INSTANCE_IDS"
        aws ec2 terminate-instances \
            --region "$AWS_REGION" \
            --instance-ids $RUNNING_INSTANCE_IDS

        echo "Waiting for instances to terminate..."
        aws ec2 wait instance-terminated \
            --region "$AWS_REGION" \
            --instance-ids $RUNNING_INSTANCE_IDS
    fi

    echo "All instances terminated."
fi


# Wait a bit for network interfaces to detach
echo "Waiting for network interfaces to detach..."
sleep 10

# Delete security groups
for SG in "$SG_NAME" "gatekeeper-sg"; do
    echo "Attempting to delete security group: $SG"
    count=0
    while [ $count -lt 10 ]; do
        if aws ec2 delete-security-group --region "$AWS_REGION" --group-name "$SG" 2>/dev/null; then
            echo "Deleted security group: $SG"
            break
        fi
        count=$((count + 1))
        if [ $count -ge 10 ]; then
            echo "Could not delete security group $SG (may not exist or still in use)"
            break
        fi
        echo "Retrying in 5 seconds... ($count/10)"
        sleep 5
    done
done

# Delete key pair
echo "Deleting key pair: $KEY_NAME"
if aws ec2 delete-key-pair --region "$AWS_REGION" --key-name "$KEY_NAME" 2>/dev/null; then
    echo "Key pair deleted from AWS"
else
    echo "Key pair not found in AWS (may already be deleted)"
fi

rm -f "${KEY_NAME}.pem"
echo "Local key file removed"

# Clean up generated files
rm -f proxy_ip.txt gatekeeper_ip.txt benchmark_results.json
echo "Cleaned up generated files"

echo ""
echo "Cleanup completed successfully!"
echo "All EC2 instances, security groups, and keys have been removed."
