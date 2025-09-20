# Deployment Guide

## Overview

UIAutodev supports multiple deployment strategies depending on your infrastructure requirements and target environment. This guide covers development, staging, and production deployment scenarios.

![Deployment Process](diagrams/processes/deployment-process.svg)

## Deployment Options

### 1. Development Deployment

**Recommended for**: Local development, testing, and debugging

```bash
# Quick start (requires Nix)
git clone <repository-url>
cd uiagent
nix develop
./start-dev.sh
```

**Services**:
- Frontend: http://localhost:5173 (Vite dev server)
- Backend: http://localhost:20242 (Uvicorn with --reload)
- Hot reload enabled for both frontend and backend

**Requirements**:
- Nix package manager
- Connected Android device with USB debugging
- 4GB RAM minimum, 8GB recommended

### 2. Container Deployment

**Recommended for**: Production environments, cloud deployments, CI/CD

#### Docker Compose Setup

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  uiagent-backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "20242:20242"
    environment:
      - UIAUTODEV_LOG_LEVEL=INFO
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - /dev/bus/usb:/dev/bus/usb
      - ./data:/app/data
    privileged: true  # Required for ADB device access
    networks:
      - uiagent-network

  uiagent-frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "8080:80"
    environment:
      - VITE_API_BASE_URL=http://localhost:20242
    depends_on:
      - uiagent-backend
    networks:
      - uiagent-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/ssl
    depends_on:
      - uiagent-frontend
      - uiagent-backend
    networks:
      - uiagent-network

networks:
  uiagent-network:
    driver: bridge
```

#### Backend Dockerfile

Create `Dockerfile.backend`:
```dockerfile
# Multi-stage build with Nix
FROM nixos/nix:latest AS builder

# Copy Nix configuration
COPY flake.nix flake.lock ./

# Build the environment
RUN nix --extra-experimental-features "nix-command flakes" \
    develop --command echo "Environment built"

# Runtime stage
FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    android-tools-adb \
    android-tools-fastboot \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
WORKDIR /app
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 20242

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:20242/api/info || exit 1

# Start command
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "20242"]
```

#### Frontend Dockerfile

Create `frontend/Dockerfile`:
```dockerfile
# Build stage
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/build /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

#### Nginx Configuration

Create `frontend/nginx.conf`:
```nginx
server {
    listen 80;
    server_name localhost;

    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # Frontend routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api/ {
        proxy_pass http://uiagent-backend:20242;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static assets with caching
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 3. NixOS Deployment

**Recommended for**: NixOS servers, declarative infrastructure

#### NixOS Module

Create `nixos-module.nix`:
```nix
{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.services.uiagent;
in
{
  options.services.uiagent = {
    enable = mkEnableOption "UIAutodev service";

    user = mkOption {
      type = types.str;
      default = "uiagent";
      description = "User to run UIAutodev as";
    };

    group = mkOption {
      type = types.str;
      default = "uiagent";
      description = "Group to run UIAutodev as";
    };

    port = mkOption {
      type = types.port;
      default = 20242;
      description = "Port to run UIAutodev backend on";
    };

    dataDir = mkOption {
      type = types.path;
      default = "/var/lib/uiagent";
      description = "Data directory for UIAutodev";
    };

    environmentFile = mkOption {
      type = types.nullOr types.path;
      default = null;
      description = "Environment file with secrets";
    };
  };

  config = mkIf cfg.enable {
    users.users.${cfg.user} = {
      isSystemUser = true;
      group = cfg.group;
      home = cfg.dataDir;
      createHome = true;
    };

    users.groups.${cfg.group} = {};

    systemd.services.uiagent-backend = {
      description = "UIAutodev Backend Service";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];

      serviceConfig = {
        Type = "simple";
        User = cfg.user;
        Group = cfg.group;
        WorkingDirectory = cfg.dataDir;
        ExecStart = "${pkgs.python3}/bin/uvicorn app:app --host 0.0.0.0 --port ${toString cfg.port}";
        Restart = "always";
        RestartSec = 10;

        # Security settings
        NoNewPrivileges = true;
        PrivateTmp = true;
        PrivateDevices = false;  # Need device access for ADB
        ProtectHome = true;
        ProtectClock = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictSUIDSGID = true;
        RemoveIPC = true;
        LockPersonality = true;
      };

      environment = {
        PYTHONPATH = cfg.dataDir;
      };

      environmentFile = cfg.environmentFile;
    };

    # Nginx reverse proxy
    services.nginx = {
      enable = true;
      virtualHosts."uiagent.local" = {
        locations."/" = {
          root = "${cfg.dataDir}/frontend/build";
          tryFiles = "$uri $uri/ /index.html";
        };

        locations."/api/" = {
          proxyPass = "http://127.0.0.1:${toString cfg.port}";
          proxyWebsockets = true;
        };
      };
    };

    # Firewall configuration
    networking.firewall.allowedTCPPorts = [ 80 443 cfg.port ];

    # ADB udev rules for device access
    services.udev.packages = [ pkgs.android-udev-rules ];
  };
}
```

#### NixOS Configuration

Add to your NixOS configuration:
```nix
# configuration.nix
{
  imports = [ ./nixos-module.nix ];

  services.uiagent = {
    enable = true;
    port = 20242;
    environmentFile = "/etc/uiagent/environment";
  };

  # Required packages
  environment.systemPackages = with pkgs; [
    android-tools
    python3
  ];

  # USB access for ADB
  users.users.uiagent.extraGroups = [ "plugdev" ];
}
```

### 4. Traditional Server Deployment

**Recommended for**: Ubuntu/Debian servers, traditional hosting

#### System Requirements

```bash
# Ubuntu 22.04 LTS or later
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y \
    python3.13 \
    python3.13-venv \
    python3-pip \
    nodejs \
    npm \
    nginx \
    android-tools-adb \
    android-tools-fastboot \
    git \
    curl
