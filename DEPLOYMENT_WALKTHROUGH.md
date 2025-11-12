# 🚀 Entmoot Production Deployment Walkthrough

This is your step-by-step guide to deploy Entmoot to production.

## 📋 What's Been Set Up For You

✅ Docker configuration (Dockerfile, docker-compose.yml)
✅ Frontend build process (React + Vite + Nginx)
✅ Backend API (FastAPI + PostgreSQL + Redis)
✅ Environment configuration templates
✅ Comprehensive deployment documentation
✅ Automated deployment script

## 🎯 Choose Your Path

### Path A: Test Locally First (Recommended)
**Time: 5 minutes**

This lets you see the full production setup running on your machine.

```bash
cd /Users/aleksandrgaun/Downloads/Entmoot

# Run the automated deployment script
./deploy.sh

# Select option 2 (Production Build)
# The script will:
# 1. Check prerequisites
# 2. Create .env file with generated secrets
# 3. Build Docker images
# 4. Start all services
# 5. Run health checks

# Access your app:
# Frontend: http://localhost
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

**What you'll see:**
- A working version of Entmoot with PostgreSQL + Redis
- Exactly what production will look like
- Ability to test map editing, violations, etc.

---

### Path B: Deploy to a Server (Production)
**Time: 15-30 minutes | Cost: $10-20/month**

#### Step 1: Get a Server

**Option A - DigitalOcean (Easiest)**
1. Go to https://digitalocean.com
2. Create account ($200 credit for 60 days with referral)
3. Create Droplet:
   - Image: Ubuntu 22.04 LTS
   - Plan: Basic - $18/month (2GB RAM, 2 CPUs)
   - Region: Choose closest to your users
   - Authentication: SSH Key (generate if needed)
4. Note your server IP address

**Option B - Other Providers**
- Linode: https://linode.com ($100 credit)
- Vultr: https://vultr.com
- Hetzner: https://hetzner.com (cheapest, Europe only)

#### Step 2: Configure Server

```bash
# SSH into your server
ssh root@YOUR_SERVER_IP

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt-get update
apt-get install -y docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

#### Step 3: Deploy Application

```bash
# Clone your repository
cd /opt
git clone https://github.com/YOUR_USERNAME/Entmoot.git
cd Entmoot

# Run the deployment script
./deploy.sh

# Select option 2 (Production Build)
# Review and update the .env file when prompted
# Update CORS_ORIGINS with your server IP or domain
```

#### Step 4: Open Firewall

```bash
# Allow HTTP and HTTPS
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 22/tcp
ufw enable
```

#### Step 5: Test Deployment

```bash
# Check services are running
docker compose ps

# Test backend
curl http://YOUR_SERVER_IP:8000/health

# Test frontend
curl http://YOUR_SERVER_IP/
```

Open browser: `http://YOUR_SERVER_IP`

---

### Path C: Add HTTPS (Optional but Recommended)
**Time: 10 minutes**

#### Prerequisites
- Own a domain name (Namecheap, Google Domains, etc.)
- Point domain A record to your server IP

#### Setup Let's Encrypt

```bash
# Install Certbot
apt-get install -y certbot python3-certbot-nginx

# Get SSL certificate
certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Install Nginx reverse proxy
apt-get install -y nginx

# Create nginx config
cat > /etc/nginx/sites-available/entmoot << 'EOF'
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Frontend
    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend docs
    location /docs {
        proxy_pass http://localhost:8000/docs;
        proxy_set_header Host $host;
    }

    # Backend health check
    location /health {
        proxy_pass http://localhost:8000/health;
    }
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/entmoot /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Test configuration
nginx -t

# Reload nginx
systemctl reload nginx

# Auto-renew certificates
certbot renew --dry-run
```

#### Update .env File

```bash
# Update CORS_ORIGINS in /opt/Entmoot/.env
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Restart backend to apply changes
cd /opt/Entmoot
docker compose restart backend
```

Now access: `https://yourdomain.com` 🎉

---

## 🔧 Common Tasks

### View Logs
```bash
cd /opt/Entmoot
docker compose logs -f
docker compose logs backend
docker compose logs frontend
```

### Restart Services
```bash
docker compose restart
docker compose restart backend  # Just backend
```

### Update Application
```bash
cd /opt/Entmoot
git pull
docker compose build
docker compose up -d
```

