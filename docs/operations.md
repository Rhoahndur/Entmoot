# Operations Runbook

Entmoot - AI-Driven Site Layout Automation Platform

**Version:** 1.0
**Last Updated:** 2025-11-10
**Audience:** DevOps Engineers, SREs, Operations Team

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Daily Operations](#daily-operations)
3. [Common Operational Tasks](#common-operational-tasks)
4. [Troubleshooting Guide](#troubleshooting-guide)
5. [Log Locations and Analysis](#log-locations-and-analysis)
6. [Alert Response Procedures](#alert-response-procedures)
7. [Scaling Procedures](#scaling-procedures)
8. [Database Maintenance](#database-maintenance)
9. [Performance Optimization](#performance-optimization)
10. [On-Call Procedures](#on-call-procedures)

---

## Quick Reference

### Important Endpoints and Resources

```
Production:
  API: https://api.yourdomain.com
  Status Page: https://status.yourdomain.com
  Monitoring: https://grafana.yourdomain.com
  Logs: https://kibana.yourdomain.com
  Database: entmoot-prod.xxxxxxxxxxxx.rds.amazonaws.com:5432
  Redis: entmoot-redis-prod.xxxxxxxxxxxx.cache.amazonaws.com:6379

Staging:
  API: https://api-staging.yourdomain.com
  Database: entmoot-staging.xxxxxxxxxxxx.rds.amazonaws.com:5432
  Redis: entmoot-redis-staging.xxxxxxxxxxxx.cache.amazonaws.com:6379
```

### Critical Contacts

```
On-Call Engineer: [Configure for your organization]
Database DBA: [Configure for your organization]
Security Team: [Configure for your organization]
Infrastructure Lead: [Configure for your organization]
CTO/Tech Lead: [Configure for your organization]
```

### Quick Commands

```bash
# API Health
curl -H "Authorization: Bearer $TOKEN" https://api.yourdomain.com/health

# Service Status (AWS)
aws ecs describe-services --cluster entmoot-prod --services entmoot-api \
  --query 'services[0].{Status:status,RunningCount:runningCount,DesiredCount:desiredCount}'

# Database Status
psql -h entmoot-prod.rds.amazonaws.com -U postgres -c \
  "SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;"

# Redis Status
redis-cli -h entmoot-redis-prod.cache.amazonaws.com ping

# Recent Logs
aws logs tail /ecs/entmoot-prod --follow --since 10m

# Error Count (Last Hour)
aws logs filter-log-events --log-group-name /ecs/entmoot-prod \
  --start-time $(date -d '1 hour ago' +%s000) | grep ERROR | wc -l
```

---

## Daily Operations

### Morning Checklist (Start of Business Day)

**Time: 09:00 AM - 15 minutes**

```bash
#!/bin/bash
# scripts/daily-morning-checklist.sh

echo "=== Daily Morning Operations Checklist ==="
echo "Start time: $(date)"

# 1. Check service status
echo ""
echo "[1] Checking service status..."
curl -s -H "Authorization: Bearer $API_TOKEN" \
  https://api.yourdomain.com/health | jq '.'

# 2. Check for alarms
echo ""
echo "[2] Checking for any active alarms..."
aws cloudwatch describe-alarms --state-value ALARM --max-items 10 \
  --query 'MetricAlarms[*].[AlarmName,StateReason]' --output table

# 3. Check database replication
echo ""
echo "[3] Checking database replication lag..."
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT
    slot_name,
    slot_type,
    active,
    restart_lsn
  FROM pg_replication_slots;
EOF

# 4. Check Redis status
echo ""
echo "[4] Checking Redis cluster status..."
redis-cli -h entmoot-redis-prod.cache.amazonaws.com \
  --csv INFO stats | grep -E "total_commands_processed|connected_clients"

# 5. Check disk usage
echo ""
echo "[5] Checking disk usage..."
aws rds describe-db-instances --db-instance-identifier entmoot-prod \
  --query 'DBInstances[0].{AllocatedStorage:AllocatedStorage,StorageType:StorageType}' \
  --output table

# 6. Check error rate
echo ""
echo "[6] Checking error rate (last hour)..."
ERROR_COUNT=$(aws logs filter-log-events \
  --log-group-name /ecs/entmoot-prod \
  --start-time $(date -d '1 hour ago' +%s000) \
  --filter-pattern "[ERROR]" | jq '.events | length')
echo "Error count: $ERROR_COUNT"

# 7. Check job queue
echo ""
echo "[7] Checking optimization job queue..."
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT
    status,
    COUNT(*) as job_count,
    MIN(created_at) as oldest_job
  FROM optimization_jobs
  WHERE status IN ('pending', 'running')
  GROUP BY status;
EOF

echo ""
echo "=== Checklist Complete ==="
echo "Issues found? Check 'Troubleshooting Guide' section"
```

### Evening Checklist (End of Business Day)

**Time: 05:00 PM - 10 minutes**

```bash
#!/bin/bash
# scripts/daily-evening-checklist.sh

echo "=== Daily Evening Operations Checklist ==="
echo "End time: $(date)"

# 1. Verify backup completed
echo ""
echo "[1] Verifying backup..."
LATEST_BACKUP=$(aws rds describe-db-snapshots \
  --db-instance-identifier entmoot-prod \
  --query 'DBSnapshots[0].SnapshotCreateTime' --output text)
echo "Latest backup: $LATEST_BACKUP"

BACKUP_AGE_HOURS=$(( ($(date +%s) - $(date -d "$LATEST_BACKUP" +%s)) / 3600 ))
if [ $BACKUP_AGE_HOURS -gt 24 ]; then
  echo "WARNING: Backup is $BACKUP_AGE_HOURS hours old!"
fi

# 2. Check for pending deployments
echo ""
echo "[2] Checking for pending changes..."
aws ecs describe-services --cluster entmoot-prod --services entmoot-api \
  --query 'services[0].{PendingCount:pendingCount,DeploymentCount:deployments | length()}' \
  --output table

# 3. Verify no unusual activity
echo ""
echo "[3] Checking for unusual activity..."
aws cloudtrail lookup-events --max-results 5 \
  --query 'Events[*].[EventTime,EventName,Username]' --output table

# 4. Summary of daily metrics
echo ""
echo "[4] Summary of daily metrics..."
echo "API Request Count (last 24h):"
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name RequestCount \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Sum \
  --output table

echo ""
echo "=== Evening Checklist Complete ==="
```

---

## Common Operational Tasks

### Deploying a New Version

```bash
#!/bin/bash
# scripts/deploy-new-version.sh

VERSION=$1
if [ -z "$VERSION" ]; then
  echo "Usage: ./deploy-new-version.sh <version>"
  echo "Example: ./deploy-new-version.sh 0.2.0"
  exit 1
fi

echo "=== Deploying Entmoot v$VERSION ==="

# 1. Build Docker image
echo "[1] Building Docker image..."
docker build -t entmoot-api:$VERSION .
docker tag entmoot-api:$VERSION 123456789.dkr.ecr.us-east-1.amazonaws.com/entmoot-api:$VERSION

# 2. Push to registry
echo "[2] Pushing to ECR..."
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin \
  123456789.dkr.ecr.us-east-1.amazonaws.com
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/entmoot-api:$VERSION

# 3. Register new task definition
echo "[3] Registering new task definition..."
sed "s|{{VERSION}}|$VERSION|g" ecs-task-definition.json > /tmp/task-def-$VERSION.json
aws ecs register-task-definition --cli-input-json file:///tmp/task-def-$VERSION.json

# 4. Update service (blue-green deployment)
echo "[4] Updating ECS service..."
TASK_REVISION=$(aws ecs describe-task-definition \
  --task-definition entmoot-api \
  --query 'taskDefinition.revision' --output text)

aws ecs update-service \
  --cluster entmoot-prod \
  --service entmoot-api \
  --task-definition entmoot-api:$TASK_REVISION \
  --force-new-deployment

# 5. Monitor deployment
echo "[5] Monitoring deployment progress..."
for i in {1..300}; do
  STATUS=$(aws ecs describe-services \
    --cluster entmoot-prod \
    --services entmoot-api \
    --query 'services[0].{Running:runningCount,Desired:desiredCount}' \
    --output text)

  RUNNING=$(echo $STATUS | awk '{print $1}')
  DESIRED=$(echo $STATUS | awk '{print $2}')

  echo "Progress: $RUNNING/$DESIRED instances healthy"

  if [ "$RUNNING" -eq "$DESIRED" ]; then
    echo "Deployment complete!"
    break
  fi

  if [ $((i % 10)) -eq 0 ]; then
    # Every 10 checks, verify health
    HEALTH=$(curl -s -H "Authorization: Bearer $API_TOKEN" \
      https://api.yourdomain.com/health | jq '.status')
    echo "Health: $HEALTH"
  fi

  sleep 1
done

# 6. Verify deployment
echo "[6] Verifying deployment..."
DEPLOYED_VERSION=$(curl -s -H "Authorization: Bearer $API_TOKEN" \
  https://api.yourdomain.com/health | jq '.version')

if [ "$DEPLOYED_VERSION" = "\"$VERSION\"" ]; then
  echo "✓ Deployment successful!"
else
  echo "✗ Deployment verification failed. Expected $VERSION, got $DEPLOYED_VERSION"
  exit 1
fi

echo ""
echo "=== Deployment Complete ==="
echo "Monitor at: https://grafana.yourdomain.com"
```

### Rolling Back a Deployment

```bash
#!/bin/bash
# scripts/rollback-deployment.sh

PREVIOUS_VERSION=$1
if [ -z "$PREVIOUS_VERSION" ]; then
  echo "Usage: ./rollback-deployment.sh <previous-version>"
  echo "Example: ./rollback-deployment.sh 0.1.0"
  exit 1
fi

echo "=== Rolling Back to v$PREVIOUS_VERSION ==="
read -p "This will rollback production. Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  exit 1
fi

# 1. Get previous task definition
echo "[1] Getting previous task definition..."
PREVIOUS_REVISION=$(aws ecs describe-task-definition \
  --task-definition entmoot-api:$PREVIOUS_VERSION \
  --query 'taskDefinition.revision' --output text)

# 2. Update service
echo "[2] Rolling back service..."
aws ecs update-service \
  --cluster entmoot-prod \
  --service entmoot-api \
  --task-definition entmoot-api:$PREVIOUS_REVISION \
  --force-new-deployment

# 3. Monitor rollback
echo "[3] Monitoring rollback..."
for i in {1..300}; do
  STATUS=$(aws ecs describe-services \
    --cluster entmoot-prod \
    --services entmoot-api \
    --query 'services[0].{Running:runningCount,Desired:desiredCount}' \
    --output text)

  RUNNING=$(echo $STATUS | awk '{print $1}')
  DESIRED=$(echo $STATUS | awk '{print $2}')

  echo "Progress: $RUNNING/$DESIRED instances"

  if [ "$RUNNING" -eq "$DESIRED" ]; then
    echo "Rollback complete!"
    break
  fi

  sleep 1
done

echo ""
echo "=== Rollback Complete ==="
```

### Scaling API Servers

```bash
#!/bin/bash
# scripts/scale-api-servers.sh

DESIRED_COUNT=$1
if [ -z "$DESIRED_COUNT" ]; then
  echo "Usage: ./scale-api-servers.sh <count>"
  echo "Current capacity: 3-20 instances"
  exit 1
fi

echo "=== Scaling API Servers ==="
echo "Current desired count: $(aws ecs describe-services \
  --cluster entmoot-prod --services entmoot-api \
  --query 'services[0].desiredCount' --output text)"

echo "New desired count: $DESIRED_COUNT"
read -p "Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  exit 1
fi

# Update service
aws ecs update-service \
  --cluster entmoot-prod \
  --service entmoot-api \
  --desired-count $DESIRED_COUNT

echo "Scaling request submitted"
echo "Monitor progress: aws ecs describe-services --cluster entmoot-prod --services entmoot-api"
```

---

## Troubleshooting Guide

### High API Error Rate

**Symptom:** Error rate > 1% (alert triggered)

**Investigation:**
```bash
# Check error logs
aws logs filter-log-events \
  --log-group-name /ecs/entmoot-prod \
  --filter-pattern "[ERROR]" \
  --start-time $(date -d '30 minutes ago' +%s000) | \
  jq '.events[] | .message' | head -20

# Check specific error type
aws logs filter-log-events \
  --log-group-name /ecs/entmoot-prod \
  --filter-pattern "ERROR.*DatabaseError" \
  --start-time $(date -d '30 minutes ago' +%s000)

# Check recent deployments
aws ecs describe-services \
  --cluster entmoot-prod \
  --services entmoot-api \
  --query 'services[0].deployments'

# Check database connections
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT datname, usename, state, count(*)
  FROM pg_stat_activity
  GROUP BY datname, usename, state;
EOF

# Check Redis status
redis-cli -h entmoot-redis-prod.cache.amazonaws.com INFO stats
```

**Common Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Database connection pool exhausted | Increase `DATABASE_POOL_SIZE` or restart API |
| Recent bad deployment | Rollback to previous version |
| Slow database queries | Analyze slow queries, add indices |
| External API timeouts | Check external API status, increase timeout |
| Memory leak/OOM | Restart containers, investigate memory profiling |

### High Database CPU

**Symptom:** Database CPU > 80%

**Investigation:**
```bash
# Check currently running queries
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT pid, usename, state, query, query_start, wait_event
  FROM pg_stat_activity
  WHERE state != 'idle'
  ORDER BY query_start ASC;
EOF

# Check slow query log
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT query, calls, mean_time, max_time
  FROM pg_stat_statements
  ORDER BY mean_time DESC
  LIMIT 10;
EOF

# Check table statistics
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT schemaname, tablename, idx_scan, idx_tup_read, idx_tup_fetch
  FROM pg_stat_user_indexes
  ORDER BY idx_scan DESC;
EOF

# Check for missing indices
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT * FROM pg_stat_user_tables
  WHERE seq_scan > idx_scan
  AND seq_scan > 1000
  ORDER BY seq_scan DESC;
EOF
```

**Solutions:**

1. **Kill long-running query:**
   ```bash
   psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot \
     -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid = <pid>"
   ```

2. **Add missing index:**
   ```bash
   psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
     CREATE INDEX idx_buildings_location ON buildings USING GIST(geom);
     ANALYZE buildings;
   EOF
   ```

3. **Increase database resources:**
   ```bash
   # Upgrade RDS instance
   aws rds modify-db-instance \
     --db-instance-identifier entmoot-prod \
     --db-instance-class db.r6i.2xlarge \
     --apply-immediately
   ```

4. **Scale read replicas:**
   ```bash
   # Redirect read-heavy queries to replica
   # Update application connection string
   ```

### API Response Time High

**Symptom:** API p95 response time > 500ms

**Investigation:**
```bash
# Check API metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name TargetResponseTime \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average,Maximum \
  --output table

# Check slow endpoints
aws logs filter-log-events \
  --log-group-name /ecs/entmoot-prod \
  --filter-pattern "[duration > 1000]" | \
  jq '.events[] | .message' | head -10

# Check request queue depth
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name RequestCount \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum

# Check instance CPU/Memory
aws ecs describe-container-instances \
  --cluster entmoot-prod \
  --query 'containerInstances[*].{CPU:registeredCpuUnits,Memory:registeredMemoryUnits}'
```

**Solutions:**

1. **Scale horizontally:**
   ```bash
   ./scripts/scale-api-servers.sh 8  # Increase from current count
   ```

2. **Identify slow endpoints:**
   ```bash
   # From logs, identify which endpoints are slow
   # Profile the endpoint code
   # Optimize database queries
   ```

3. **Increase caching:**
   ```bash
   # Increase Redis TTL for expensive queries
   # Add new cache keys
   # Monitor cache hit rate
   ```

### Redis Connection Issues

**Symptom:** Redis connection timeout or "NOAUTH" errors

**Investigation:**
```bash
# Check Redis cluster status
redis-cli -h entmoot-redis-prod.cache.amazonaws.com \
  -a $REDIS_PASSWORD \
  cluster info

# Check connections
redis-cli -h entmoot-redis-prod.cache.amazonaws.com \
  -a $REDIS_PASSWORD \
  INFO clients

# Check memory usage
redis-cli -h entmoot-redis-prod.cache.amazonaws.com \
  -a $REDIS_PASSWORD \
  INFO memory
```

**Solutions:**

1. **Check authentication:**
   ```bash
   # Verify AUTH token is correct
   # Update .env files if token changed
   # Restart API servers
   ```

2. **Flush old cache:**
   ```bash
   redis-cli -h entmoot-redis-prod.cache.amazonaws.com \
     -a $REDIS_PASSWORD \
     FLUSHALL
   ```

3. **Increase max memory:**
   ```bash
   redis-cli -h entmoot-redis-prod.cache.amazonaws.com \
     -a $REDIS_PASSWORD \
     CONFIG SET maxmemory 8gb
   ```

### Database Connection Pool Exhaustion

**Symptom:** "QueuePool timeout exceeded" errors

**Investigation:**
```bash
# Check connection pool size
echo $DATABASE_POOL_SIZE

# Check active connections
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT datname, count(*) as connection_count
  FROM pg_stat_activity
  GROUP BY datname;
EOF

# Check for idle connections
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT datname, state, count(*)
  FROM pg_stat_activity
  GROUP BY datname, state;
EOF
```

**Solutions:**

1. **Increase pool size:**
   ```bash
   # Update .env
   DATABASE_POOL_SIZE=30

   # Restart API servers to apply change
   aws ecs update-service --cluster entmoot-prod --service entmoot-api --force-new-deployment
   ```

2. **Kill idle connections:**
   ```bash
   psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
     SELECT pg_terminate_backend(pid)
     FROM pg_stat_activity
     WHERE datname = 'entmoot'
       AND state = 'idle'
       AND query_start < NOW() - INTERVAL '30 minutes';
   EOF
   ```

3. **Enable connection pooling (PgBouncer):**
   ```bash
   # Deploy PgBouncer as sidecar container
   # Configure pgbouncer.ini for application
   # Restart API servers
   ```

---

## Log Locations and Analysis

### AWS CloudWatch Logs

```bash
# API logs
aws logs tail /ecs/entmoot-prod --follow

# Filter by level
aws logs filter-log-events \
  --log-group-name /ecs/entmoot-prod \
  --filter-pattern "[ERROR]"

# Filter by endpoint
aws logs filter-log-events \
  --log-group-name /ecs/entmoot-prod \
  --filter-pattern "POST /api/optimize"

# Export logs
aws logs create-export-task \
  --log-group-name /ecs/entmoot-prod \
  --start-time $(date -d '7 days ago' +%s000) \
  --end-time $(date +%s000) \
  --destination entmoot-log-exports \
  --destination-prefix entmoot-prod-$(date +%Y%m%d)
```

### GCP Cloud Logging

```bash
# View API logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=entmoot-api" \
  --limit 50 --format json

# Filter by severity
gcloud logging read "severity=ERROR AND resource.type=cloud_run_revision" \
  --limit 20 --format=json

# Stream logs
gcloud logging read "resource.type=cloud_run_revision" --limit 0 --follow
```

### Azure Monitor

```bash
# Query logs
az monitor log-analytics query \
  -w <workspace-id> \
  -q "AzureDiagnostics | where TimeGenerated > ago(1h) | summarize count() by Level"

# Stream logs
az monitor diagnostic-settings list \
  --resource entmoot-api \
  --resource-group entmoot-prod
```

### Log Analysis Examples

**Find errors in last hour:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/entmoot-prod \
  --start-time $(date -d '1 hour ago' +%s000) \
  --filter-pattern "[ERROR]" | \
  jq '.events[].message' | sort | uniq -c | sort -rn
```

**Find slowest requests:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/entmoot-prod \
  --filter-pattern "[duration >= 2000]" | \
  jq '.events[].message' | head -10
```

**Monitor specific endpoint:**
```bash
aws logs tail /ecs/entmoot-prod --follow --filter-pattern "POST /api/optimize"
```

---

## Alert Response Procedures

### Alert: High CPU Utilization (>80%)

**Priority:** Medium | **Response Time:** 15 minutes

| Step | Action | Command |
|------|--------|---------|
| 1 | Acknowledge alert | Click alert in PagerDuty |
| 2 | Identify source | `aws cloudwatch get-metric-statistics --metric-name CPUUtilization` |
| 3 | Check database | See "High Database CPU" troubleshooting |
| 4 | Check API | See "API Response Time High" troubleshooting |
| 5 | Scale if needed | `./scripts/scale-api-servers.sh <count>` |
| 6 | Document | Add note to incident ticket |

### Alert: Error Rate High (>1%)

**Priority:** Critical | **Response Time:** 5 minutes

| Step | Action | Command |
|------|--------|---------|
| 1 | Page on-call | PagerDuty auto-pages |
| 2 | Check recent deployments | `aws ecs describe-services --cluster entmoot-prod` |
| 3 | Review error logs | `aws logs filter-log-events --filter-pattern "[ERROR]"` |
| 4 | Determine if rollback needed | Check error patterns |
| 5 | Rollback if necessary | `./scripts/rollback-deployment.sh <version>` |
| 6 | Verify recovery | `curl https://api.yourdomain.com/health` |
| 7 | Post-mortem | Schedule incident review |

### Alert: Database Replication Lag (>60s)

**Priority:** High | **Response Time:** 10 minutes

| Step | Action | Command |
|------|--------|---------|
| 1 | Check replication status | `psql ... -c "SELECT slot_name, restart_lsn FROM pg_replication_slots;"` |
| 2 | Check network | `aws ec2 describe-network-interfaces` |
| 3 | Monitor lag | Watch metrics for recovery |
| 4 | If lag increasing | Reduce write load to primary |
| 5 | Contact AWS Support | If lag continues > 5 min |

### Alert: Disk Space Low (<10%)

**Priority:** High | **Response Time:** 30 minutes

| Step | Action | Command |
|------|--------|---------|
| 1 | Check disk usage | `aws rds describe-db-instances --query 'DBInstances[0].AllocatedStorage'` |
| 2 | Analyze large tables | `psql ... -c "SELECT * FROM pg_stat_user_tables ORDER BY heap_blks_read DESC;"` |
| 3 | Archive old data | Move old projects/optimizations to archive |
| 4 | Increase storage | `aws rds modify-db-instance --allocated-storage 500` |
| 5 | Cleanup S3 | Review S3 lifecycle policies |

---

## Scaling Procedures

### Horizontal Scaling (Add More Instances)

**When to scale out:**
- CPU > 70%
- Memory > 80%
- Request latency p95 > 500ms
- Error rate > 0.5%

```bash
#!/bin/bash
# scripts/scale-out-api.sh

echo "=== Scaling Out API Servers ==="

CURRENT=$(aws ecs describe-services \
  --cluster entmoot-prod --services entmoot-api \
  --query 'services[0].desiredCount' --output text)

NEW_COUNT=$(($CURRENT + 2))
MAX_COUNT=20

if [ $NEW_COUNT -gt $MAX_COUNT ]; then
  NEW_COUNT=$MAX_COUNT
  echo "WARNING: Reached maximum capacity ($MAX_COUNT)"
fi

echo "Scaling from $CURRENT to $NEW_COUNT instances..."

aws ecs update-service \
  --cluster entmoot-prod \
  --service entmoot-api \
  --desired-count $NEW_COUNT

# Monitor scaling
for i in {1..60}; do
  RUNNING=$(aws ecs describe-services \
    --cluster entmoot-prod --services entmoot-api \
    --query 'services[0].runningCount' --output text)

  echo "Running instances: $RUNNING/$NEW_COUNT"

  if [ $RUNNING -eq $NEW_COUNT ]; then
    echo "Scaling complete!"
    break
  fi

  sleep 10
done
```

### Vertical Scaling (Larger Instances)

**When to scale up:**
- Single instance consistently at 90%+ CPU
- Memory insufficient for optimization jobs
- Database CPU bottleneck

```bash
#!/bin/bash
# scripts/scale-up-database.sh

echo "=== Vertical Scaling Database ==="
echo "Current: db.r6i.xlarge"
echo "Target: db.r6i.2xlarge (double resources)"
echo ""

read -p "Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  exit 1
fi

# Modify instance (with maintenance window)
aws rds modify-db-instance \
  --db-instance-identifier entmoot-prod \
  --db-instance-class db.r6i.2xlarge \
  --apply-immediately  # WARNING: causes brief outage

echo "Instance upgrade in progress..."
echo "Monitor at: https://console.aws.amazon.com/rds"

# Wait for upgrade
while true; do
  STATUS=$(aws rds describe-db-instances \
    --db-instance-identifier entmoot-prod \
    --query 'DBInstances[0].DBInstanceStatus' \
    --output text)

  if [ "$STATUS" = "available" ]; then
    echo "Upgrade complete!"
    break
  fi

  echo "Status: $STATUS (waiting...)"
  sleep 30
done
```

### Cache Scaling (Redis)

**When to scale:**
- Eviction rate increasing (keys being removed due to memory)
- Hit rate < 70%
- Memory near 90% utilization

```bash
#!/bin/bash
# scripts/scale-redis.sh

echo "=== Redis Cluster Scaling ==="

# Check current memory
MEMORY=$(redis-cli -h entmoot-redis-prod.cache.amazonaws.com \
  INFO memory | grep used_memory_human | cut -d: -f2)

echo "Current memory usage: $MEMORY"

# Check hit rate
STATS=$(redis-cli -h entmoot-redis-prod.cache.amazonaws.com INFO stats)
HITS=$(echo "$STATS" | grep keyspace_hits | cut -d: -f2)
MISSES=$(echo "$STATS" | grep keyspace_misses | cut -d: -f2)
HIT_RATE=$(echo "scale=2; $HITS / ($HITS + $MISSES) * 100" | bc)

echo "Current hit rate: $HIT_RATE%"

if [ $(echo "$HIT_RATE < 70" | bc) -eq 1 ]; then
  echo "Hit rate low, scaling up Redis..."

  # AWS ElastiCache scaling
  aws elasticache increase-replica-count \
    --replication-group-id entmoot-redis-prod \
    --new-replica-count 5  # Add more replicas
fi
```

---

## Database Maintenance

### Weekly Maintenance

**Schedule:** Sunday 02:00-03:00 UTC (maintenance window)

```bash
#!/bin/bash
# scripts/weekly-db-maintenance.sh

echo "=== Weekly Database Maintenance ==="

# 1. Analyze tables
echo "[1] Analyzing tables..."
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  ANALYZE buildings;
  ANALYZE projects;
  ANALYZE optimizations;
  ANALYZE optimization_jobs;
EOF

# 2. Reindex if needed
echo "[2] Checking for index bloat..."
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT schemaname, tablename, indexname, idx_blks_read
  FROM pg_stat_user_indexes
  WHERE idx_blks_read > 1000
  ORDER BY idx_blks_read DESC;
EOF

# 3. Vacuum to reclaim space
echo "[3] Vacuuming tables..."
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  VACUUM ANALYZE buildings;
  VACUUM ANALYZE projects;
  VACUUM ANALYZE optimizations;
EOF

# 4. Check bloat
echo "[4] Checking table bloat..."
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT schemaname, tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
  FROM pg_stat_user_tables
  WHERE pg_total_relation_size(schemaname||'.'||tablename) > 1000000
  ORDER BY pg_total_relation_size DESC;
EOF

echo "=== Maintenance Complete ==="
```

### Monthly Maintenance

**Schedule:** First Sunday of month, 02:00-05:00 UTC

```bash
#!/bin/bash
# scripts/monthly-db-maintenance.sh

echo "=== Monthly Database Maintenance ==="

# 1. Full REINDEX (careful!)
echo "[1] Reindexing critical tables..."
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  REINDEX INDEX CONCURRENTLY idx_buildings_location;
  REINDEX INDEX CONCURRENTLY idx_buildings_bbox;
  REINDEX TABLE CONCURRENTLY projects;
EOF

# 2. Update statistics
echo "[2] Updating query planner statistics..."
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  ANALYZE;
EOF

# 3. Check for unused indices
echo "[3] Identifying unused indices..."
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT schemaname, tablename, indexname, idx_scan
  FROM pg_stat_user_indexes
  WHERE idx_scan = 0
  AND indexrelname NOT LIKE 'pg_toast%';
EOF

# 4. Cleanup old data (archive if needed)
echo "[4] Archiving old optimization results..."
psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  -- Move old completed jobs to archive table
  INSERT INTO optimization_jobs_archive
  SELECT * FROM optimization_jobs
  WHERE completed_at < NOW() - INTERVAL '90 days'
  AND status = 'completed';

  -- Delete from main table
  DELETE FROM optimization_jobs
  WHERE completed_at < NOW() - INTERVAL '90 days'
  AND status = 'completed';

  VACUUM ANALYZE optimization_jobs;
EOF

echo "=== Monthly Maintenance Complete ==="
```

### Query Performance Tuning

```bash
#!/bin/bash
# scripts/analyze-slow-queries.sh

echo "=== Slow Query Analysis ==="

psql -h entmoot-prod.rds.amazonaws.com -U postgres -d entmoot << EOF
  -- Enable pg_stat_statements if not already enabled
  CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

  -- Find slowest queries
  SELECT query, calls, mean_time, max_time, stddev_time
  FROM pg_stat_statements
  WHERE mean_time > 1000  -- Queries taking > 1 second
  ORDER BY mean_time DESC
  LIMIT 20;

  -- Find most frequently called slow queries
  SELECT query, calls, mean_time
  FROM pg_stat_statements
  WHERE mean_time > 100  -- Queries taking > 100ms
    AND calls > 100      -- Called more than 100 times
  ORDER BY calls * mean_time DESC
  LIMIT 10;

  -- Reset statistics
  -- SELECT pg_stat_statements_reset();
EOF
```

---

## Performance Optimization

### Connection Pool Tuning

```bash
# Current settings
echo "DATABASE_POOL_SIZE: $DATABASE_POOL_SIZE"
echo "DATABASE_MAX_OVERFLOW: $DATABASE_MAX_OVERFLOW"

# Formula for optimal pool size
# pool_size = (core_count * 2) + effective_spindle_count
# For 4 cores: pool_size = 8 + 1 = 9 (round to 10-20)
# For 8 cores: pool_size = 16 + 1 = 17 (round to 20-30)

# Recommended settings
DATABASE_POOL_SIZE=25              # Number of worker * 3
DATABASE_MAX_OVERFLOW=5            # Additional overflow connections
DATABASE_POOL_TIMEOUT=30           # Wait up to 30s for connection
DATABASE_POOL_RECYCLE=3600         # Recycle connections after 1 hour
```

### Query Optimization

```bash
# Before:
SELECT * FROM buildings
WHERE ST_Intersects(geom, ST_GeomFromText('POLYGON(...)'));

# After: Add GIST index
CREATE INDEX idx_buildings_geom ON buildings USING GIST(geom);

-- Then verify index is used
EXPLAIN ANALYZE
SELECT * FROM buildings
WHERE ST_Intersects(geom, ST_GeomFromText('POLYGON(...)'));
```

### Caching Strategy

```bash
# High-traffic read queries should be cached
# TTL guidelines:

- Constraint data (boundaries, zoning): 86400s (24h)
- Elevation data (DEM): 604800s (7 days)
- User preferences: 3600s (1h)
- API responses: 300s (5 min)
- Session data: 86400s (24h)

# Monitor cache effectiveness
redis-cli -h entmoot-redis-prod.cache.amazonaws.com \
  INFO stats | grep -E "keyspace_hits|keyspace_misses"
```

---

## On-Call Procedures

### On-Call Escalation

```
Level 1: Primary On-Call (15 min response time)
- Page PagerDuty
- Check #incidents Slack
- Follow escalation procedures

Level 2: Secondary On-Call (30 min response time)
- Auto-page if primary doesn't acknowledge

Level 3: Manager (1 hour response time)
- Auto-page if no response from Level 2
```

### Handoff Procedures

**End of shift checklist:**

```bash
#!/bin/bash
# scripts/onCall-handoff.sh

echo "=== On-Call Handoff Checklist ==="
echo "Current: $(date)"
echo ""

echo "[ ] Review open incidents in PagerDuty"
echo "[ ] Check active alarms:"
aws cloudwatch describe-alarms --state-value ALARM

echo "[ ] Verify recent deployments stable"
aws ecs describe-services --cluster entmoot-prod --services entmoot-api

echo "[ ] Check error rate (should be < 0.5%)"
aws logs filter-log-events \
  --log-group-name /ecs/entmoot-prod \
  --start-time $(date -d '1 hour ago' +%s000) \
  --filter-pattern "[ERROR]" | wc -l

echo "[ ] Share context with next on-call:"
echo "    - Any known issues"
echo "    - Pending deployments"
echo "    - Unusual metrics"
echo ""
echo "=== Handoff Complete ==="
```

### Emergency Response

**Critical Incident Flow:**

```
1. Acknowledge alert (< 5 min)
   - PagerDuty auto-page
   - Join war room call
   - Share screen / logs

2. Initial assessment (< 10 min)
   - What is affected?
   - How many users impacted?
   - What is the cause?
   - Is it still ongoing?

3. Mitigation (< 30 min)
   - Stop the bleeding
   - Rollback if needed
   - Scale up if needed
   - Enable read-only if needed

4. Resolution (< 2 hours)
   - Fix root cause
   - Verify fix works
   - Full system test
   - Monitor for stability

5. Post-Incident (within 48 hours)
   - Write detailed timeline
   - Document what happened
   - Identify action items
   - Schedule follow-up items
```

---

**Last Updated:** 2025-11-10
**Maintained By:** DevOps/SRE Team
**Review Schedule:** Monthly
**Next Review:** 2025-12-10
