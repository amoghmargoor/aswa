# Task 7.2.3: Kubernetes - Persistent Volumes

## Context

You are setting up Kubernetes infrastructure for ASWA at `/infrastructure/kubernetes/`. Network policies are complete. Now we need persistent storage configurations.

## Objective

Create persistent volume configurations that:
1. Define storage classes for different needs
2. Configure persistent volume claims
3. Support dynamic provisioning
4. Enable backup-friendly storage
5. Handle multi-AZ deployments

## Requirements

### 1. Create `/infrastructure/kubernetes/storage/storage-classes.yaml`
```yaml
# Standard SSD storage class
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: aswa-ssd
  labels:
    app.kubernetes.io/name: aswa
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
  encrypted: "true"
  kmsKeyId: alias/aswa-ebs-key
reclaimPolicy: Retain
allowVolumeExpansion: true
volumeBindingMode: WaitForFirstConsumer
---
# High-performance SSD storage class
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: aswa-ssd-fast
  labels:
    app.kubernetes.io/name: aswa
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  iops: "16000"
  throughput: "1000"
  encrypted: "true"
  kmsKeyId: alias/aswa-ebs-key
reclaimPolicy: Retain
allowVolumeExpansion: true
volumeBindingMode: WaitForFirstConsumer
---
# Provisioned IOPS storage class for databases
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: aswa-ssd-io1
  labels:
    app.kubernetes.io/name: aswa
provisioner: ebs.csi.aws.com
parameters:
  type: io2
  iops: "32000"
  encrypted: "true"
  kmsKeyId: alias/aswa-ebs-key
reclaimPolicy: Retain
allowVolumeExpansion: true
volumeBindingMode: WaitForFirstConsumer
---
# Standard storage class for backups
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: aswa-standard
  labels:
    app.kubernetes.io/name: aswa
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  encrypted: "true"
  kmsKeyId: alias/aswa-ebs-key
reclaimPolicy: Retain
allowVolumeExpansion: true
volumeBindingMode: WaitForFirstConsumer
---
# EFS storage class for shared storage
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: aswa-efs
  labels:
    app.kubernetes.io/name: aswa
provisioner: efs.csi.aws.com
parameters:
  provisioningMode: efs-ap
  fileSystemId: fs-xxxxxxxxx  # Replace with actual EFS ID
  directoryPerms: "700"
  uid: "1000"
  gid: "1000"
reclaimPolicy: Retain
volumeBindingMode: Immediate
```

### 2. Create `/infrastructure/kubernetes/storage/postgresql-pvc.yaml`
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgresql-data
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: postgresql
  annotations:
    # Enable volume snapshots
    snapshot.storage.kubernetes.io/is-default-class: "true"
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: aswa-ssd-io1
  resources:
    requests:
      storage: 100Gi
---
# PostgreSQL WAL storage
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgresql-wal
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: postgresql
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: aswa-ssd-fast
  resources:
    requests:
      storage: 20Gi
```

### 3. Create `/infrastructure/kubernetes/storage/elasticsearch-pvc.yaml`
```yaml
# Elasticsearch master node storage
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: elasticsearch-master-0
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: elasticsearch
    elasticsearch.node.role: master
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: aswa-ssd
  resources:
    requests:
      storage: 20Gi
---
# Elasticsearch data node storage (template for StatefulSet)
# These PVCs are created by the StatefulSet
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: elasticsearch-data-0
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: elasticsearch
    elasticsearch.node.role: data
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: aswa-ssd-fast
  resources:
    requests:
      storage: 500Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: elasticsearch-data-1
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: elasticsearch
    elasticsearch.node.role: data
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: aswa-ssd-fast
  resources:
    requests:
      storage: 500Gi
```

### 4. Create `/infrastructure/kubernetes/storage/redis-pvc.yaml`
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-data
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: redis
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: aswa-ssd
  resources:
    requests:
      storage: 10Gi
```

### 5. Create `/infrastructure/kubernetes/storage/shared-storage.yaml`
```yaml
# Shared storage for document uploads (temporary)
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: aswa-uploads
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: shared-storage
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: aswa-efs
  resources:
    requests:
      storage: 100Gi
---
# Shared cache storage
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: aswa-cache
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: shared-storage
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: aswa-efs
  resources:
    requests:
      storage: 50Gi
```

### 6. Create `/infrastructure/kubernetes/storage/volume-snapshots.yaml`
```yaml
# Volume snapshot class for backups
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: aswa-snapshot
  labels:
    app.kubernetes.io/name: aswa
  annotations:
    snapshot.storage.kubernetes.io/is-default-class: "true"
driver: ebs.csi.aws.com
deletionPolicy: Retain
parameters:
  tagSpecification_1: "Name=aswa-backup"
  tagSpecification_2: "Environment=production"
---
# PostgreSQL daily snapshot
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: postgresql-snapshot-template
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: postgresql
    backup-type: scheduled
spec:
  volumeSnapshotClassName: aswa-snapshot
  source:
    persistentVolumeClaimName: postgresql-data
---
# Elasticsearch snapshot
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: elasticsearch-snapshot-template
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: elasticsearch
    backup-type: scheduled
spec:
  volumeSnapshotClassName: aswa-snapshot
  source:
    persistentVolumeClaimName: elasticsearch-data-0
```

