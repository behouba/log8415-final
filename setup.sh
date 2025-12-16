#!/bin/bash

# Detect AWS region from AWS CLI configuration (defauult to us-east-1 if not set)
AWS_REGION=$(aws configure get region)
if [ -z "$AWS_REGION" ]; then
  AWS_REGION="us-east-1"
fi

echo "AWS Region: $AWS_REGION"

# Get the latest Ubuntu 24.04 LTS AMI ID for the detected region
# https://documentation.ubuntu.com/aws/aws-how-to/instances/find-ubuntu-images/
AMI_ID=$(aws ec2 describe-images \
   --owners 099720109477 \
   --filters \
      "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
   --query "Images | sort_by(@, &CreationDate) | [-1].ImageId" \
   --output text)

if [ -z "$AMI_ID" ]; then
  echo "Failed to retrieve the latest Ubuntu 24.04 LTS AMI ID for region $AWS_REGION"
  exit 1
fi

echo "Found AMI ID: $AMI_ID"

# Generate .env file
cat <<EOF > .env
# AWS Configuration (Generated automatically)
AWS_REGION=$AWS_REGION
AMI_ID=$AMI_ID
INSTANCE_TYPE=t2.micro
KEY_NAME=cluster-key
SEC_GROUP_NAME=cluster-sg

# Database Credentials
DB_USER=sbtest
DB_PASS=sbtest_password
DB_NAME=sakila
EOF

echo ".env file generated successfully."