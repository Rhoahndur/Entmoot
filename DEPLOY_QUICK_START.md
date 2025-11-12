# Entmoot - Quick Deployment Guide

## Overview

You have 3 deployment options, ranked by ease of setup:

1. **Railway/Render (Easiest)** - 5 minutes, free tier available
2. **Docker on VPS (Recommended)** - 15 minutes, $10-20/month
3. **Cloud Provider (Production)** - 1-3 days, $500-2000/month (see docs/deployment.md)

---

## Option 1: Railway.app (Easiest - 5 minutes)

### What You Get
- ✅ Free tier available ($5 credit/month)
- ✅ Automatic HTTPS
- ✅ Zero configuration deployment
- ✅ Git-based deployments
- ✅ PostgreSQL + Redis included

### Steps

#### 1. Sign up at Railway.app
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login
```

#### 2. Create Project
```bash
cd /Users/aleksandrgaun/Downloads/Entmoot

# Initialize Railway project
railway init

# Add PostgreSQL
railway add --plugin postgresql

# Add Redis
railway add --plugin redis
```

#### 3. Configure Environment
Railway will auto-set `DATABASE_URL` and `REDIS_URL`. You just need to add:

```bash
railway variables set SECRET_KEY=$(openssl rand -hex 32)
railway variables set ENVIRONMENT=production
railway variables set CORS_ORIGINS=https://your-app.railway.app
```

#### 4. Deploy
```bash
# Deploy backend
railway up

# Deploy frontend separately or use Railway templates
```

**Estimated Time:** 5-10 minutes
**Cost:** Free tier ($5 credit/month) or $5-20/month

---

## Option 2: Docker on VPS (Recommended - 15 minutes)

### What You Get
- ✅ Full control
- ✅ Affordable ($10-20/month)
- ✅ Easy to maintain
- ✅ One-command deployment

### Prerequisites
- A server with Docker installed (DigitalOcean, Linode, Vultr, Hetzner)
- Domain name (optional but recommended)

### Steps

#### 1. Get a Server

**DigitalOcean Droplet (Recommended)**
- Size: 2 GB RAM / 2 CPUs ($18/month)
- OS: Ubuntu 22.04 LTS
- Add Firewall: Allow ports 22, 80, 443

**Quick Setup:**
```bash
# On your local machine
doctl compute droplet create entmoot \
  --size s-2vcpu-2gb \
  --image ubuntu-22-04-x64 \
  --region nyc1
```

#### 2. Install Docker on Server

```bash
# SSH into your server
ssh root@YOUR_SERVER_IP

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt-get update
apt-get install -y docker-compose-plugin

# Verify
docker --version
docker compose version
```

#### 3. Deploy Application

```bash
# Clone your repo
cd /opt
git clone https://github.com/YOUR_USERNAME/Entmoot.git
cd Entmoot

# Create environment file
cp .env.example .env

# Generate secrets
export SECRET_KEY=$(openssl rand -hex 32)
export POSTGRES_PASSWORD=$(openssl rand -hex 16)
export REDIS_PASSWORD=$(openssl rand -hex 16)

# Update .env file
cat > .env << EOF
# Core
ENVIRONMENT=production
SECRET_KEY=${SECRET_KEY}

# Database
POSTGRES_DB=entmoot
POSTGRES_USER=entmoot
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_PORT=5432

# Redis
REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_PORT=6379

# API
BACKEND_PORT=8000
FRONTEND_PORT=80
MAX_UPLOAD_SIZE=52428800

# CORS - Update with your domain
CORS_ORIGINS=http://YOUR_DOMAIN,https://YOUR_DOMAIN

# Storage
UPLOADS_DIR=/app/data/uploads
TEMP_DIR=/app/data/temp
EOF

# Build and start
docker compose up -d

# Check status
docker compose ps
docker compose logs -f
```

#### 4. Set Up HTTPS (Optional but Recommended)

```bash
# Install Certbot
apt-get install -y certbot

