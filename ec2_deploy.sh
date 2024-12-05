#!/bin/bash

# Update the system
sudo yum update -y

# Install Docker
sudo yum -y install docker

# Start Docker service
sudo service docker start

# Enable Docker service to start on boot
sudo systemctl enable docker

# Add ec2-user to the docker group
sudo usermod -a -G docker ec2-user

# Give ec2-user permission to access Docker socket
sudo chmod 666 /var/run/docker.sock

# Install Git
sudo yum install git -y

# Check Git version
git --version

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Pull repository from GitHub
git clone https://github.com/DrCBeatz/music-store-assistant.git
cd music-store-assistant

# Pull the latest Docker image and start the app
docker-compose up -d --build
