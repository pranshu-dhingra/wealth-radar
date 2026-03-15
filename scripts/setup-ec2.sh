#!/usr/bin/env bash
# =============================================================================
# WealthRadar — EC2 Setup Script
# Run once on a fresh Amazon Linux 2023 or Ubuntu 22.04 instance.
# Usage: bash setup-ec2.sh
# =============================================================================
set -e

echo "====== [0/8] Add 2GB swap (essential for t3.micro 1GB RAM) ======"
if [ ! -f /swapfile ]; then
  sudo dd if=/dev/zero of=/swapfile bs=128M count=16   # 2GB
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
  echo "Swap enabled: $(free -h | grep Swap)"
else
  echo "Swap already configured — skipping"
fi

echo "====== [1/8] System update & dependencies ======"
if command -v dnf &>/dev/null; then
  # Amazon Linux 2023
  sudo dnf update -y
  sudo dnf install -y python3.11 python3.11-pip python3.11-devel git nginx
  sudo ln -sf /usr/bin/python3.11 /usr/bin/python3
else
  # Ubuntu 22.04
  sudo apt-get update -y
  sudo apt-get install -y python3.11 python3.11-venv python3.11-dev git nginx curl
fi

echo "====== [2/8] Install Node.js 20 (for PM2) ======"
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash - 2>/dev/null || \
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
if command -v dnf &>/dev/null; then
  sudo dnf install -y nodejs
else
  sudo apt-get install -y nodejs
fi
sudo npm install -g pm2

echo "====== [3/8] Clone repository ======"
cd /home/ec2-user
if [ -d "wealth-radar" ]; then
  echo "Repo already cloned — pulling latest..."
  cd wealth-radar && git pull
else
  # Replace with your actual Git repo URL
  git clone https://github.com/pranshu-dhingra/wealth-radar.git
  cd wealth-radar
fi

echo "====== [4/8] Python virtual environment & dependencies ======"
cd /home/ec2-user/wealth-radar/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "====== [5/8] Create log directory ======"
mkdir -p /home/ec2-user/logs

echo "====== [6/8] Copy .env file ======"
# The .env file must be copied to the backend directory manually via:
#   scp -i your-key.pem .env ec2-user@<EC2-IP>:/home/ec2-user/wealth-radar/backend/.env
if [ ! -f "/home/ec2-user/wealth-radar/backend/.env" ]; then
  echo "WARNING: .env file not found at /home/ec2-user/wealth-radar/backend/.env"
  echo "Copy it manually: scp -i your-key.pem .env ec2-user@<EC2-IP>:/home/ec2-user/wealth-radar/backend/.env"
fi

echo "====== [7/8] Rebuild FAISS index ======"
# The .faiss file is gitignored — rebuild it from the source documents
cd /home/ec2-user/wealth-radar
source backend/.venv/bin/activate
python scripts/index_documents.py || echo "Index rebuild failed — check logs above"

echo "====== [8/8] Start API with PM2 ======"
cd /home/ec2-user/wealth-radar/backend
pm2 start ecosystem.config.js
pm2 save
pm2 startup | tail -1 | sudo bash  # Register PM2 as system service

echo ""
echo "====== Setup complete! ======"
echo "API running at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000"
echo "Check status:   pm2 status"
echo "View logs:      pm2 logs wealth-radar-api"
echo ""
echo "Next step: Copy Nginx config and enable HTTPS (see nginx/wealth-radar.conf)"
