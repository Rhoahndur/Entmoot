# Deployment Checklist

Use this checklist before deploying Entmoot to production.

## Pre-Deployment

### Environment Configuration
- [ ] Copy `.env.example` to `.env`
- [ ] Generate strong random `SECRET_KEY` (32+ characters)
- [ ] Set secure `POSTGRES_PASSWORD`
- [ ] Set secure `REDIS_PASSWORD`
- [ ] Configure `CORS_ORIGINS` with production domains
- [ ] Set `ENVIRONMENT=production`
- [ ] Review `MAX_UPLOAD_SIZE` limit

### Infrastructure
- [ ] Docker 20.10+ installed
- [ ] Docker Compose v2.0+ installed
- [ ] Sufficient disk space (20GB+ recommended)
- [ ] Ports 80, 443, 8000 available
- [ ] Firewall configured
- [ ] SSL/TLS certificates ready (if using HTTPS)

### GitHub Secrets (for CI/CD)
- [ ] `DOCKER_USERNAME` configured
- [ ] `DOCKER_PASSWORD` configured
- [ ] `STAGING_HOST` configured
- [ ] `STAGING_USER` configured
- [ ] `STAGING_SSH_KEY` configured
- [ ] `PRODUCTION_HOST` configured
- [ ] `PRODUCTION_USER` configured
- [ ] `PRODUCTION_SSH_KEY` configured
- [ ] `SLACK_WEBHOOK` configured (optional)

## Deployment Steps

### 1. Build and Test Locally
```bash
# Build images
docker compose build

# Run tests
docker compose -f docker-compose.dev.yml run backend pytest

# Start services
docker compose up -d

# Verify health
curl http://localhost:8000/health
curl http://localhost/health
```

### 2. Push to Registry (Manual)
```bash
# Tag images
docker tag entmoot-backend:latest yourdockerhub/entmoot-backend:v1.0.0
docker tag entmoot-frontend:latest yourdockerhub/entmoot-frontend:v1.0.0

# Push to registry
docker push yourdockerhub/entmoot-backend:v1.0.0
docker push yourdockerhub/entmoot-frontend:v1.0.0
```

### 3. Deploy to Production
```bash
# On production server
cd /opt/entmoot
git pull origin main
cp .env.example .env
# Edit .env with production values

# Start services
docker compose pull
docker compose up -d

# Verify deployment
docker compose ps
docker compose logs -f
```

### 4. Post-Deployment Verification
- [ ] Backend health check: `curl https://api.yourdomain.com/health`
- [ ] Frontend accessible: `https://yourdomain.com`
- [ ] API documentation: `https://api.yourdomain.com/docs`
- [ ] Database connection working
- [ ] Redis connection working
- [ ] File uploads working
- [ ] All services show as "healthy" in `docker compose ps`

## Post-Deployment

### Monitoring
- [ ] Set up log monitoring
- [ ] Configure alerting
- [ ] Monitor resource usage
- [ ] Set up uptime monitoring
- [ ] Configure backup schedule

### Security
- [ ] Enable HTTPS with valid SSL certificate
- [ ] Configure rate limiting
- [ ] Set up fail2ban or similar
- [ ] Regular security updates scheduled
- [ ] Vulnerability scanning enabled
- [ ] Access logs reviewed

### Backup
- [ ] Database backup configured
- [ ] Volume backup configured
- [ ] Backup restoration tested
- [ ] Backup retention policy defined

### Documentation
- [ ] Document production URLs
- [ ] Document deployment procedures
- [ ] Document rollback procedures
- [ ] Update team documentation

## Rollback Procedure

If deployment fails:

```bash
# Stop current deployment
docker compose down

# Restore from backup
tar xzf backup-YYYYMMDD-HHMMSS.tar.gz

# Start previous version
docker compose up -d

# Verify rollback
curl http://localhost:8000/health
```

## Health Check Endpoints

- Backend: `/health` - Returns `{"status": "healthy"}`
- Frontend: `/health` - Returns `healthy`

## Support Contacts

- DevOps Team: [contact]
- On-Call: [contact]
- Emergency: [contact]

## Notes

- Always test in staging before production
- Keep backup before major changes
- Monitor logs during deployment
- Have rollback plan ready
- Communicate with team during deployment

## CI/CD Deployment

If using GitHub Actions:

1. Push to `develop` branch → Auto-deploy to staging
2. Create release tag → Auto-deploy to production
3. Monitor GitHub Actions for status
4. Check Slack for deployment notifications