### 7. Create `/infrastructure/kubernetes/storage/backup-cronjob.yaml`
```yaml
# CronJob for creating volume snapshots
apiVersion: batch/v1
kind: CronJob
metadata:
  name: volume-backup
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: backup
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        metadata:
          labels:
            app.kubernetes.io/name: aswa
            app.kubernetes.io/component: backup
        spec:
          serviceAccountName: aswa-backup
          restartPolicy: OnFailure
          containers:
            - name: backup
              image: bitnami/kubectl:latest
              command:
                - /bin/bash
                - -c
                - |
                  set -e

                  DATE=$(date +%Y%m%d-%H%M%S)

                  # Create PostgreSQL snapshot
                  cat <<EOF | kubectl apply -f -
                  apiVersion: snapshot.storage.k8s.io/v1
                  kind: VolumeSnapshot
                  metadata:
                    name: postgresql-snapshot-${DATE}
                    namespace: aswa-prod
                    labels:
                      app.kubernetes.io/name: aswa
                      app.kubernetes.io/component: postgresql
                      backup-date: "${DATE}"
                  spec:
                    volumeSnapshotClassName: aswa-snapshot
                    source:
                      persistentVolumeClaimName: postgresql-data
                  EOF

                  echo "PostgreSQL snapshot created: postgresql-snapshot-${DATE}"

                  # Create Elasticsearch snapshots
                  for i in 0 1; do
                    cat <<EOF | kubectl apply -f -
                  apiVersion: snapshot.storage.k8s.io/v1
                  kind: VolumeSnapshot
                  metadata:
                    name: elasticsearch-data-${i}-snapshot-${DATE}
                    namespace: aswa-prod
                    labels:
                      app.kubernetes.io/name: aswa
                      app.kubernetes.io/component: elasticsearch
                      backup-date: "${DATE}"
                  spec:
                    volumeSnapshotClassName: aswa-snapshot
                    source:
                      persistentVolumeClaimName: elasticsearch-data-${i}
                  EOF
                    echo "Elasticsearch snapshot created: elasticsearch-data-${i}-snapshot-${DATE}"
                  done

                  # Cleanup old snapshots (keep last 7 days)
                  CUTOFF_DATE=$(date -d '7 days ago' +%Y%m%d)

                  kubectl get volumesnapshots -n aswa-prod -o json | \
                    jq -r ".items[] | select(.metadata.labels[\"backup-date\"] != null) | select(.metadata.labels[\"backup-date\"] < \"${CUTOFF_DATE}\") | .metadata.name" | \
                    xargs -r -I {} kubectl delete volumesnapshot {} -n aswa-prod

                  echo "Backup job completed successfully"
              resources:
                requests:
                  cpu: 100m
                  memory: 128Mi
                limits:
                  cpu: 200m
                  memory: 256Mi
---
# Service account for backup job
apiVersion: v1
kind: ServiceAccount
metadata:
  name: aswa-backup
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: backup
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: aswa-backup-role
  namespace: aswa-prod
rules:
  - apiGroups: ["snapshot.storage.k8s.io"]
    resources: ["volumesnapshots"]
    verbs: ["get", "list", "watch", "create", "delete"]
  - apiGroups: [""]
    resources: ["persistentvolumeclaims"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: aswa-backup-binding
  namespace: aswa-prod
subjects:
  - kind: ServiceAccount
    name: aswa-backup
    namespace: aswa-prod
roleRef:
  kind: Role
  name: aswa-backup-role
  apiGroup: rbac.authorization.k8s.io
```

### 8. Create `/infrastructure/kubernetes/storage/restore-job.yaml`
```yaml
# Job template for restoring from snapshot
apiVersion: batch/v1
kind: Job
metadata:
  name: restore-postgresql
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: restore
spec:
  ttlSecondsAfterFinished: 86400
  template:
    spec:
      serviceAccountName: aswa-backup
      restartPolicy: Never
      containers:
        - name: restore
          image: bitnami/kubectl:latest
          env:
            - name: SNAPSHOT_NAME
              value: "postgresql-snapshot-20240115-020000"  # Set to actual snapshot name
          command:
            - /bin/bash
            - -c
            - |
              set -e

              echo "Creating PVC from snapshot: ${SNAPSHOT_NAME}"

              # Create new PVC from snapshot
              cat <<EOF | kubectl apply -f -
              apiVersion: v1
              kind: PersistentVolumeClaim
              metadata:
                name: postgresql-data-restored
                namespace: aswa-prod
                labels:
                  app.kubernetes.io/name: aswa
                  app.kubernetes.io/component: postgresql
                  restored-from: "${SNAPSHOT_NAME}"
              spec:
                accessModes:
                  - ReadWriteOnce
                storageClassName: aswa-ssd-io1
                resources:
                  requests:
                    storage: 100Gi
                dataSource:
                  name: ${SNAPSHOT_NAME}
                  kind: VolumeSnapshot
                  apiGroup: snapshot.storage.k8s.io
              EOF

              echo "Waiting for PVC to be bound..."
              kubectl wait --for=jsonpath='{.status.phase}'=Bound pvc/postgresql-data-restored -n aswa-prod --timeout=600s

              echo "Restore PVC created successfully"
              echo "To complete restore:"
              echo "1. Scale down PostgreSQL: kubectl scale statefulset postgresql --replicas=0 -n aswa-prod"
              echo "2. Rename PVCs or update StatefulSet to use restored PVC"
              echo "3. Scale up PostgreSQL: kubectl scale statefulset postgresql --replicas=1 -n aswa-prod"
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 200m
              memory: 256Mi
```

## Verification

1. Apply storage classes: `kubectl apply -f infrastructure/kubernetes/storage/storage-classes.yaml`
2. Apply PVCs: `kubectl apply -f infrastructure/kubernetes/storage/`
3. Verify PVCs are bound: `kubectl get pvc -n aswa-prod`
4. Test snapshot creation: `kubectl apply -f infrastructure/kubernetes/storage/volume-snapshots.yaml`
5. Verify backup CronJob: `kubectl get cronjobs -n aswa-prod`