```

#### Application Setup

```bash
# Create application user
sudo useradd -r -s /bin/bash -d /opt/uiagent uiagent
sudo mkdir -p /opt/uiagent
sudo chown uiagent:uiagent /opt/uiagent

# Switch to application user
sudo -u uiagent -i

# Clone and setup application
cd /opt/uiagent
git clone <repository-url> .

# Python backend setup
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend build
cd frontend
npm install
npm run build
cd ..

# Create environment file
cp .envexample .env
# Edit .env with production settings
```

#### Systemd Service

Create `/etc/systemd/system/uiagent-backend.service`:
```ini
[Unit]
Description=UIAutodev Backend Service
After=network.target

[Service]
Type=simple
User=uiagent
Group=uiagent
WorkingDirectory=/opt/uiagent
Environment=PATH=/opt/uiagent/venv/bin
EnvironmentFile=/opt/uiagent/.env
ExecStart=/opt/uiagent/venv/bin/uvicorn app:app --host 127.0.0.1 --port 20242
Restart=always
RestartSec=10

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectClock=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RemoveIPC=true
LockPersonality=true

[Install]
WantedBy=multi-user.target
```

#### Nginx Configuration

Create `/etc/nginx/sites-available/uiagent`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Frontend
    location / {
        root /opt/uiagent/frontend/build;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:20242;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
}
```

Enable and start services:
```bash
# Enable nginx site
sudo ln -s /etc/nginx/sites-available/uiagent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Start UIAutodev service
sudo systemctl enable uiagent-backend
sudo systemctl start uiagent-backend
sudo systemctl status uiagent-backend
```

## SSL/TLS Configuration

### Let's Encrypt with Certbot

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### Manual SSL Certificate

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Rest of configuration...
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

## Environment Configuration

### Production Environment Variables

Create secure environment configuration:

```bash
# .env (Backend)
UIAUTODEV_LOG_LEVEL=INFO
CORS_ORIGINS=https://your-domain.com
DATABASE_URL=postgresql://user:password@localhost/uiagent
REDIS_URL=redis://localhost:6379

# API Keys (keep secure)
DEEPSEEK_API_KEY=your_deepseek_api_key
OPENAI_API_KEY=your_openai_api_key

# Security
SECRET_KEY=your_secret_key_here
ALLOWED_HOSTS=your-domain.com

# Performance
WORKERS=4
MAX_CONNECTIONS=100
TIMEOUT=30
```

### Frontend Environment Variables

```bash
# frontend/.env.production
VITE_API_BASE_URL=https://your-domain.com
VITE_WS_URL=wss://your-domain.com
VITE_ENVIRONMENT=production
VITE_ANALYTICS_ID=your_analytics_id
```

## Security Configuration

### Firewall Setup

```bash
# UFW (Ubuntu)
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw deny 20242  # Block direct backend access

# iptables (alternative)
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 20242 -s 127.0.0.1 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 20242 -j DROP
```

### Application Security

1. **API Security**:
   - Enable CORS only for trusted domains
   - Implement rate limiting
   - Add API authentication for production
   - Sanitize all inputs

2. **Device Security**:
   - Restrict ADB access to application user
   - Use device-specific authentication
   - Implement device access logging

3. **System Security**:
   - Run services with minimal privileges
   - Enable AppArmor/SELinux
   - Regular security updates
   - Log monitoring and alerting

## Monitoring and Logging

### Application Monitoring

**Health Checks**:
```python
# Add to app.py
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": __version__,
        "services": {
            "devices": len(provider.list_devices()),
            "llm": "available"
        }
    }
```

