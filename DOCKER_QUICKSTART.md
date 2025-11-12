# Docker Quick Start Guide

## Prerequisites

- Docker 20.10+
- Docker Compose v2.0+

## Quick Start (5 Minutes)

### 1. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your preferred settings
# IMPORTANT: Change passwords in production!
nano .env
```

### 2. Start Services

```bash
# Production mode
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### 3. Access Application

- **Frontend**: http://localhost
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 4. Stop Services

```bash
# Stop and remove containers
docker compose down

# Stop and remove volumes (WARNING: deletes all data!)
docker compose down -v
```

## Development Mode

Development mode includes hot reload for both backend and frontend:

```bash
# Start development environment
docker compose -f docker-compose.dev.yml up

# Backend runs on: http://localhost:8000
# Frontend runs on: http://localhost:5173
# Code changes automatically reload
```

## Common Commands

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
```

### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart backend
```

### Execute Commands in Containers

```bash
# Backend shell
docker compose exec backend bash

# Run Python shell
docker compose exec backend python

# Run tests
docker compose exec backend pytest

# Frontend shell
docker compose exec frontend sh

# Database shell
docker compose exec postgres psql -U entmoot
```

### Check Service Health

```bash
# View service status
docker compose ps

# Check backend health
curl http://localhost:8000/health

# Check frontend health
curl http://localhost/health
```

### Rebuild Images

```bash
# Rebuild all images
docker compose build

# Rebuild specific service
docker compose build backend

# Rebuild without cache
docker compose build --no-cache
```

### Clean Up

```bash
# Remove stopped containers
docker compose rm

# Remove all containers and networks
docker compose down

# Remove everything including volumes
docker compose down -v

# Remove unused Docker resources
docker system prune -f
```

## Troubleshooting

### Port Already in Use

```bash
# Check what's using port 8000
lsof -i :8000

# Change port in .env file
BACKEND_PORT=8001
FRONTEND_PORT=8080
```

### Database Connection Issues

```bash
# Check postgres logs
docker compose logs postgres

# Verify database is healthy
docker compose exec postgres pg_isready -U entmoot

# Restart database
docker compose restart postgres
```

### Build Failures

```bash
# Clear build cache
docker compose build --no-cache

# Remove old images
docker image prune -a

# Check for system requirements
docker info
```

### Permission Issues

```bash
# Fix volume permissions (Linux)
sudo chown -R $USER:$USER data/

# Or run as root temporarily
docker compose exec -u root backend bash
```

### Logs Not Showing

```bash
# Follow logs in real-time
docker compose logs -f --tail=100

# Check specific service
docker compose logs backend | tail -n 50
```

## Environment Variables

Key variables in `.env`:

### Database
- `POSTGRES_DB`: Database name (default: entmoot)
- `POSTGRES_USER`: Database user (default: entmoot)
- `POSTGRES_PASSWORD`: **CHANGE IN PRODUCTION**
- `POSTGRES_PORT`: Port to expose (default: 5432)

### Redis
- `REDIS_PASSWORD`: **CHANGE IN PRODUCTION**
- `REDIS_PORT`: Port to expose (default: 6379)

### Application
- `ENVIRONMENT`: production or development
- `SECRET_KEY`: **GENERATE RANDOM STRING IN PRODUCTION**
- `MAX_UPLOAD_SIZE`: Max file upload size in bytes
- `CORS_ORIGINS`: Comma-separated list of allowed origins

### Ports
- `BACKEND_PORT`: Backend API port (default: 8000)
- `FRONTEND_PORT`: Frontend web server port (default: 80)

## Security Checklist

Before deploying to production:

- [ ] Change all default passwords in `.env`
- [ ] Generate strong `SECRET_KEY`
- [ ] Update `CORS_ORIGINS` with your domain
- [ ] Enable HTTPS (use reverse proxy)
- [ ] Set up firewall rules
- [ ] Enable Docker content trust
- [ ] Regular security updates
- [ ] Monitor logs for suspicious activity

## Production Deployment

### Using Docker Registry

```bash
# Build and tag
docker compose build
docker tag entmoot-backend:latest yourdockerhub/entmoot-backend:latest
docker tag entmoot-frontend:latest yourdockerhub/entmoot-frontend:latest

# Push to registry
docker push yourdockerhub/entmoot-backend:latest
docker push yourdockerhub/entmoot-frontend:latest

# Pull on production server
docker pull yourdockerhub/entmoot-backend:latest
docker pull yourdockerhub/entmoot-frontend:latest
docker compose up -d
```

### Using CI/CD

The project includes GitHub Actions workflows:
- Automatic builds on push
- Tests run before deployment
- Automated deployment to staging/production
- See `.github/workflows/` for details

## Performance Tuning

### Resource Limits

Add to `docker-compose.yml`:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          memory: 1G
```

### Scaling

```bash
# Run multiple backend instances
docker compose up -d --scale backend=3

# Requires load balancer configuration
```

## Backup and Restore

### Backup

```bash
# Backup database
docker compose exec postgres pg_dump -U entmoot entmoot > backup.sql

# Backup volumes
docker run --rm -v entmoot_postgres_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres_backup.tar.gz /data
```

### Restore

```bash
# Restore database
cat backup.sql | docker compose exec -T postgres psql -U entmoot entmoot

# Restore volumes
docker run --rm -v entmoot_postgres_data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/postgres_backup.tar.gz -C /
```

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Project README](README.md)
- [Full Completion Report](STORIES_6.5-6.6_COMPLETION.md)

## Getting Help

If you encounter issues:

1. Check logs: `docker compose logs -f`
2. Verify configuration: `docker compose config`
3. Check service health: `docker compose ps`
4. Review environment variables: `cat .env`
5. Check GitHub issues
6. Contact development team