### Backup Database
```bash
# Create backup
docker compose exec postgres pg_dump -U entmoot entmoot > backup-$(date +%Y%m%d).sql

# Compress
gzip backup-*.sql

# Download to local machine
scp root@YOUR_SERVER_IP:/opt/Entmoot/backup-*.sql.gz ~/Downloads/
```

### Restore Database
```bash
# Upload backup to server
scp ~/Downloads/backup-20241111.sql.gz root@YOUR_SERVER_IP:/opt/Entmoot/

# Restore
cd /opt/Entmoot
gunzip backup-20241111.sql.gz
cat backup-20241111.sql | docker compose exec -T postgres psql -U entmoot entmoot
```

### Monitor Resources
```bash
# Check disk space
df -h

# Check memory
free -h

# Check Docker resource usage
docker stats

# Check logs size
du -sh /var/lib/docker/volumes/
```

---

## 🚨 Troubleshooting

### Services Won't Start
```bash
# Check logs
docker compose logs

# Check if ports are in use
netstat -tulpn | grep ':80\|:8000\|:5432\|:6379'

# Stop and restart
docker compose down
docker compose up -d
```

### Database Connection Issues
```bash
# Check postgres is running
docker compose ps postgres

# Test database connection
docker compose exec postgres psql -U entmoot -d entmoot -c "SELECT 1;"

# Reset database (⚠️ destroys data)
docker compose down -v
docker compose up -d
```

### Frontend Shows Blank Page
```bash
# Check frontend logs
docker compose logs frontend

# Check nginx configuration
docker compose exec frontend cat /etc/nginx/conf.d/default.conf

# Rebuild frontend
docker compose build frontend
docker compose up -d frontend
```

### Backend API Not Responding
```bash
# Check backend logs
docker compose logs backend

# Check environment variables
docker compose exec backend env | grep DATABASE

# Restart backend
docker compose restart backend

# Check health endpoint
curl http://localhost:8000/health
```

---

## 📊 Monitoring (Optional but Recommended)

### Set Up Uptime Monitoring
1. Create account at https://uptimerobot.com (free)
2. Add monitor for your domain
3. Set up email/Slack alerts

### Set Up Error Tracking
1. Create account at https://sentry.io (free tier)
2. Update .env with Sentry DSN:
   ```
   SENTRY_DSN=your_dsn_here
   ```
3. Restart backend: `docker compose restart backend`

---

## 💰 Cost Breakdown

### Monthly Costs (Minimal Setup)
- **Server (DigitalOcean):** $18/month
- **Domain Name:** $10-15/year (~$1/month)
- **SSL Certificate:** FREE (Let's Encrypt)
- **Total:** ~$19/month

### Monthly Costs (With Backups & Monitoring)
- **Server:** $18/month
- **Backups (DigitalOcean):** $3/month
- **Domain:** $1/month
- **Uptime Robot:** FREE
- **Sentry:** FREE (10k events/month)
- **Total:** ~$22/month

### Scaling Options
When you outgrow a single server:
- Add more server resources: $36-72/month
- Managed database: +$50-200/month
- CDN for frontend: +$10-50/month
- Load balancer: +$20/month

---

## 📚 Additional Resources

- **Full deployment guide:** `docs/deployment.md` (AWS/GCP/Azure)
- **Operations runbook:** `docs/operations.md`
- **Disaster recovery:** `docs/disaster-recovery.md`
- **Quick start:** `DEPLOY_QUICK_START.md`
- **Checklist:** `DEPLOYMENT_CHECKLIST.md`

---

## 🎓 Learning Path

If you're new to deployment:

1. **Start local** (Path A) - Get familiar with Docker
2. **Deploy to VPS** (Path B) - Learn server management
3. **Add HTTPS** (Path C) - Secure your application
4. **Set up monitoring** - Know when things break
5. **Learn AWS/GCP** (later) - When you need to scale

---

## ✅ Success Checklist

After deployment, verify:

- [ ] Frontend loads at your domain
- [ ] Can create a new project
- [ ] Can upload property data
- [ ] Map displays correctly
- [ ] Can place assets
- [ ] Can edit assets
- [ ] Violations detection works
- [ ] Can export results
- [ ] HTTPS works (if configured)
- [ ] Backups are running

---

## 🆘 Need Help?

1. Check logs: `docker compose logs`
2. Review troubleshooting section above
3. Check GitHub Issues
4. Contact support: [your-email]

---

## 🎉 You're Ready!

Choose your path and start deploying! The automated `deploy.sh` script makes it easy.

**Quick Start:**
```bash
./deploy.sh
```

Good luck! 🚀
