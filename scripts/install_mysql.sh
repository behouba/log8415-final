#!/bin/bash

SYSBENCH_RESULTS="/home/ubuntu/sysbench_results.txt"

# Update the system
sudo apt-get update -y
sudo apt-get upgrade -y

# Install MySQL, Unzip and Sysbench on Ubuntu 24.04
sudo apt-get install mysql-server unzip sysbench -y


# Start MySQL service
sudo systemctl start mysql
sudo systemctl enable mysql

# Wait for MySQL to be ready
for i in {1..30}; do
    if sudo mysql -e "SELECT 1" > /dev/null 2>&1; then
        echo "MySQL is ready"
        break
    fi
    echo "Waiting for MySQL to start... ($i/30)"
    sleep 2
done

# Download and install Sakila database
wget https://downloads.mysql.com/docs/sakila-db.zip
unzip sakila-db.zip

# Connect to MySQL and create Sakila database
sudo mysql -e "SOURCE sakila-db/sakila-schema.sql;"
sudo mysql -e "SOURCE sakila-db/sakila-data.sql;"

# Create user for Sysbench using the credentials from .env file
# Allow connections from any host (%) so the proxy can connect
sudo mysql -e "CREATE USER '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';"
sudo mysql -e "CREATE USER '$DB_USER'@'%' IDENTIFIED BY '$DB_PASS';"
sudo mysql -e "GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';"
sudo mysql -e "GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'%';"
sudo mysql -e "FLUSH PRIVILEGES;"

# Run Sysbenh
sudo sysbench /usr/share/sysbench/oltp_read_only.lua \
  --mysql-db=$DB_NAME \
  --mysql-user=$DB_USER \
  --mysql-password=$DB_PASS \
  prepare

# Run Sysbench benchmark test
sudo sysbench /usr/share/sysbench/oltp_read_only.lua \
  --mysql-db=$DB_NAME \
  --mysql-user=$DB_USER \
  --mysql-password=$DB_PASS \
  run > $SYSBENCH_RESULTS

echo "MySQL installation and Sysbench benchmark completed. Results saved in $SYSBENCH_RESULTS"
