#!/bin/bash
# User data script for FinEventStream producer instances.
# Installs dependencies, clones the application repo, and starts the producer script.

# Log all user-data output for debugging purposes.
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

set -e # Exit immediately if a command exits with a non-zero status.

echo "INFO: Starting producer instance setup."

# Install base dependencies
yum update -y
yum install -y git python3 python3-pip
echo "INFO: System dependencies installed."

# Set up application directory and clone repo as ec2-user
APP_DIR="/home/ec2-user/app"
mkdir -p $APP_DIR
chown ec2-user:ec2-user $APP_DIR
cd $APP_DIR
sudo -u ec2-user git clone ${github_repo_url} .
echo "INFO: Application repository cloned."

# Install Python application dependencies
pip3 install -r src/producer/requirements.txt
echo "INFO: Python dependencies installed."

# Set API key from Terraform template variable and export for the producer process
export FINNHUB_API_KEY="${finnhub_api_key}"
echo "INFO: FINNHUB_API_KEY environment variable configured."

# Launch the specified producer script in the background using nohup
PRODUCER_SCRIPT_PATH="src/producer/${script_to_run}"
echo "INFO: Launching producer: ${script_to_run}"
sudo -u ec2-user nohup python3 $PRODUCER_SCRIPT_PATH &

echo "INFO: User data script execution finished."