**Prometheus Metrics**:
```bash
# Install prometheus client
pip install prometheus-client

# Add metrics endpoint
from prometheus_client import Counter, Histogram, generate_latest

api_requests = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint'])
request_duration = Histogram('request_duration_seconds', 'Request duration')

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### Log Management

**Structured Logging**:
```python
import structlog

logger = structlog.get_logger()

# Use structured logging
logger.info("Device operation", device_id=serial, operation="screenshot", duration=0.5)
```

**Log Rotation**:
```bash
# /etc/logrotate.d/uiagent
/var/log/uiagent/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

## Backup and Recovery

### Application Backup

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/uiagent"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup application files
tar -czf "$BACKUP_DIR/uiagent_app_$DATE.tar.gz" /opt/uiagent

# Backup configuration
cp /opt/uiagent/.env "$BACKUP_DIR/env_$DATE"

# Backup nginx configuration
cp /etc/nginx/sites-available/uiagent "$BACKUP_DIR/nginx_$DATE.conf"

# Clean old backups (keep 30 days)
find "$BACKUP_DIR" -type f -mtime +30 -delete
```

### Database Backup (if applicable)

```bash
# PostgreSQL backup
pg_dump uiagent > "/backups/uiagent/db_$(date +%Y%m%d_%H%M%S).sql"

# Redis backup
cp /var/lib/redis/dump.rdb "/backups/uiagent/redis_$(date +%Y%m%d_%H%M%S).rdb"
```

## Performance Optimization

### Backend Optimization

1. **Use Production ASGI Server**:
   ```bash
   # Gunicorn with Uvicorn workers
   pip install gunicorn
   gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

2. **Enable Response Caching**:
   ```python
   from fastapi_cache import FastAPICache
   from fastapi_cache.backends.redis import RedisBackend

   FastAPICache.init(RedisBackend(), prefix="uiagent-cache")
   ```

3. **Database Connection Pooling**:
   ```python
   from sqlalchemy.pool import QueuePool

   engine = create_engine(
       DATABASE_URL,
       poolclass=QueuePool,
       pool_size=20,
       max_overflow=30
   )
   ```

### Frontend Optimization

1. **Build Optimization**:
   ```javascript
   // vite.config.js
   export default {
     build: {
       rollupOptions: {
         output: {
           manualChunks: {
             vendor: ['svelte', '@codemirror/view'],
             editor: ['@codemirror/lang-python', '@codemirror/autocomplete']
           }
         }
       }
     }
   }
   ```

2. **CDN Configuration**:
   ```nginx
   # Use CDN for static assets
   location /assets/ {
       expires 1y;
       add_header Cache-Control "public, immutable";
       # Redirect to CDN in production
       # return 301 https://cdn.example.com$request_uri;
   }
   ```

## Scaling Considerations

### Horizontal Scaling

1. **Load Balancer Configuration**:
   ```nginx
   upstream uiagent_backend {
       server 127.0.0.1:20242;
       server 127.0.0.1:20243;
       server 127.0.0.1:20244;
   }
   ```

2. **Session Management**:
   - Use Redis for shared session storage
   - Implement sticky sessions for device connections
   - Consider WebSocket connection affinity

3. **Database Scaling**:
   - Read replicas for query scaling
   - Connection pooling and load balancing
   - Database partitioning for large datasets

### Container Orchestration

**Kubernetes Deployment**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: uiagent-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: uiagent-backend
  template:
    metadata:
      labels:
        app: uiagent-backend
    spec:
      containers:
      - name: backend
        image: uiagent/backend:latest
        ports:
        - containerPort: 20242
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: uiagent-secrets
              key: database-url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

## Troubleshooting

### Common Deployment Issues

1. **Port Conflicts**:
   ```bash
   sudo netstat -tulpn | grep :20242
   sudo lsof -i :20242
   ```

2. **Permission Issues**:
   ```bash
   # Check ADB permissions
   ls -la /dev/bus/usb/
   groups uiagent

   # Fix permissions
   sudo usermod -a -G plugdev uiagent
   ```

3. **Service Startup Issues**:
   ```bash
   sudo systemctl status uiagent-backend
   sudo journalctl -u uiagent-backend -f
   ```

4. **Database Connection Issues**:
   ```bash
   # Test database connection
   psql -h localhost -U uiagent -d uiagent
   ```

### Performance Issues

1. **High Memory Usage**:
   - Monitor with `htop` or `ps aux`
   - Check for memory leaks in Python processes
   - Optimize database queries

2. **Slow API Responses**:
   - Enable API request logging
   - Profile slow endpoints
   - Check database query performance

3. **Device Connection Issues**:
   - Verify ADB connection: `adb devices`
   - Check USB cable and port
   - Restart ADB daemon: `adb kill-server && adb start-server`

---

For development setup, see [DEVELOPMENT.md](DEVELOPMENT.md).
For architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md).