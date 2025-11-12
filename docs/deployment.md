# Production Deployment Guide

Entmoot - AI-Driven Site Layout Automation Platform

**Version:** 1.0
**Last Updated:** 2025-11-10
**Audience:** DevOps Engineers, Infrastructure Teams

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Infrastructure Setup](#infrastructure-setup)
4. [Configuration](#configuration)
5. [Deployment Process](#deployment-process)
6. [Database Migration](#database-migration)
7. [Scaling Configuration](#scaling-configuration)
8. [Backup and Restore](#backup-and-restore)
9. [Monitoring and Alerting](#monitoring-and-alerting)
10. [Cost Estimation](#cost-estimation)
11. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### AWS, GCP, or Azure Account

Choose your cloud provider based on organizational requirements:

#### AWS
- AWS Account with appropriate IAM permissions
- VPC with public/private subnets
- S3 bucket for artifacts and backups
- RDS PostgreSQL with PostGIS extension available
- ElastiCache Redis cluster support
- Application Load Balancer (ALB) or Network Load Balancer (NLB)
- Certificate from AWS Certificate Manager (ACM)

#### GCP
- GCP Project with billing enabled
- Cloud VPC network
- Cloud Storage bucket
- Cloud SQL with PostgreSQL and PostGIS
- Cloud Memorystore for Redis
- Cloud Load Balancing
- Google Managed Certificates

#### Azure
- Azure Subscription with appropriate RBAC permissions
- Virtual Network with subnets
- Storage Account for blobs
- Azure Database for PostgreSQL with PostGIS
- Azure Cache for Redis
- Application Gateway or Load Balancer
- Key Vault for secrets
- Managed certificates or custom certificates

### Local Requirements

```bash
# Minimum versions
- Docker Engine 20.10+
- Docker Compose 2.0+ (for local testing)
- Terraform 1.0+ (if using IaC)
- kubectl 1.24+ (if using Kubernetes)
- AWS CLI 2.0+ / gcloud CLI / Azure CLI
- git 2.30+
```

### Domain and SSL

- Registered domain name
- SSL certificate (can be provisioned via cloud provider)
- DNS zone configured for your domain

---

## Architecture Overview

### Production Environment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Client Layer (Internet)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Load Balancer (ALB/NLB/Application Gateway)         │
│              - SSL/TLS Termination                               │
│              - Health Checks                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
        ┌──────────────────┐   ┌──────────────────┐
        │  Frontend (React)│   │   API Gateway    │
        │  Static Hosting  │   │   (FastAPI)      │
        │  - S3/GCS/Blob   │   │   Container      │
        │  - CDN           │   │   - Auto-scaling │
        └──────────────────┘   └──────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
        ┌─────────────────────┐          ┌──────────────────────┐
        │  Application Layer  │          │  Cache Layer         │
        │  - Core Processing  │          │  - Redis Cluster     │
        │  - Optimization     │          │  - Session Cache     │
        │  - Auto-scaling     │          │  - Query Cache       │
        └─────────────────────┘          └──────────────────────┘
                    │                              │
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────┐
                    │  Data Storage Layer      │
                    ├──────────────────────────┤
                    │  PostGIS Database        │
                    │  - Read Replicas         │
                    │  - Automated Backup      │
                    │  - Multi-AZ              │
                    └──────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
        ┌──────────────────────┐    ┌──────────────────────┐
        │  Object Storage      │    │  Backup Storage      │
        │  - S3/GCS/Blob       │    │  - Cross-region      │
        │  - File uploads      │    │  - Point-in-time     │
        │  - Exports           │    │  - Disaster recovery │
        └──────────────────────┘    └──────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              Observability & Management Layer                     │
│  - Prometheus + Grafana (Monitoring)                             │
│  - CloudWatch/GCP Operations/Azure Monitor (Logs)                │
│  - Sentry (Error Tracking)                                       │
│  - CloudTrail/Cloud Logging/Audit Logs                           │
└─────────────────────────────────────────────────────────────────┘
```

### Component Specifications

| Component | Purpose | Min Instances | Recommended | Max |
|-----------|---------|---------------|-------------|-----|
| API Gateway | Handle HTTP requests | 2 | 3-5 | 20 |
| Worker/Optimizer | Process optimizations | 1 | 2-4 | 10 |
| Database (Primary) | Data persistence | 1 | 1 (Multi-AZ) | - |
| Database (Replica) | Read scaling | 0 | 1-2 | 3 |
| Redis | Caching/Sessions | 1 | Cluster (3+) | - |
| Load Balancer | Traffic distribution | 1 | 1 (Multi-AZ) | - |

---

## Infrastructure Setup

### Option 1: AWS Deployment

#### 1.1 VPC and Networking

```bash
# Create VPC
aws ec2 create-vpc --cidr-block 10.0.0.0/16 --region us-east-1

# Create public subnets
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.1.0/24 \
  --availability-zone us-east-1a --region us-east-1

aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.2.0/24 \
  --availability-zone us-east-1b --region us-east-1

# Create private subnets
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.10.0/24 \
  --availability-zone us-east-1a --region us-east-1

aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.11.0/24 \
  --availability-zone us-east-1b --region us-east-1

# Create Internet Gateway
aws ec2 create-internet-gateway --region us-east-1
aws ec2 attach-internet-gateway --vpc-id vpc-xxx --internet-gateway-id igw-xxx
```

#### 1.2 Security Groups

**API Security Group:**
```bash
# Allow HTTPS from internet
aws ec2 authorize-security-group-ingress --group-id sg-api \
  --protocol tcp --port 443 --cidr 0.0.0.0/0

# Allow HTTP redirect
aws ec2 authorize-security-group-ingress --group-id sg-api \
  --protocol tcp --port 80 --cidr 0.0.0.0/0

# Allow from ALB
aws ec2 authorize-security-group-ingress --group-id sg-api \
  --protocol tcp --port 8000 --source-group sg-alb
```

**Database Security Group:**
```bash
# Allow PostgreSQL from API
aws ec2 authorize-security-group-ingress --group-id sg-db \
  --protocol tcp --port 5432 --source-group sg-api
```

**Redis Security Group:**
```bash
# Allow Redis from API
aws ec2 authorize-security-group-ingress --group-id sg-redis \
  --protocol tcp --port 6379 --source-group sg-api
```

#### 1.3 RDS PostgreSQL with PostGIS

```bash
# Create DB subnet group
aws rds create-db-subnet-group \
  --db-subnet-group-name entmoot-db-subnet \
  --db-subnet-group-description "Entmoot database subnet" \
  --subnet-ids subnet-public-1 subnet-public-2

# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier entmoot-prod \
  --db-instance-class db.r6i.xlarge \
  --engine postgres \
  --engine-version 16.1 \
  --master-username postgres \
  --master-user-password "$(openssl rand -base64 32)" \
  --allocated-storage 100 \
  --storage-type gp3 \
  --storage-encrypted \
  --multi-az \
  --vpc-security-group-ids sg-db \
  --db-subnet-group-name entmoot-db-subnet \
  --backup-retention-period 30 \
  --backup-window "03:00-04:00" \
  --maintenance-window "sun:04:00-sun:05:00" \
  --enable-cloudwatch-logs-exports postgresql \
  --enable-iam-database-authentication

# Enable PostGIS extension (connect to DB and run):
# CREATE EXTENSION postgis;
# CREATE EXTENSION postgis_topology;
# CREATE EXTENSION fuzzystrmatch;
```

**RDS Configuration Parameters:**

```ini
# Parameter Group: entmoot-prod-pg
shared_buffers = 262144              # 25% of instance memory
effective_cache_size = 1048576       # 75% of instance memory
maintenance_work_mem = 65536         # 25% of instance memory
work_mem = 16384                     # shared_buffers / max_connections / 4
max_worker_processes = 8
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
random_page_cost = 1.1               # For SSD storage
effective_io_concurrency = 200       # For gp3 storage
synchronous_commit = on              # For data safety
wal_level = logical                  # For replication
max_wal_senders = 10
wal_keep_size = 10240                # 10GB
max_replication_slots = 10
log_min_duration_statement = 1000     # Log slow queries
log_statement = 'ddl'
log_connections = on
log_disconnections = on
```

#### 1.4 ElastiCache Redis

```bash
# Create Redis subnet group
aws elasticache create-cache-subnet-group \
  --cache-subnet-group-name entmoot-redis-subnet \
  --cache-subnet-group-description "Entmoot Redis subnet" \
  --subnet-ids subnet-private-1 subnet-private-2

# Create Redis cluster (recommended for production)
aws elasticache create-replication-group \
  --replication-group-description "Entmoot production Redis" \
  --replication-group-id entmoot-redis-prod \
  --engine redis \
  --cache-node-type cache.r7g.xlarge \
  --engine-version 7.0 \
  --num-cache-clusters 3 \
  --automatic-failover-enabled \
  --cache-subnet-group-name entmoot-redis-subnet \
  --security-group-ids sg-redis \
  --at-rest-encryption-enabled \
  --transit-encryption-enabled \
  --auth-token "$(openssl rand -base64 32)" \
  --snapshot-retention-limit 5 \
  --snapshot-window "03:00-05:00" \
  --maintenance-window "sun:05:00-sun:07:00"
```

#### 1.5 S3 Bucket for Files and Backups

```bash
# Create S3 bucket
aws s3api create-bucket \
  --bucket entmoot-prod-files \
  --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket entmoot-prod-files \
  --versioning-configuration Status=Enabled

# Enable server-side encryption
aws s3api put-bucket-encryption \
  --bucket entmoot-prod-files \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Block public access
aws s3api put-public-access-block \
  --bucket entmoot-prod-files \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Create lifecycle policy (delete old uploads after 7 days, archive old exports after 30 days)
aws s3api put-bucket-lifecycle-configuration \
  --bucket entmoot-prod-files \
  --lifecycle-configuration file://s3-lifecycle.json
```

**s3-lifecycle.json:**
```json
{
  "Rules": [
    {
      "Id": "DeleteTempUploads",
      "Prefix": "uploads/temp/",
      "Status": "Enabled",
      "Expiration": {
        "Days": 7
      }
    },
    {
      "Id": "ArchiveExports",
      "Prefix": "exports/",
      "Status": "Enabled",
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 365
      }
    }
  ]
}
```

#### 1.6 Load Balancer and SSL

```bash
# Create Application Load Balancer
aws elbv2 create-load-balancer \
  --name entmoot-alb-prod \
  --subnets subnet-public-1 subnet-public-2 \
  --security-groups sg-alb \
  --scheme internet-facing \
  --type application

# Create target group for API
aws elbv2 create-target-group \
  --name entmoot-api-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxx \
  --health-check-enabled \
  --health-check-protocol HTTP \
  --health-check-path "/health" \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 5 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3

# Request SSL certificate
aws acm request-certificate \
  --domain-name yourdomain.com \
  --subject-alternative-names "*.yourdomain.com" \
  --validation-method DNS \
  --region us-east-1

# Create HTTPS listener (after certificate is validated)
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:... \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=arn:aws:acm:... \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:...

# Create HTTP redirect listener
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:... \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=redirect,RedirectConfig="{Protocol=HTTPS,Port=443,StatusCode=HTTP_301}"
```

#### 1.7 ECS Cluster for Container Orchestration

```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name entmoot-prod

# Create CloudWatch log group
aws logs create-log-group --log-group-name /ecs/entmoot-prod

# Register task definition (see section 3.4)
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Create ECS service for API
aws ecs create-service \
  --cluster entmoot-prod \
  --service-name entmoot-api \
  --task-definition entmoot-api:1 \
  --desired-count 3 \
  --launch-type EC2 \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=api,containerPort=8000 \
  --deployment-configuration maximumPercent=200,minimumHealthyPercent=100

# Create autoscaling
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/entmoot-prod/entmoot-api \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 3 \
  --max-capacity 20

# Create scaling policy (CPU-based)
aws application-autoscaling put-scaling-policy \
  --policy-name entmoot-api-cpu-scaling \
  --service-namespace ecs \
  --resource-id service/entmoot-prod/entmoot-api \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file://scaling-policy.json
```

**scaling-policy.json:**
```json
{
  "TargetValue": 70.0,
  "PredefinedMetricSpecification": {
    "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
  },
  "ScaleOutCooldown": 300,
  "ScaleInCooldown": 600
}
```

### Option 2: GCP Deployment

#### 2.1 VPC and Networking

```bash
# Create VPC
gcloud compute networks create entmoot-vpc --subnet-mode=custom

# Create subnets
gcloud compute networks subnets create entmoot-public \
  --network=entmoot-vpc \
  --region=us-central1 \
  --range=10.0.1.0/24

gcloud compute networks subnets create entmoot-private \
  --network=entmoot-vpc \
  --region=us-central1 \
  --range=10.0.10.0/24 \
  --secondary-range pods=10.4.0.0/14,services=10.0.16.0/20
```

#### 2.2 Cloud SQL PostgreSQL with PostGIS

```bash
# Create Cloud SQL instance
gcloud sql instances create entmoot-prod \
  --database-version=POSTGRES_16 \
  --tier=db-custom-4-16384 \
  --region=us-central1 \
  --network=projects/PROJECT_ID/global/networks/entmoot-vpc \
  --availability-type=REGIONAL \
  --backup-start-time=03:00 \
  --retained-backups-count=30 \
  --retained-transaction-log-days=7 \
  --enable-bin-log=false

# Create database
gcloud sql databases create entmoot --instance=entmoot-prod

# Create user
gcloud sql users create entmoot \
  --instance=entmoot-prod \
  --password='[SECURE_PASSWORD]'

# Connect and enable PostGIS
gcloud sql connect entmoot-prod --user=postgres
# psql> CREATE EXTENSION postgis;
# psql> CREATE EXTENSION postgis_topology;
# psql> GRANT USAGE ON SCHEMA public TO entmoot;
# psql> GRANT CREATE ON DATABASE entmoot TO entmoot;
```

#### 2.3 Cloud Memorystore Redis

```bash
# Create Redis instance
gcloud redis instances create entmoot-prod \
  --size=8 \
  --region=us-central1 \
  --redis-version=7.0 \
  --network=projects/PROJECT_ID/global/networks/entmoot-vpc \
  --redis-config maxmemory-policy=allkeys-lru \
  --transit-encryption-mode=SERVER_AUTHENTICATION
```

#### 2.4 Cloud Storage Buckets

```bash
# Create bucket for files
gsutil mb -l us-central1 -c STANDARD gs://entmoot-prod-files

# Enable versioning
gsutil versioning set on gs://entmoot-prod-files

# Set lifecycle policy
echo '{"lifecycle": {"rule": [{"action": {"type": "Delete"}, "condition": {"age": 7, "matchesPrefix": ["uploads/temp/"]}}]}}' > lifecycle.json
gsutil lifecycle set lifecycle.json gs://entmoot-prod-files
```

#### 2.5 Cloud Run for API

```bash
# Build and push image to Artifact Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/entmoot-api:1.0.0 .

# Deploy to Cloud Run
gcloud run deploy entmoot-api \
  --image=gcr.io/PROJECT_ID/entmoot-api:1.0.0 \
  --platform=managed \
  --region=us-central1 \
  --memory=4Gi \
  --cpu=2 \
  --timeout=3600 \
  --max-instances=100 \
  --min-instances=3 \
  --vpc-connector=entmoot-vpc-connector \
  --set-env-vars=DATABASE_URL=cloudsql://...,REDIS_URL=rediss://...
```

#### 2.6 Cloud Load Balancing with SSL

```bash
# Create health check
gcloud compute health-checks create https entmoot-health-check \
  --request-path=/health \
  --port=443

# Create backend service
gcloud compute backend-services create entmoot-backend \
  --protocol=HTTPS \
  --health-checks=entmoot-health-check \
  --load-balancing-scheme=EXTERNAL \
  --global

# Create URL map
gcloud compute url-maps create entmoot-lb \
  --default-service=entmoot-backend

# Create SSL certificate
gcloud compute ssl-certificates create entmoot-cert \
  --certificate=path/to/cert.crt \
  --private-key=path/to/key.key

# Create HTTPS proxy
gcloud compute target-https-proxies create entmoot-proxy \
  --ssl-certificates=entmoot-cert \
  --url-map=entmoot-lb

# Create forwarding rule
gcloud compute forwarding-rules create entmoot-https \
  --global \
  --target-https-proxy=entmoot-proxy \
  --address=entmoot-ip \
  --ports=443
```

### Option 3: Azure Deployment

#### 3.1 Resource Group and VNet

```bash
# Create resource group
az group create \
  --name entmoot-prod \
  --location eastus

# Create VNet
az network vnet create \
  --resource-group entmoot-prod \
  --name entmoot-vnet \
  --address-prefix 10.0.0.0/16

# Create subnets
az network vnet subnet create \
  --resource-group entmoot-prod \
  --vnet-name entmoot-vnet \
  --name app-subnet \
  --address-prefix 10.0.1.0/24

az network vnet subnet create \
  --resource-group entmoot-prod \
  --vnet-name entmoot-vnet \
  --name db-subnet \
  --address-prefix 10.0.10.0/24
```

#### 3.2 Azure Database for PostgreSQL

```bash
# Create PostgreSQL server
az postgres flexible-server create \
  --resource-group entmoot-prod \
  --name entmoot-db \
  --location eastus \
  --admin-user postgres \
  --admin-password '[SECURE_PASSWORD]' \
  --sku-name Standard_B4ms \
  --storage-size 102400 \
  --tier GeneralPurpose \
  --public-access Disabled \
  --vnet entmoot-vnet \
  --subnet db-subnet

# Create database
az postgres flexible-server db create \
  --resource-group entmoot-prod \
  --server-name entmoot-db \
  --database-name entmoot

# Enable PostGIS
az postgres flexible-server parameter set \
  --resource-group entmoot-prod \
  --server-name entmoot-db \
  --name shared_preload_libraries \
  --value postgis
```

#### 3.3 Azure Cache for Redis

```bash
# Create Redis cache
az redis create \
  --resource-group entmoot-prod \
  --name entmoot-redis \
  --location eastus \
  --sku Premium \
  --vm-size p1 \
  --enable-non-ssl-port false \
  --minimum-tls-version 1.2
```

#### 3.4 Storage Account

```bash
# Create storage account
az storage account create \
  --resource-group entmoot-prod \
  --name entmootprodfiles \
  --location eastus \
  --sku Standard_LRS \
  --https-only true

# Create blob container
az storage container create \
  --account-name entmootprodfiles \
  --name files
```

#### 3.5 Application Gateway with SSL

```bash
# Create public IP
az network public-ip create \
  --resource-group entmoot-prod \
  --name entmoot-pip \
  --allocation-method Static

# Create Application Gateway
az network application-gateway create \
  --resource-group entmoot-prod \
  --name entmoot-appgw \
  --location eastus \
  --vnet-name entmoot-vnet \
  --subnet app-subnet \
  --capacity 2 \
  --sku Standard_v2 \
  --public-ip-address entmoot-pip \
  --cert-file /path/to/cert.pfx \
  --cert-password '[PASSWORD]' \
  --http-settings-cookie-based-affinity Disabled
```

---

## Configuration

### Environment Variables

See `.env.production.example` and `.env.staging.example` for comprehensive templates.

#### Critical Variables for All Environments

```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/entmoot
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600

# Cache
REDIS_URL=redis://:[password]@host:6379/0
REDIS_SSL_CERTFILE=/path/to/cert.pem
REDIS_SESSION_EXPIRY=86400

# AWS / GCP / Azure Storage
STORAGE_PROVIDER=aws|gcp|azure
AWS_ACCESS_KEY_ID=[if using AWS]
AWS_SECRET_ACCESS_KEY=[if using AWS]
AWS_REGION=us-east-1
AWS_S3_BUCKET=entmoot-prod-files
AWS_S3_UPLOAD_PREFIX=uploads/
AWS_S3_EXPORT_PREFIX=exports/

# OR GCP
GCP_PROJECT_ID=[if using GCP]
GCP_CREDENTIALS_PATH=/path/to/credentials.json
GCP_BUCKET_NAME=entmoot-prod-files

# OR Azure
AZURE_STORAGE_ACCOUNT_NAME=[if using Azure]
AZURE_STORAGE_ACCOUNT_KEY=[if using Azure]
AZURE_CONTAINER_NAME=files

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
UVICORN_WORKERS=4

# Security
SECRET_KEY=[generate with: openssl rand -base64 32]
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
CORS_ENABLED=true

# Monitoring & Observability
LOG_LEVEL=INFO
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090
SENTRY_DSN=[if using Sentry]
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

# Feature Flags
ENABLE_OPTIMIZATION=true
ENABLE_GEOSPATIAL_ANALYSIS=true
OPTIMIZATION_TIMEOUT=3600
MAX_FILE_SIZE_MB=500
MAX_CONCURRENT_JOBS=10

# Email (optional)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=[SendGrid API key]
EMAIL_FROM=noreply@yourdomain.com
```

### Managing Secrets

**AWS Secrets Manager:**
```bash
# Store database password
aws secretsmanager create-secret \
  --name entmoot/prod/db-password \
  --secret-string '[SECURE_PASSWORD]'

# Store Redis auth token
aws secretsmanager create-secret \
  --name entmoot/prod/redis-token \
  --secret-string '[REDIS_AUTH_TOKEN]'

# Reference in IAM role
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:entmoot/prod/*"
    }
  ]
}
```

**GCP Secret Manager:**
```bash
# Create secrets
echo -n '[SECURE_PASSWORD]' | gcloud secrets create entmoot-db-password --data-file=-

# Grant access
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member=serviceAccount:entmoot@PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

**Azure Key Vault:**
```bash
# Create Key Vault
az keyvault create \
  --resource-group entmoot-prod \
  --name entmoot-kv

# Store secrets
az keyvault secret set \
  --vault-name entmoot-kv \
  --name DBPassword \
  --value '[SECURE_PASSWORD]'
```

---

## Deployment Process

### Step 1: Pre-Deployment Checklist

- [ ] Infrastructure created and tested
- [ ] Database created with PostGIS extension
- [ ] Redis cluster operational
- [ ] S3/GCS/Blob storage bucket created
- [ ] Load balancer and SSL certificates configured
- [ ] Security groups/firewall rules configured
- [ ] Monitoring and logging configured
- [ ] Backup strategy implemented
- [ ] Disaster recovery plan tested
- [ ] All environment variables set in secrets manager
- [ ] Database migrations prepared
- [ ] Docker images built and pushed to registry

### Step 2: Database Initialization

```bash
# Apply migrations (detailed in next section)
./scripts/migrate.sh production

# Verify schema
psql -h your-db.rds.amazonaws.com -U postgres -d entmoot -c "\dt"

# Create indices for performance
psql -h your-db.rds.amazonaws.com -U postgres -d entmoot < scripts/create-indices.sql
```

### Step 3: Deploy Application

**Using AWS ECS:**
```bash
# Update task definition
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Update service
aws ecs update-service \
  --cluster entmoot-prod \
  --service entmoot-api \
  --task-definition entmoot-api:NEW_REVISION \
  --force-new-deployment
```

**Using GCP Cloud Run:**
```bash
# Deploy new version
gcloud run deploy entmoot-api \
  --image=gcr.io/PROJECT_ID/entmoot-api:1.0.1 \
  --region=us-central1 \
  --traffic=LATEST=100
```

**Using Azure Container Instances/App Service:**
```bash
# Update image in App Service
az webapp deployment container config \
  --resource-group entmoot-prod \
  --name entmoot-api \
  --enable-continuous-deployment true

# Or update image tag
az container app update \
  --resource-group entmoot-prod \
  --name entmoot-api \
  --image gcr.io/PROJECT_ID/entmoot-api:1.0.1
```

### Step 4: Verify Deployment

```bash
# Check health endpoint
curl -H "Authorization: Bearer [YOUR_TOKEN]" \
  https://api.yourdomain.com/health

# Expected response:
# {"status": "healthy", "version": "0.1.0", "timestamp": "2025-11-10T00:00:00Z"}

# Check logs
# AWS: aws logs tail /ecs/entmoot-prod --follow
# GCP: gcloud logging read "resource.type=cloud_run_revision" --limit 50 --format json
# Azure: az container logs --resource-group entmoot-prod --name entmoot-api

# Run smoke tests
pytest tests/integration/test_health.py
```

### Step 5: Monitoring and Alerts

- Monitor API response times (target: <500ms p95)
- Monitor CPU usage (target: <70%)
- Monitor memory usage (target: <80%)
- Monitor database connections (target: <80% of pool)
- Monitor error rate (target: <0.1%)
- Monitor Redis hit rate (target: >80%)

---

## Database Migration

### Pre-Migration Checklist

1. Backup production database
2. Test migrations on staging
3. Prepare rollback procedure
4. Schedule during maintenance window
5. Notify stakeholders
6. Ensure monitoring is active

### Running Migrations

**Alembic Setup (Python):**

```bash
# Create migration
alembic revision --autogenerate -m "Add new feature"

# Review migration file
cat alembic/versions/XXX_add_new_feature.py

# Apply migration
alembic upgrade head

# Verify
alembic current
```

**Migration Script:**
```bash
#!/bin/bash
# scripts/migrate.sh

set -e

ENV=${1:-staging}
DB_HOST=${2:-localhost}

echo "Running migrations for $ENV environment..."

if [ "$ENV" = "production" ]; then
  echo "Creating backup..."
  pg_dump -h "$DB_HOST" -U postgres entmoot > \
    "backups/entmoot_$(date +%Y%m%d_%H%M%S).sql"
fi

echo "Applying migrations..."
alembic upgrade head

echo "Verifying schema..."
psql -h "$DB_HOST" -U postgres -d entmoot -c "\d"

echo "Done!"
```

### Zero-Downtime Migrations

For large tables, use strategies to minimize blocking:

```sql
-- Add column without default (non-blocking)
ALTER TABLE buildings ADD COLUMN new_field TEXT;

-- Backfill in batches
UPDATE buildings SET new_field = 'default'
WHERE id IN (SELECT id FROM buildings LIMIT 10000);

-- Add constraint after data is populated
ALTER TABLE buildings ADD CONSTRAINT check_new_field
  CHECK (new_field IS NOT NULL);
```

### Rollback Procedure

```bash
# Downgrade to previous version
alembic downgrade -1

# Or specific version
alembic downgrade <target_revision>

# Restore from backup if needed
pg_restore -h "$DB_HOST" -U postgres -d entmoot < backups/latest.sql
```

---

## Scaling Configuration

### Horizontal Scaling

**API Servers:**

```yaml
# ECS Auto Scaling Policy
minCapacity: 3
maxCapacity: 20
targetTrackingScalingPolicies:
  - name: cpu-scaling
    targetValue: 70.0
    cooldown: 300s (scale-out) / 600s (scale-in)

  - name: memory-scaling
    targetValue: 80.0
    cooldown: 300s (scale-out) / 600s (scale-in)

  - name: request-count
    targetValue: 1000
    cooldown: 300s (scale-out) / 600s (scale-in)
```

**Database:**

```
Primary (Multi-AZ): Single write node, synchronous replication to standby
Read Replicas: 1-2 for read-heavy workloads

Connection pooling:
- PgBouncer: 50 connections per API instance
- RDS Proxy (AWS): 200 connection limit per user
```

**Redis:**

```
Cluster mode enabled:
- 3-node cluster for HA
- Each node: cache.r7g.xlarge (8 vCPU, 64GB RAM)
- Eviction policy: allkeys-lru
```

### Vertical Scaling

**Database Instance Types:**

| Environment | Instance Type | CPU | Memory | Storage |
|-------------|---------------|-----|--------|---------|
| Staging | db.t3.medium | 1 vCPU | 1 GB | 20 GB |
| Production | db.r6i.2xlarge | 8 vCPU | 64 GB | 500 GB |
| High-traffic | db.r7i.4xlarge | 16 vCPU | 128 GB | 1000 GB |

**API Instance Types:**

| Environment | Instance Type | CPU | Memory | Storage |
|-------------|---------------|-----|--------|---------|
| Staging | t3.medium | 1 vCPU | 1 GB | 20 GB |
| Production | t3.large | 2 vCPU | 8 GB | 50 GB |
| Optimization job | c5.2xlarge | 8 vCPU | 16 GB | 100 GB |

---

## Backup and Restore

### Automated Backups

**AWS RDS:**
```
- Retention period: 30 days
- Backup window: 03:00-04:00 UTC
- Automated backups stored in S3
- Encrypted with KMS
```

**GCP Cloud SQL:**
```
- Automated backups: Daily
- Retention: 30 days
- On-demand backups: Before major changes
- Point-in-time recovery: 35 days
```

**Azure Database for PostgreSQL:**
```
- Automated backups: Every 5 minutes
- Retention: 35 days
- Geo-redundant backup: Enabled
- Point-in-time restore: Available
```

### Manual Backup Procedure

```bash
#!/bin/bash
# scripts/backup-database.sh

DB_HOST=${1:-your-db.rds.amazonaws.com}
DB_NAME=entmoot
BACKUP_DIR=backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/entmoot_${TIMESTAMP}.sql"

mkdir -p "$BACKUP_DIR"

# Backup database
pg_dump \
  -h "$DB_HOST" \
  -U postgres \
  -d "$DB_NAME" \
  --no-password \
  --format=custom \
  --compress=9 \
  -f "$BACKUP_FILE"

# Upload to S3
aws s3 cp "$BACKUP_FILE" s3://entmoot-prod-backups/

# Keep local copy for 7 days
find "$BACKUP_DIR" -name "*.sql" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE"
```

### Restore Procedure

**Full Restore:**
```bash
#!/bin/bash
# scripts/restore-database.sh

BACKUP_FILE=$1
DB_HOST=${2:-your-db.rds.amazonaws.com}
DB_NAME=entmoot

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: ./restore-database.sh <backup_file> [db_host]"
  exit 1
fi

# Create empty database
psql -h "$DB_HOST" -U postgres -c "CREATE DATABASE entmoot_restore;"

# Restore backup
pg_restore \
  -h "$DB_HOST" \
  -U postgres \
  -d entmoot_restore \
  --no-password \
  "$BACKUP_FILE"

# Verify restore
psql -h "$DB_HOST" -U postgres -d entmoot_restore -c "SELECT COUNT(*) FROM buildings;"

echo "Restore completed. Verify with: psql -h $DB_HOST -U postgres -d entmoot_restore"
```

**Point-in-Time Recovery (PITR):**

AWS RDS:
```bash
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier entmoot-prod \
  --target-db-instance-identifier entmoot-prod-pitr \
  --restore-time "2025-11-10T12:30:00Z"
```

GCP Cloud SQL:
```bash
gcloud sql backups restore BACKUP_ID \
  --backup-instance=entmoot-prod
```

Azure:
```bash
az postgres flexible-server restore \
  --resource-group entmoot-prod \
  --name entmoot-db-restore \
  --source-server entmoot-db \
  --restore-point-in-time "2025-11-10T12:30:00Z"
```

### Cross-Region Backup

**AWS:**
```bash
# Enable cross-region backup
aws rds create-db-instance-read-replica \
  --db-instance-identifier entmoot-prod-replica \
  --source-db-instance-identifier entmoot-prod \
  --source-region us-east-1 \
  --region us-west-2 \
  --availability-zone us-west-2a

# Promote replica to standalone instance (if needed)
aws rds promote-read-replica \
  --db-instance-identifier entmoot-prod-replica
```

---

## Monitoring and Alerting

### Key Metrics to Monitor

**API Metrics:**
- Request rate (requests/sec)
- Response time (p50, p95, p99)
- Error rate (5xx errors)
- HTTP status code distribution
- Endpoint-specific latency

**Database Metrics:**
- Connection count and pool utilization
- Query latency (slow queries)
- Replication lag (if applicable)
- Disk space usage
- IOPS and throughput
- Lock contention
- Cache hit rate

**Infrastructure Metrics:**
- CPU utilization (target: <70%)
- Memory utilization (target: <80%)
- Disk I/O
- Network bandwidth
- Cost (track daily)

**Application Metrics:**
- Active jobs
- Queue depth
- Cache hit rate (target: >80%)
- Optimization success rate

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - localhost:9093

rule_files:
  - 'alerts.yml'

scrape_configs:
  - job_name: 'entmoot-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']
```

**alerts.yml:**
```yaml
groups:
  - name: entmoot_alerts
    interval: 30s
    rules:
      - alert: HighAPIErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.001
        for: 5m
        annotations:
          summary: "High API error rate detected"
          description: "Error rate is {{ $value }} errors/sec"

      - alert: HighDatabaseConnections
        expr: pg_stat_activity_count > 80
        for: 5m
        annotations:
          summary: "High database connection count"
          description: "Currently {{ $value }} connections"

      - alert: LowCacheHitRate
        expr: redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total) < 0.8
        for: 10m
        annotations:
          summary: "Low Redis cache hit rate"

      - alert: DiskSpaceLow
        expr: node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.1
        for: 5m
        annotations:
          summary: "Low disk space"
          description: "Only {{ humanize $value }}% free"
```

### CloudWatch Alarms (AWS)

```bash
# High API error rate
aws cloudwatch put-metric-alarm \
  --alarm-name entmoot-api-errors \
  --alarm-description "API error rate exceeds threshold" \
  --metric-name RequestCount \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold

# High CPU utilization
aws cloudwatch put-metric-alarm \
  --alarm-name entmoot-api-cpu \
  --alarm-description "API CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold
```

### Grafana Dashboards

Key dashboards to create:

1. **API Dashboard**
   - Request rate
   - Response time (p50, p95, p99)
   - Error rate by endpoint
   - Status code distribution

2. **Database Dashboard**
   - Connections (active/idle)
   - Query latency
   - Replication lag
   - Cache hit rate
   - Slow queries

3. **Infrastructure Dashboard**
   - CPU/Memory/Disk usage
   - Network I/O
   - Cost breakdown

4. **Business Dashboard**
   - Active projects
   - Jobs completed
   - Average processing time

### Log Aggregation (ELK Stack)

**Filebeat configuration:**
```yaml
filebeat.inputs:
  - type: container
    enabled: true
    paths:
      - '/var/lib/docker/containers/*/*.log'

output.elasticsearch:
  hosts: ["elasticsearch:9200"]

processors:
  - add_docker_metadata:
  - add_kubernetes_metadata:
```

**Log retention policy:**
```yaml
# Index Lifecycle Management (ILM)
- Hot phase: First 7 days (write)
- Warm phase: 7-30 days (read)
- Cold phase: 30-365 days (archive)
- Delete: After 365 days
```

---

## Cost Estimation

### AWS Cost Breakdown (Monthly)

| Service | Instance Type | Cost/Month | Notes |
|---------|---------------|-----------|-------|
| RDS PostgreSQL | db.r6i.xlarge (Multi-AZ) | $1,200 | 100GB storage, 30-day backups |
| ElastiCache Redis | cache.r7g.xlarge (3-node) | $900 | Cluster mode, encryption |
| ECS (API) | t3.large x 3-5 (avg) | $200-300 | Auto-scaling, on-demand |
| ALB | Standard ALB | $150 | LCU charges included |
| S3 | Variable | $100-500 | Storage + data transfer |
| CloudWatch | Variable | $50-200 | Logs + metrics |
| Data Transfer | Variable | $100-500 | Inter-AZ + egress |
| **Total** | | **$2,700-4,250** | **Conservative estimate** |

**Cost optimization tips:**
- Use Reserved Instances for 1-3 years (30-70% discount)
- Use Spot Instances for batch jobs (70% discount)
- Enable S3 Intelligent-Tiering
- Use RDS Savings Plans

### GCP Cost Breakdown (Monthly)

| Service | Configuration | Cost/Month | Notes |
|---------|---------------|-----------|-------|
| Cloud SQL | db-custom-4-16384 (Regional) | $1,000 | 100GB storage, 30-day backups |
| Cloud Memorystore | redis-7.0 (8GB) | $400 | High availability |
| Cloud Run | 2 vCPU, 4GB RAM (avg 3 instances) | $250 | Memory-optimized |
| Cloud Storage | Standard bucket | $100-400 | Lifecycle policies applied |
| Cloud Load Balancing | HTTP(S) | $25 | Per month (no per-request charges) |
| Cloud Monitoring | Logs + metrics | $50-150 | Depends on log volume |
| **Total** | | **$1,825-2,225** | **Conservative estimate** |

### Azure Cost Breakdown (Monthly)

| Service | Configuration | Cost/Month | Notes |
|---------|---------------|-----------|-------|
| Database for PostgreSQL | Standard_D4s_v3 | $800 | 100GB storage |
| Azure Cache for Redis | Premium P1 | $400 | 6GB |
| App Service | Premium P2V2 x 3 | $300 | Auto-scaling |
| Application Gateway | Standard_v2 | $150 | Variable hourly |
| Storage Account | Standard LRS | $100-300 | Based on usage |
| Monitor/Logs | Variable | $50-150 | Analytics + diagnostics |
| **Total** | | **$1,800-2,200** | **Conservative estimate** |

### Cost Monitoring

```bash
# AWS Cost Explorer API
aws ce get-cost-and-usage \
  --time-period Start=2025-11-01,End=2025-11-30 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE

# Set up billing alarms
aws cloudwatch put-metric-alarm \
  --alarm-name billing-threshold \
  --alarm-description "Alert if bill exceeds $5000" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --threshold 5000 \
  --comparison-operator GreaterThanThreshold
```

---

## Troubleshooting

### Common Issues and Solutions

#### Database Connection Issues

**Symptom:** "too many connections" error

```bash
# Check active connections
SELECT datname, usename, count(*) FROM pg_stat_activity GROUP BY datname, usename;

# Kill idle connections
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE state = 'idle' AND query_start < NOW() - INTERVAL '1 hour';

# Increase max_connections in RDS parameter group
# Recommended: max_connections = 200 + (num_workers * num_connections_per_worker)
```

**Symptom:** High query latency

```bash
# Enable slow query logging
ALTER SYSTEM SET log_min_duration_statement = 1000;
SELECT pg_reload_conf();

# Find slow queries
SELECT query, calls, mean_time FROM pg_stat_statements
ORDER BY mean_time DESC LIMIT 10;

# Analyze and optimize
EXPLAIN ANALYZE SELECT ... FROM ...;

# Add missing indices
CREATE INDEX idx_buildings_location ON buildings USING GIST(geom);
```

#### Redis Issues

**Symptom:** High memory usage

```bash
# Check memory usage
INFO memory

# Find largest keys
MEMORY DOCTOR
MEMORY STATS

# Reduce eviction policy memory
CONFIG SET maxmemory-policy allkeys-lru
CONFIG REWRITE
```

**Symptom:** Connection issues

```bash
# Check active connections
INFO clients

# Increase max clients if needed
CONFIG SET maxclients 100000
```

#### API Performance Issues

**Symptom:** High response time

```bash
# Check API metrics
curl http://localhost:8000/metrics

# Check worker processes
ps aux | grep uvicorn

# Increase workers if needed
UVICORN_WORKERS=8 (for 4-core CPU, use 2-4x)

# Check database connection pool
SELECT * FROM pg_stat_database WHERE datname = 'entmoot';
```

**Symptom:** Memory leaks

```bash
# Monitor memory over time
docker stats

# Check for memory leaks
# Use memory profiler: python -m memory_profiler app.py

# Restart container with health check
# Implement automated restart: max_restarts=5 with cooldown
```

#### Deployment Failures

**Symptom:** ECS task fails to start

```bash
# Check task logs
aws logs tail /ecs/entmoot-prod --follow

# Check task definition
aws ecs describe-task-definition --task-definition entmoot-api:1

# Validate environment variables
aws ecs describe-task-definition --task-definition entmoot-api:1 | \
  grep -A 20 containerDefinitions
```

**Symptom:** Health check fails

```bash
# Test health endpoint
curl -v https://api.yourdomain.com/health

# Check TLS certificate
openssl s_client -connect api.yourdomain.com:443

# Verify application is listening
netstat -tlnp | grep 8000
```

### Performance Tuning Checklist

- [ ] Database connection pool size optimized
- [ ] Redis cluster configured for high availability
- [ ] Query indices created for common operations
- [ ] Caching strategy implemented
- [ ] API worker processes tuned (2-4x CPU cores)
- [ ] Database parameters tuned (shared_buffers, effective_cache_size, etc.)
- [ ] Load balancer configured for session affinity if needed
- [ ] CDN enabled for static assets
- [ ] API rate limiting configured
- [ ] Database connection timeouts configured

### Debug Commands

```bash
# SSH into ECS container
aws ecs execute-command \
  --cluster entmoot-prod \
  --task <task-id> \
  --container api \
  --interactive \
  --command "/bin/bash"

# Check database from API container
psql postgresql://user:pass@host/entmoot -c "SELECT version();"

# Monitor in real-time
watch 'curl http://localhost:8000/metrics | grep http_request'

# Tail application logs
docker logs -f <container-id> --timestamps

# Check Redis connection
redis-cli -h <redis-host> -a <password> ping
```

---

## Appendix

### Security Best Practices

1. **Network Security**
   - Use VPC with private subnets for databases
   - Enable VPC Flow Logs for monitoring
   - Use security groups to restrict access
   - Enable WAF (Web Application Firewall)

2. **Data Protection**
   - Enable encryption at rest (KMS/Azure Disk)
   - Enable encryption in transit (TLS 1.2+)
   - Use AWS Secrets Manager / Azure Key Vault / GCP Secret Manager
   - Implement column-level encryption for sensitive data

3. **Access Control**
   - Use IAM roles instead of credentials
   - Implement MFA for all accounts
   - Use SSH keys instead of passwords
   - Regularly audit IAM permissions

4. **Compliance**
   - Enable audit logging (CloudTrail/Cloud Audit Logs)
   - Implement data retention policies
   - Regular security assessments
   - Penetration testing quarterly

### Disaster Recovery Runbook Quick Reference

| Scenario | RTO | RPO | Action |
|----------|-----|-----|--------|
| Single server failure | 5 min | 1 min | Auto-heal via ASG |
| Database failure | 10 min | 5 min | Promote read replica |
| Region failure | 30 min | 15 min | Failover to backup region |
| Data corruption | 1 hour | 0 min | PITR restore |
| Security breach | 2 hours | 0 min | Rebuild from clean AMI |

### Related Documentation

- [Disaster Recovery Plan](disaster-recovery.md)
- [Operations Runbook](operations.md)
- [Architecture Documentation](../architecture.md)
- [Development Guide](development.md)

---

**Last Updated:** 2025-11-10
**Maintained By:** DevOps Team
**Review Schedule:** Quarterly
