#!/bin/bash
# QuantGPT ECS Deployment Script
# Run on server: bash /opt/quantgpt/deploy/deploy.sh
set -euo pipefail

echo "========================================="
echo "  QuantGPT ECS Deployment"
echo "========================================="

# ---- Step 1: System dependencies ----
echo ""
echo "[1/8] Installing system dependencies..."

# Git + Nginx
dnf install -y git nginx

# Node.js 18
if ! command -v node &>/dev/null || [[ "$(node -v)" != v18* ]]; then
    echo "Installing Node.js 18..."
    curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -
    dnf install -y nodejs
fi
echo "  Node.js: $(node -v)"

# Docker
if ! command -v docker &>/dev/null; then
    echo "Installing Docker..."
    dnf install -y docker
fi
systemctl enable --now docker
echo "  Docker: $(docker --version)"

# ---- Step 2: Docker PostgreSQL ----
echo ""
echo "[2/8] Starting PostgreSQL via Docker..."

if docker ps -a --format '{{.Names}}' | grep -q '^quantgpt-pg$'; then
    if docker ps --format '{{.Names}}' | grep -q '^quantgpt-pg$'; then
        echo "  PostgreSQL container already running"
    else
        echo "  Starting existing container..."
        docker start quantgpt-pg
    fi
else
    echo "  Creating new PostgreSQL container..."
    docker run -d \
        --name quantgpt-pg \
        --restart always \
        -e POSTGRES_USER=quantgpt \
        -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-changeme} \
        -e POSTGRES_DB=quantgpt \
        -p 5433:5432 \
        -v pgdata:/var/lib/postgresql/data \
        postgres:15-alpine
fi

# Wait for PostgreSQL to be ready
echo "  Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if docker exec quantgpt-pg pg_isready -U quantgpt &>/dev/null; then
        echo "  PostgreSQL is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  ERROR: PostgreSQL failed to start"
        exit 1
    fi
    sleep 1
done

# ---- Step 3: Python dependencies ----
echo ""
echo "[3/8] Installing Python dependencies..."
cd /opt/quantgpt
pip3 install -e . 2>&1 | tail -5

# ---- Step 4: Frontend build ----
echo ""
echo "[4/8] Building frontend..."
cd /opt/quantgpt/frontend
npm install --legacy-peer-deps 2>&1 | tail -3
npm run build 2>&1 | tail -3
cd /opt/quantgpt

# ---- Step 5: Create directories ----
echo ""
echo "[5/8] Creating directories..."
mkdir -p logs reports data feedback

# ---- Step 6: Database migration ----
echo ""
echo "[6/8] Running database migrations..."
cd /opt/quantgpt
alembic upgrade head

# ---- Step 7: Systemd service ----
echo ""
echo "[7/8] Configuring systemd service..."

cat > /etc/systemd/system/quantgpt.service << 'SYSTEMD_EOF'
[Unit]
Description=QuantGPT API Server
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/quantgpt
ExecStart=/usr/bin/python3 -m quantgpt --transport http --port 8002
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

systemctl daemon-reload
systemctl enable quantgpt
systemctl restart quantgpt
echo "  QuantGPT service started"

# ---- Step 8: Nginx ----
echo ""
echo "[8/8] Configuring Nginx..."

cat > /etc/nginx/conf.d/quantgpt.conf << 'NGINX_EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
NGINX_EOF

# Remove default config if it conflicts
rm -f /etc/nginx/conf.d/default.conf

nginx -t
systemctl enable --now nginx
systemctl reload nginx
echo "  Nginx configured and running"

# ---- Verify ----
echo ""
echo "========================================="
echo "  Deployment Complete!"
echo "========================================="
echo ""

sleep 2  # Give uvicorn a moment to start

echo "Checking services..."
echo -n "  PostgreSQL: "
docker ps --format '{{.Status}}' --filter name=quantgpt-pg

echo -n "  QuantGPT:   "
systemctl is-active quantgpt || true

echo -n "  Nginx:      "
systemctl is-active nginx || true

echo ""
echo -n "  Health check: "
curl -s http://localhost:8002/api/v1/health || echo "FAILED (service may still be starting)"

echo ""
echo ""
echo "Access: http://47.111.3.102"
echo "Logs:   journalctl -u quantgpt -f"
echo ""