# Get SSL certificate
certbot certonly --standalone -d your-domain.com

# Add nginx proxy (create nginx-proxy.conf)
cat > nginx-proxy.conf << 'EOF'
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# Install nginx
apt-get install -y nginx
cp nginx-proxy.conf /etc/nginx/sites-available/entmoot
ln -s /etc/nginx/sites-available/entmoot /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

#### 5. Verify Deployment

```bash
# Check health
curl http://YOUR_SERVER_IP:8000/health
curl http://YOUR_SERVER_IP/

# Or if you set up HTTPS
curl https://your-domain.com/health
```

**Estimated Time:** 15-30 minutes
**Cost:** $10-20/month

---

## Option 3: Production Cloud Deployment

For AWS, GCP, or Azure deployment with full production features (load balancing, auto-scaling, monitoring, backups), see:

- **Full Guide:** `docs/deployment.md`
- **Checklist:** `DEPLOYMENT_CHECKLIST.md`
- **Environment Templates:** `.env.production.example`

**Estimated Time:** 1-3 days
**Cost:** $500-2000/month

---

## Quick Test Locally First

Before deploying, test the full Docker setup locally:

```bash
cd /Users/aleksandrgaun/Downloads/Entmoot

# Create .env file
cp .env.example .env

# Edit .env with your values
nano .env

# Build and run
docker compose build
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f

# Test
open http://localhost
curl http://localhost:8000/health

# Stop
docker compose down
```

---

## Maintenance Commands

### View Logs
```bash
docker compose logs -f
docker compose logs backend
docker compose logs frontend
```

### Restart Services
```bash
docker compose restart
docker compose restart backend
```

### Update Deployment
```bash
git pull
docker compose build
docker compose up -d
```

### Backup Database
```bash
docker compose exec postgres pg_dump -U entmoot entmoot > backup-$(date +%Y%m%d).sql
```

### Restore Database
```bash
cat backup-20241111.sql | docker compose exec -T postgres psql -U entmoot entmoot
```

---

## Troubleshooting

### Service Won't Start
```bash
# Check logs
docker compose logs backend

# Check if ports are in use
lsof -i :8000
lsof -i :80

# Restart everything
docker compose down
docker compose up -d
```

### Database Connection Issues
```bash
# Check postgres is running
docker compose ps postgres

# Test connection
docker compose exec postgres psql -U entmoot -d entmoot -c "SELECT 1;"
```

### Frontend Can't Reach Backend
```bash
# Check CORS_ORIGINS in .env
# Make sure it includes your frontend URL

# Restart backend after changing .env
docker compose restart backend
```

---

## Next Steps After Deployment

1. **Set up monitoring** - Install uptime monitoring (UptimeRobot, Pingdom)
2. **Configure backups** - Set up automated database backups
3. **Enable HTTPS** - Get SSL certificate (Let's Encrypt)
4. **Set up CI/CD** - Enable GitHub Actions for auto-deployment
5. **Add custom domain** - Point your domain to the server

---

## Support

- **Documentation:** `docs/` directory
- **Issues:** GitHub Issues
- **Email:** [your-email]

---

## Cost Comparison

| Option | Setup Time | Monthly Cost | Best For |
|--------|------------|--------------|----------|
| Railway | 5 min | $0-20 | Testing, demos, MVPs |
| VPS | 15 min | $10-20 | Small teams, production |
| AWS/GCP | 1-3 days | $500-2000 | Enterprise, high traffic |

## My Recommendation

Start with **Option 2 (VPS)** because:
- ✅ Full control over your infrastructure
- ✅ Easy to understand and debug
- ✅ Affordable
- ✅ Can scale later to cloud providers
- ✅ One `.env` file to manage
- ✅ Docker Compose handles everything

You can always migrate to AWS/GCP later when you need advanced features like auto-scaling, multi-region, etc.
