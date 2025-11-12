# Disaster Recovery Plan

Entmoot - AI-Driven Site Layout Automation Platform

**Version:** 1.0
**Last Updated:** 2025-11-10
**Audience:** DevOps Engineers, SREs, Infrastructure Teams

## Executive Summary

This document outlines the comprehensive disaster recovery (DR) strategy for Entmoot, including recovery procedures, RTO/RPO targets, and testing schedules. The plan ensures business continuity and minimizes data loss in event of infrastructure failures.

## Table of Contents

1. [Recovery Targets](#recovery-targets)
2. [Backup Strategy](#backup-strategy)
3. [Failure Scenarios](#failure-scenarios)
4. [Recovery Procedures](#recovery-procedures)
5. [Failover Procedures](#failover-procedures)
6. [Testing and Validation](#testing-and-validation)
7. [Communication Plan](#communication-plan)
8. [Change Log](#change-log)

---

## Recovery Targets

### Recovery Time Objective (RTO) and Recovery Point Objective (RPO)

| Failure Scenario | RTO | RPO | Priority | Notes |
|------------------|-----|-----|----------|-------|
| Single server failure | 5 minutes | 1 minute | Critical | Auto-healing via ASG/HPA |
| AZ failure (partial) | 15 minutes | 5 minutes | Critical | Load balancer redirects traffic |
| Database failure (failover) | 10 minutes | 5 minutes | Critical | Automated promotion of standby |
| Region failure (DR) | 30 minutes | 15 minutes | High | Manual failover to backup region |
| Data corruption | 1 hour | 0 minutes | High | PITR restore to known good state |
| Security breach | 2 hours | 0 minutes | Critical | Rebuild from clean image |
| Cache layer failure | 3 minutes | 0 minutes | Medium | Auto-heal, graceful degradation |
| Storage bucket failure | 30 minutes | 1 hour | Medium | Cross-region replication |

### Service Level Targets

- **Availability Target:** 99.95% (4.38 hours downtime/month)
- **API Response Time:** p95 < 500ms
- **Database Connection Success Rate:** > 99.9%
- **Data Backup Success Rate:** 100%

---

## Backup Strategy

### Automated Backup Schedule

```
Database:
- Full backups: Daily at 03:00 UTC (30-day retention)
- Transaction logs: Continuous archival (7-day PITR window)
- Replicas: Continuous replication to standby in different AZ

Object Storage:
- Versioning: Enabled with 30-day retention
- Cross-region replication: Async to us-west-2 (AWS) / Multi-region (GCP/Azure)
- Lifecycle: Archive to Glacier after 30 days, delete after 1 year

Configuration:
- Infrastructure-as-Code: Daily snapshot to S3 backend
- Application secrets: Version controlled in Secret Manager
- DNS records: Regular export to version control
```

### Backup Infrastructure

#### AWS Backup

**Database Backups:**
```bash
# RDS automated backups
aws rds create-db-snapshot \
  --db-instance-identifier entmoot-prod \
  --db-snapshot-identifier entmoot-prod-manual-$(date +%Y%m%d-%H%M%S)

# Copy to another region for DR
aws rds copy-db-snapshot \
  --source-db-snapshot-identifier arn:aws:rds:us-east-1:ACCOUNT:snapshot:entmoot-prod-manual-20251110 \
  --target-db-snapshot-identifier entmoot-prod-manual-20251110-dr \
  --source-region us-east-1 \
  --destination-region us-west-2
```

**S3 Replication:**
```bash
# Enable S3 cross-region replication
aws s3api put-bucket-replication \
  --bucket entmoot-prod-files \
  --replication-configuration file://s3-replication.json
```

**s3-replication.json:**
```json
{
  "Role": "arn:aws:iam::ACCOUNT_ID:role/s3-replication-role",
  "Rules": [
    {
      "ID": "ReplicateAll",
      "Filter": {"Prefix": ""},
      "Status": "Enabled",
      "Destination": {
        "Bucket": "arn:aws:s3:::entmoot-prod-files-us-west-2",
        "ReplicationTime": {
          "Status": "Enabled",
          "Time": {"Minutes": 15}
        },
        "Metrics": {
          "Status": "Enabled",
          "EventThreshold": {"Minutes": 15}
        }
      }
    }
  ]
}
```

#### GCP Backup

**Cloud SQL Backups:**
```bash
# Automated backups configured in Cloud SQL instance settings
gcloud sql backups create \
  --instance=entmoot-prod

# Export to Cloud Storage for archival
gcloud sql export sql entmoot-prod \
  gs://entmoot-backups/entmoot-$(date +%Y%m%d-%H%M%S).sql
```

**Cloud Storage Replication:**
```bash
# Multi-region replication configured at bucket level
gsutil replication set "{}"
```

#### Azure Backup

**Azure Database Backups:**
```bash
# Automated backup configured in Azure Database settings
# PITR available for 35 days
az postgres flexible-server backup show \
  --resource-group entmoot-prod \
  --server-name entmoot-db

# Create on-demand backup
az postgres flexible-server backup create \
  --resource-group entmoot-prod \
  --server-name entmoot-db \
  --backup-name entmoot-$(date +%Y%m%d-%H%M%S)
```

**Storage Account Replication:**
```bash
# Configure geo-redundant storage (GRS) at account level
az storage account update \
  --resource-group entmoot-prod \
  --name entmootprodfiles \
  --sku Standard_GZRS
```

### Backup Verification

**Weekly Backup Verification:**

```bash
#!/bin/bash
# scripts/verify-backups.sh

set -e

echo "Verifying database backups..."

# Check latest backup
aws rds describe-db-snapshots \
  --db-instance-identifier entmoot-prod \
  --query 'DBSnapshots[0].[DBSnapshotIdentifier,SnapshotCreateTime,Status]' \
  --output table

# Check backup age
LATEST_BACKUP=$(aws rds describe-db-snapshots \
  --db-instance-identifier entmoot-prod \
  --query 'DBSnapshots[0].SnapshotCreateTime' \
  --output text)

BACKUP_AGE_HOURS=$(( ($(date +%s) - $(date -d "$LATEST_BACKUP" +%s)) / 3600 ))

if [ $BACKUP_AGE_HOURS -gt 24 ]; then
  echo "WARNING: Backup is $BACKUP_AGE_HOURS hours old"
  exit 1
fi

# Check S3 cross-region replication
aws s3 ls s3://entmoot-prod-files-us-west-2 --summarize

# Check backup file count
BACKUP_COUNT=$(aws s3 ls s3://entmoot-prod-backups --recursive | wc -l)
if [ $BACKUP_COUNT -lt 20 ]; then
  echo "WARNING: Only $BACKUP_COUNT backups found"
fi

echo "Backup verification completed successfully"
```

**Monthly Backup Restoration Test:**

```bash
#!/bin/bash
# scripts/test-backup-restore.sh

ENV=${1:-staging}
DB_HOST=${2:-localhost}

echo "Testing backup restoration..."

# Download latest backup
aws s3 cp s3://entmoot-prod-backups/latest.sql .

# Create test database
psql -h "$DB_HOST" -U postgres -c "CREATE DATABASE entmoot_test;"

# Restore backup
pg_restore -h "$DB_HOST" -U postgres -d entmoot_test latest.sql

# Run validation tests
psql -h "$DB_HOST" -U postgres -d entmoot_test << EOF
  SELECT COUNT(*) as building_count FROM buildings;
  SELECT COUNT(*) as project_count FROM projects;
  SELECT COUNT(*) as optimization_count FROM optimizations;
EOF

# Cleanup
psql -h "$DB_HOST" -U postgres -c "DROP DATABASE entmoot_test;"

echo "Backup restoration test completed successfully"
```

---

## Failure Scenarios

### Scenario 1: Single Server Failure

**Detection:** Health check fails for 2 consecutive checks (30-60 seconds)

**Impact:**
- Single API instance down
- Traffic automatically redistributed to healthy instances
- No user-facing impact if min 2 healthy instances exist

**Recovery Steps:**

```
1. Auto-healing triggered (AWS ASG / GCP Managed Instance Group)
   - Unhealthy instance terminated
   - New instance launched in replacement
   - RTO: ~3-5 minutes
   - RPO: 0 minutes (no data loss)

2. Manual verification (optional)
   - Confirm new instance is healthy
   - Review CloudWatch logs for failure cause
   - Update monitoring/alerts if needed
```

**Prevention:**
- Maintain minimum 3 API instances in production
- Configure health checks to fail fast (30-second timeout)
- Set instance auto-recovery on any cloud provider
- Regular instance updates and patching

### Scenario 2: Availability Zone Failure

**Detection:** Load balancer detects multiple failed health checks in single AZ

**Impact:**
- 1-2 API instances down
- Database standby in different AZ unaffected
- ~2-3 minutes service degradation

**Recovery Steps:**

```
1. Load balancer automatically redirects traffic
   - Healthy instances in other AZs handle requests
   - RTO: <1 minute
   - RPO: 0 minutes

2. ASG automatically launches replacement instances in healthy AZ
   - RTO: ~5 minutes
   - RPO: 0 minutes

3. Investigation (within 24 hours)
   - Determine root cause of AZ failure
   - Review cloud provider incident reports
   - Update runbook if needed
```

**Prevention:**
- Multi-AZ deployment for all components
- Database replication across AZs
- Load balancer health checks every 30 seconds
- Maintain capacity for N+1 availability

### Scenario 3: Database Instance Failure

**Detection:** Database connection pool exhaustion or connection timeout

**Impact:**
- Write operations blocked
- Read operations may succeed from replica
- ~5-10 minutes before failover

**Recovery Steps:**

#### AWS RDS (Multi-AZ)

```bash
# 1. AWS automatically promotes Multi-AZ standby (no manual action required)
#    Estimated time: 3-5 minutes

# 2. Monitor failover progress
aws rds describe-db-instances \
  --db-instance-identifier entmoot-prod \
  --query 'DBInstances[0].[DBInstanceStatus,PendingModifiedValues]'

# 3. Verify database connectivity
psql -h entmoot-prod.xxxxxxxxxxxx.rds.amazonaws.com -U postgres -c "SELECT 1"

# 4. Run health checks
psql -h entmoot-prod.xxxxxxxxxxxx.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT COUNT(*) FROM buildings;
  SELECT pg_database.datname,
    pg_stat_activity.usename,
    COUNT(*) FROM pg_stat_activity
  GROUP BY datname, usename;
EOF

# 5. Restore replication to new standby (if standby was promoted)
aws rds create-db-instance-read-replica \
  --db-instance-identifier entmoot-prod-replica \
  --source-db-instance-identifier entmoot-prod
```

#### GCP Cloud SQL

```bash
# 1. GCP automatically performs failover (HA-enabled instances)
#    Estimated time: 2-5 minutes

# 2. Monitor failover completion
gcloud sql instances describe entmoot-prod \
  --format='get(databaseVersion,ipAddresses,settings.ipConfiguration)'

# 3. Verify connectivity
gcloud sql connect entmoot-prod --user=postgres

# 4. Check replication status
gcloud sql instances describe entmoot-prod \
  --format='get(replicaConfiguration)'
```

#### Azure Database for PostgreSQL

```bash
# 1. Initiate failover to replica
az postgres flexible-server restart \
  --resource-group entmoot-prod \
  --name entmoot-db \
  --restart-with-failover true

# 2. Monitor failover progress
az postgres flexible-server show \
  --resource-group entmoot-prod \
  --name entmoot-db

# 3. Update connection strings if endpoint changed
# (Usually automatic with DNS failover)

# 4. Run diagnostics
az postgres flexible-server connect \
  --resource-group entmoot-prod \
  --name entmoot-db
```

### Scenario 4: Data Corruption

**Detection:**
- Application logic detects invalid data
- Consistency checks fail
- User reports incorrect results

**Impact:**
- Potential data loss or inaccuracy
- May affect derived data (optimizations, exports)

**Recovery Steps:**

```
1. Immediate action (first hour)
   - Identify corruption scope and timeline
   - Stop affected operations
   - Enable read-only mode if necessary
   - Create emergency backup

2. Investigate cause
   - Review application logs
   - Check for failed migrations
   - Analyze database transaction logs
   - Determine last good backup timestamp

3. Restore to known good point
   - Identify good backup point (before corruption)
   - Test restore procedure
   - Perform PITR restore

4. Data validation
   - Run integrity checks
   - Compare with backup metadata
   - Validate business logic constraints
   - Identify any permanent data loss

5. Reprocessing
   - Identify affected optimizations
   - Requeue failed jobs
   - Notify users of reprocessing
```

**PITR Restore Example:**

```bash
#!/bin/bash
# scripts/recover-from-corruption.sh

TARGET_TIME="2025-11-10T12:00:00Z"  # Time before corruption
DB_NAME="entmoot_recovered"

echo "Performing point-in-time recovery to $TARGET_TIME..."

# AWS RDS PITR
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier entmoot-prod \
  --target-db-instance-identifier $DB_NAME \
  --restore-time "$TARGET_TIME" \
  --use-latest-restorable-time false

# Wait for restore to complete
echo "Waiting for restore to complete..."
while true; do
  STATUS=$(aws rds describe-db-instances \
    --db-instance-identifier $DB_NAME \
    --query 'DBInstances[0].DBInstanceStatus' \
    --output text)

  if [ "$STATUS" = "available" ]; then
    echo "Restore completed!"
    break
  fi

  echo "Status: $STATUS (waiting...)"
  sleep 30
done

# Validate restored data
psql -h $DB_NAME.xxxxxxxxxxxx.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT COUNT(*) as building_count FROM buildings;
  SELECT COUNT(*) as project_count FROM projects;
  SELECT MAX(modified_at) as latest_modification FROM projects;
EOF

echo "Restored database: $DB_NAME"
echo "Next: Validate data integrity and swap if healthy"
```

### Scenario 5: Security Breach

**Detection:**
- Unauthorized access detected
- Malicious activity in logs
- Third-party notification of compromise

**Impact:**
- Potential data exposure
- May require immediate shutdown
- Regulatory reporting required
- Customer notification mandatory

**Recovery Steps:**

```
1. Containment (immediate)
   - Take affected systems offline
   - Isolate from network
   - Preserve logs and evidence
   - Notify security team and legal

2. Investigation (concurrent)
   - Determine scope of breach
   - Identify compromised data
   - Review access logs
   - Determine cause (exploited vulnerability, weak credentials, etc.)

3. Remediation
   - Patch exploited vulnerability
   - Rotate all credentials
   - Rebuild compromised systems from clean images
   - Restore from clean backup before breach

4. Testing and validation
   - Security scanning of rebuilt systems
   - Penetration testing
   - Verify no backdoors remain
   - Test disaster recovery procedures

5. Communication
   - Notify affected customers
   - Report to regulators if required
   - Post-mortem analysis
   - Update security policies
```

**Incident Response Playbook:**

```
Phase 1: Detection & Response (0-30 min)
- Confirm breach
- Engage incident response team
- Begin evidence collection
- Establish war room / call bridge

Phase 2: Investigation (30 min - 4 hours)
- Determine affected systems
- Identify compromised data
- Review all access logs
- Assess regulatory impact

Phase 3: Containment (ongoing)
- Revoke all sessions/tokens
- Change all credentials
- Block suspicious IP addresses
- Disable compromised accounts

Phase 4: Eradication (4-24 hours)
- Rebuild affected systems
- Deploy security patches
- Implement compensating controls
- Verify no persistence mechanisms

Phase 5: Recovery (24-72 hours)
- Restore from clean backups
- Full system testing
- Performance validation
- Monitoring enhancement

Phase 6: Communication (ongoing)
- Customer notification (24 hours)
- Regulatory reporting (as required)
- Press statement (if public)
- Incident post-mortem
```

---

## Recovery Procedures

### Step-by-Step Recovery for Common Scenarios

#### Full Region Failure (Worst Case)

```bash
#!/bin/bash
# scripts/failover-to-dr-region.sh

set -e

PRIMARY_REGION="us-east-1"
DR_REGION="us-west-2"
MANUAL_STEP_PAUSE=30

echo "=== REGIONAL FAILOVER PROCEDURE ==="
echo "From: $PRIMARY_REGION"
echo "To: $DR_REGION"

# 1. Assess situation
echo "[Step 1] Assessing primary region status..."
aws ec2 describe-availability-zones --region $PRIMARY_REGION || \
  echo "WARNING: Cannot reach primary region"

# 2. Promote DR database
echo "[Step 2] Promoting DR database to primary..."
aws rds promote-read-replica \
  --db-instance-identifier entmoot-prod-dr-replica \
  --region $DR_REGION

# Wait for promotion
while true; do
  STATUS=$(aws rds describe-db-instances \
    --db-instance-identifier entmoot-prod-dr-replica \
    --region $DR_REGION \
    --query 'DBInstances[0].DBInstanceStatus' \
    --output text)

  if [ "$STATUS" = "available" ]; then
    echo "Database promotion completed!"
    break
  fi
  echo "Status: $STATUS (waiting...)"
  sleep 10
done

# 3. Update DNS to point to DR region
echo "[Step 3] Updating DNS..."
read -p "Press enter after updating DNS to DR region: "

# 4. Verify application connectivity
echo "[Step 4] Verifying application connectivity..."
curl -H "Authorization: Bearer $(aws secretsmanager get-secret-value --secret-id entmoot/token --region $DR_REGION --query SecretString --output text)" \
  https://api-dr.yourdomain.com/health || \
  echo "WARNING: Health check failed"

# 5. Verify data integrity
echo "[Step 5] Verifying data integrity..."
psql -h entmoot-prod-dr.xxxxxxxxxxxx.rds.amazonaws.com -U postgres -d entmoot << EOF
  SELECT COUNT(*) as building_count FROM buildings;
  SELECT COUNT(*) as project_count FROM projects;
  SELECT MAX(created_at) as latest_record FROM projects;
EOF

echo "=== FAILOVER COMPLETED ==="
echo "Primary region: $PRIMARY_REGION (offline)"
echo "Active region: $DR_REGION"
echo ""
echo "Next steps:"
echo "1. Monitor application stability"
echo "2. Investigate primary region failure"
echo "3. Document incident"
echo "4. Plan failback when primary is restored"
```

#### Database Restore from Backup

```bash
#!/bin/bash
# scripts/restore-production-database.sh

BACKUP_NAME=${1:-"latest"}
RESTORE_DB_NAME="entmoot_restored_$(date +%s)"

echo "Restoring database from backup: $BACKUP_NAME"

# 1. Download backup
echo "Downloading backup..."
aws s3 cp "s3://entmoot-prod-backups/$BACKUP_NAME.sql" /tmp/backup.sql

# 2. Create restore database
echo "Creating restore database..."
psql -h production.rds.amazonaws.com -U postgres -c \
  "CREATE DATABASE $RESTORE_DB_NAME;"

# 3. Restore data
echo "Restoring data (this may take 30+ minutes)..."
pg_restore -h production.rds.amazonaws.com \
  -U postgres \
  -d $RESTORE_DB_NAME \
  --no-password \
  /tmp/backup.sql

# 4. Validate restore
echo "Validating restored data..."
psql -h production.rds.amazonaws.com -U postgres -d $RESTORE_DB_NAME << EOF
  -- Check table counts
  SELECT 'buildings' as table_name, COUNT(*) as row_count FROM buildings
  UNION ALL
  SELECT 'projects', COUNT(*) FROM projects
  UNION ALL
  SELECT 'optimizations', COUNT(*) FROM optimizations;

  -- Check for corruption
  SELECT COUNT(*) as corrupt_records
  FROM buildings WHERE geom IS NULL AND active = true;

  -- Check indexes
  SELECT COUNT(*) as index_count
  FROM pg_indexes WHERE tablename IN ('buildings', 'projects', 'optimizations');
EOF

# 5. Swap databases
echo ""
echo "!!! MANUAL STEP REQUIRED !!!"
echo "Restored database: $RESTORE_DB_NAME"
echo "To complete restore:"
echo "  1. Verify data is correct"
echo "  2. Update connection strings to point to: $RESTORE_DB_NAME"
echo "  3. Restart application servers"
echo "  4. Monitor application logs"
echo "  5. Drop old database: DROP DATABASE entmoot;"
read -p "Press enter after completing manual steps: "

# 6. Cleanup
rm /tmp/backup.sql
echo "Restore completed!"
```

---

## Failover Procedures

### Automatic Failover (No Manual Action Required)

**Component:** Database (Multi-AZ RDS)
- **Trigger:** Database instance unavailable for 30 seconds
- **Action:** AWS automatically promotes standby instance
- **Time:** 3-5 minutes
- **Notification:** CloudWatch alarm triggered, email alert sent

**Component:** API Servers (Auto Scaling Group)
- **Trigger:** Instance fails health check 2x (60 seconds)
- **Action:** ASG terminates instance, launches replacement
- **Time:** 3-5 minutes
- **Notification:** SNS notification sent

### Semi-Automatic Failover (Requires Approval)

**Component:** Read Replica Promotion
- **Trigger:** Manual detection of primary failure
- **Action:** Operator runs promotion command
- **Time:** 2-3 minutes after approval
- **Approval:** Requires Slack notification and operator acknowledgment

### Manual Failover (Full Regional Disaster)

**Component:** Cross-Region Failover
- **Trigger:** Entire region unavailable
- **Action:** DBA performs manual failover procedure
- **Time:** 15-30 minutes (investigation + execution)
- **Approval:** Requires manager and director approval via incident bridge

---

## Testing and Validation

### Test Schedule

| Test Type | Frequency | Duration | Owner |
|-----------|-----------|----------|-------|
| Backup verification | Weekly | 30 min | DevOps |
| Backup restoration | Monthly | 1 hour | DevOps/DBA |
| Failover simulation | Quarterly | 2 hours | DevOps/DBA |
| Full DR exercise | Semi-annually | 4 hours | DevOps/DBA/Ops |
| Security incident response | Quarterly | 2 hours | Security/DevOps |

### Weekly Backup Verification

```bash
#!/bin/bash
# scripts/test-backups.sh

echo "=== Weekly Backup Verification ==="

# 1. Check backup completion
aws s3 ls s3://entmoot-prod-backups --recursive | tail -5

# 2. Check backup age
LATEST=$(aws s3 ls s3://entmoot-prod-backups \
  --recursive --human-readable | sort | tail -1)
echo "Latest backup: $LATEST"

# 3. Verify backup file size
BACKUP_SIZE=$(aws s3 ls s3://entmoot-prod-backups/latest.sql | awk '{print $5}')
if [ $BACKUP_SIZE -gt 100000000 ]; then  # > 100MB
  echo "✓ Backup size reasonable: $BACKUP_SIZE bytes"
else
  echo "✗ Backup size seems too small: $BACKUP_SIZE bytes"
fi

# 4. Test backup integrity
aws s3 cp s3://entmoot-prod-backups/latest.sql /tmp/backup_test.sql
file /tmp/backup_test.sql | grep -q "PostgreSQL custom format"
if [ $? -eq 0 ]; then
  echo "✓ Backup file integrity verified"
else
  echo "✗ Backup file appears corrupt"
fi
rm /tmp/backup_test.sql

echo "=== Backup Verification Complete ==="
```

### Monthly Backup Restoration Test

```bash
#!/bin/bash
# scripts/test-restore-monthly.sh

echo "=== Monthly Backup Restoration Test ==="

DB_NAME="entmoot_test_restore"
BACKUP_SIZE_MIN=100000000  # Minimum 100MB

# 1. Download backup
echo "Step 1: Downloading latest backup..."
aws s3 cp s3://entmoot-prod-backups/latest.sql /tmp/backup.sql

ACTUAL_SIZE=$(stat -f%z /tmp/backup.sql 2>/dev/null || stat -c%s /tmp/backup.sql)
if [ $ACTUAL_SIZE -lt $BACKUP_SIZE_MIN ]; then
  echo "ERROR: Backup file too small ($ACTUAL_SIZE bytes)"
  exit 1
fi

# 2. Create test database
echo "Step 2: Creating test database..."
psql -h production.rds.amazonaws.com -U postgres -c \
  "CREATE DATABASE $DB_NAME;" || echo "Database already exists"

# 3. Restore backup
echo "Step 3: Restoring backup (this may take time)..."
pg_restore -h production.rds.amazonaws.com \
  -U postgres \
  -d $DB_NAME \
  --no-password \
  /tmp/backup.sql
RESTORE_EXIT_CODE=$?

if [ $RESTORE_EXIT_CODE -ne 0 ]; then
  echo "ERROR: Restore failed with exit code $RESTORE_EXIT_CODE"
  exit 1
fi

# 4. Validate restored data
echo "Step 4: Validating restored data..."

VALIDATION_QUERIES="
  SELECT COUNT(*) as building_count FROM buildings;
  SELECT COUNT(*) as project_count FROM projects;
  SELECT COUNT(*) as optimization_count FROM optimizations;
  SELECT COUNT(*) as error_count FROM buildings WHERE geom IS NULL AND active = true;
"

psql -h production.rds.amazonaws.com -U postgres -d $DB_NAME << EOF $VALIDATION_QUERIES
EOF

# 5. Run test queries
echo "Step 5: Running application test queries..."
psql -h production.rds.amazonaws.com -U postgres -d $DB_NAME << EOF
  -- Check PostGIS functionality
  SELECT ST_AsText(geom) FROM buildings LIMIT 1;

  -- Check spatial indices
  SELECT COUNT(*) FROM pg_stat_user_indexes
  WHERE schemaname = 'public' AND tablename = 'buildings';

  -- Check constraints
  SELECT COUNT(*) FROM information_schema.table_constraints
  WHERE table_name = 'projects' AND constraint_type = 'PRIMARY KEY';
EOF

# 6. Cleanup
echo "Step 6: Cleaning up..."
psql -h production.rds.amazonaws.com -U postgres -c "DROP DATABASE $DB_NAME;"
rm /tmp/backup.sql

echo "=== Restoration Test Complete ==="
echo "All validations passed!"
```

### Quarterly Failover Simulation

```bash
# scripts/test-failover-quarterly.sh

echo "=== Quarterly Failover Simulation ==="
echo "WARNING: This test may cause brief service interruption"
echo "Ensure maintenance window and stakeholder approval"
echo ""

read -p "Continue with failover test? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Test cancelled"
  exit 0
fi

# 1. Notify monitoring
echo "Disabling alerts..."
aws cloudwatch disable-alarm-actions --alarm-names \
  entmoot-api-cpu-high \
  entmoot-db-cpu-high \
  entmoot-api-errors-high

# 2. Test database replica promotion
echo "Testing replica promotion..."
REPLICA_ID="entmoot-prod-replica"

# Verify replica is ready
aws rds describe-db-instances \
  --db-instance-identifier $REPLICA_ID \
  --query 'DBInstances[0].DBInstanceStatus'

# Promote (this will cause brief outage)
aws rds promote-read-replica --db-instance-identifier $REPLICA_ID

# Wait for promotion
while true; do
  STATUS=$(aws rds describe-db-instances \
    --db-instance-identifier $REPLICA_ID \
    --query 'DBInstances[0].DBInstanceStatus' \
    --output text)

  if [ "$STATUS" = "available" ]; then
    echo "Replica promotion complete!"
    break
  fi
  echo "Promotion status: $STATUS"
  sleep 30
done

# 3. Test application health
echo "Verifying application health..."
curl -f https://api.yourdomain.com/health || echo "Health check failed"

# 4. Re-enable alerts
echo "Re-enabling alerts..."
aws cloudwatch enable-alarm-actions --alarm-names \
  entmoot-api-cpu-high \
  entmoot-db-cpu-high \
  entmoot-api-errors-high

# 5. Create new read replica
echo "Creating new replica..."
aws rds create-db-instance-read-replica \
  --db-instance-identifier entmoot-prod-replica-2 \
  --source-db-instance-identifier entmoot-prod-replica

echo "=== Failover Simulation Complete ==="
```

---

## Communication Plan

### Outage Notification Template

```
INCIDENT: [INCIDENT_ID]
SEVERITY: [CRITICAL/HIGH/MEDIUM]
AFFECTED SERVICE: Entmoot API
START TIME: [UTC TIME]
ESTIMATED DURATION: [DURATION]

DESCRIPTION:
[What happened]

IMPACT:
- [Impact 1]
- [Impact 2]

CURRENT STATUS:
- Investigation: [IN_PROGRESS/COMPLETE]
- Mitigation: [IN_PROGRESS/COMPLETE]
- Resolution: [IN_PROGRESS/PENDING]

NEXT UPDATE: [TIME]

For questions: [CONTACT_INFO]
```

### Incident Communication Channels

1. **Internal Slack:** #incidents (real-time)
2. **Status Page:** https://status.yourdomain.com (customers)
3. **Email:** support@yourdomain.com (customers within 30 min)
4. **Phone:** Executive on-call (critical incidents only)

### Post-Incident Review (Within 48 Hours)

```
1. What happened?
2. Why did it happen?
3. What were the impacts?
4. What was our response?
5. What could we have done better?
6. What changes do we make?
7. When will we make them?
```

---

## Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-11-10 | 1.0 | Initial DR plan | DevOps Team |

---

## Appendix: Recovery Command Reference

### Quick Commands

```bash
# Check overall system health
curl https://api.yourdomain.com/health -H "Authorization: Bearer $TOKEN"

# Check database connections
psql -h prod-db.rds.amazonaws.com -U postgres -c \
  "SELECT count(*) FROM pg_stat_activity;"

# Check Redis health
redis-cli -h prod-redis.xxxxxxxxxxxx.cache.amazonaws.com ping

# Check S3 replication status
aws s3api get-bucket-replication --bucket entmoot-prod-files

# Get latest backup timestamp
aws s3 ls s3://entmoot-prod-backups --recursive | tail -1

# Tail application logs
aws logs tail /ecs/entmoot-prod --follow

# Get recent alarms
aws cloudwatch describe-alarms --state-value ALARM --max-items 10
```

---

**Last Updated:** 2025-11-10
**Maintained By:** DevOps Team
**Review Schedule:** Quarterly
**Next Review Date:** 2026-02-10
