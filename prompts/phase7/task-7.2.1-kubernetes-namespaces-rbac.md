# Task 7.2.1: Kubernetes - Namespaces and RBAC

## Context

You are setting up Kubernetes infrastructure for ASWA at `/infrastructure/kubernetes/`. This task focuses on namespace organization and role-based access control.

## Objective

Create Kubernetes namespace and RBAC configurations that:
1. Define environment-specific namespaces
2. Implement least-privilege access
3. Configure service accounts
4. Set up role bindings
5. Enable workload identity

## Requirements

### 1. Create `/infrastructure/kubernetes/namespaces/development.yaml`
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: aswa-dev
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/environment: development
    istio-injection: disabled
  annotations:
    scheduler.alpha.kubernetes.io/defaultTolerations: |
      [{"operator": "Exists", "effect": "NoSchedule", "key": "environment", "value": "development"}]
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: aswa-dev-quota
  namespace: aswa-dev
spec:
  hard:
    requests.cpu: "8"
    requests.memory: 16Gi
    limits.cpu: "16"
    limits.memory: 32Gi
    pods: "50"
    services: "20"
    secrets: "50"
    configmaps: "50"
    persistentvolumeclaims: "20"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: aswa-dev-limits
  namespace: aswa-dev
spec:
  limits:
    - default:
        cpu: 500m
        memory: 512Mi
      defaultRequest:
        cpu: 100m
        memory: 128Mi
      max:
        cpu: "2"
        memory: 4Gi
      min:
        cpu: 50m
        memory: 64Mi
      type: Container
    - max:
        storage: 50Gi
      min:
        storage: 1Gi
      type: PersistentVolumeClaim
```

### 2. Create `/infrastructure/kubernetes/namespaces/staging.yaml`
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: aswa-staging
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/environment: staging
    istio-injection: enabled
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
  annotations:
    scheduler.alpha.kubernetes.io/defaultTolerations: |
      [{"operator": "Exists", "effect": "NoSchedule", "key": "environment", "value": "staging"}]
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: aswa-staging-quota
  namespace: aswa-staging
spec:
  hard:
    requests.cpu: "32"
    requests.memory: 64Gi
    limits.cpu: "64"
    limits.memory: 128Gi
    pods: "100"
    services: "30"
    secrets: "100"
    configmaps: "100"
    persistentvolumeclaims: "50"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: aswa-staging-limits
  namespace: aswa-staging
spec:
  limits:
    - default:
        cpu: 500m
        memory: 512Mi
      defaultRequest:
        cpu: 100m
        memory: 256Mi
      max:
        cpu: "4"
        memory: 8Gi
      min:
        cpu: 50m
        memory: 64Mi
      type: Container
    - max:
        storage: 100Gi
      min:
        storage: 1Gi
      type: PersistentVolumeClaim
```

### 3. Create `/infrastructure/kubernetes/namespaces/production.yaml`
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/environment: production
    istio-injection: enabled
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
  annotations:
    scheduler.alpha.kubernetes.io/defaultTolerations: |
      [{"operator": "Exists", "effect": "NoSchedule", "key": "environment", "value": "production"}]
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: aswa-prod-quota
  namespace: aswa-prod
spec:
  hard:
    requests.cpu: "128"
    requests.memory: 256Gi
    limits.cpu: "256"
    limits.memory: 512Gi
    pods: "500"
    services: "50"
    secrets: "200"
    configmaps: "200"
    persistentvolumeclaims: "100"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: aswa-prod-limits
  namespace: aswa-prod
spec:
  limits:
    - default:
        cpu: "1"
        memory: 1Gi
      defaultRequest:
        cpu: 200m
        memory: 512Mi
      max:
        cpu: "8"
        memory: 16Gi
      min:
        cpu: 100m
        memory: 128Mi
      type: Container
    - max:
        storage: 500Gi
      min:
        storage: 1Gi
      type: PersistentVolumeClaim
```

### 4. Create `/infrastructure/kubernetes/rbac/service-accounts.yaml`
```yaml
# API Gateway Service Account
apiVersion: v1
kind: ServiceAccount
metadata:
  name: aswa-api-gateway
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: api-gateway
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT_ID:role/aswa-api-gateway-role
---
# Ingestion Service Account
apiVersion: v1
kind: ServiceAccount
metadata:
  name: aswa-ingestion
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: ingestion
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT_ID:role/aswa-ingestion-role
---
# Query Service Account
apiVersion: v1
kind: ServiceAccount
metadata:
  name: aswa-query
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: query
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT_ID:role/aswa-query-role
---
# Insight Service Account
apiVersion: v1
kind: ServiceAccount
metadata:
  name: aswa-insight
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: insight
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT_ID:role/aswa-insight-role
---
# Batch Jobs Service Account
apiVersion: v1
kind: ServiceAccount
metadata:
  name: aswa-batch-jobs
  namespace: aswa-prod
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: batch
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT_ID:role/aswa-batch-role
```

### 5. Create `/infrastructure/kubernetes/rbac/roles.yaml`
```yaml
# Read-only role for services
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: aswa-reader
  namespace: aswa-prod
rules:
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["services", "endpoints"]
    verbs: ["get", "list", "watch"]
---
# Standard service role
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: aswa-service
  namespace: aswa-prod
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["aswa-secrets", "aswa-db-credentials"]
    verbs: ["get"]
  - apiGroups: [""]
    resources: ["services", "endpoints"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["coordination.k8s.io"]
    resources: ["leases"]
    verbs: ["get", "list", "watch", "create", "update", "delete"]
---
# Ingestion service role with additional permissions
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: aswa-ingestion-role
  namespace: aswa-prod
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["aswa-secrets", "aswa-db-credentials", "aswa-storage-credentials"]
    verbs: ["get"]
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["get", "list", "watch", "create", "delete"]
  - apiGroups: ["coordination.k8s.io"]
    resources: ["leases"]
    verbs: ["get", "list", "watch", "create", "update", "delete"]
---
# Batch jobs role
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: aswa-batch-role
  namespace: aswa-prod
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "list", "watch", "create", "update", "delete"]
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["aswa-secrets", "aswa-db-credentials", "aswa-storage-credentials"]
    verbs: ["get"]
  - apiGroups: ["batch"]
    resources: ["jobs", "cronjobs"]
    verbs: ["get", "list", "watch", "create", "update", "delete"]
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch", "delete"]
```

### 6. Create `/infrastructure/kubernetes/rbac/role-bindings.yaml`
```yaml
# API Gateway role binding
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: aswa-api-gateway-binding
  namespace: aswa-prod
subjects:
  - kind: ServiceAccount
    name: aswa-api-gateway
    namespace: aswa-prod
roleRef:
  kind: Role
  name: aswa-service
  apiGroup: rbac.authorization.k8s.io
---
# Ingestion role binding
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: aswa-ingestion-binding
  namespace: aswa-prod
subjects:
  - kind: ServiceAccount
    name: aswa-ingestion
    namespace: aswa-prod
roleRef:
  kind: Role
  name: aswa-ingestion-role
  apiGroup: rbac.authorization.k8s.io
---
# Query service role binding
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: aswa-query-binding
  namespace: aswa-prod
subjects:
  - kind: ServiceAccount
    name: aswa-query
    namespace: aswa-prod
roleRef:
  kind: Role
  name: aswa-service
  apiGroup: rbac.authorization.k8s.io
---
# Insight service role binding
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: aswa-insight-binding
  namespace: aswa-prod
subjects:
  - kind: ServiceAccount
    name: aswa-insight
    namespace: aswa-prod
roleRef:
  kind: Role
  name: aswa-service
  apiGroup: rbac.authorization.k8s.io
---
# Batch jobs role binding
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: aswa-batch-binding
  namespace: aswa-prod
subjects:
  - kind: ServiceAccount
    name: aswa-batch-jobs
    namespace: aswa-prod
roleRef:
  kind: Role
  name: aswa-batch-role
  apiGroup: rbac.authorization.k8s.io
```

### 7. Create `/infrastructure/kubernetes/rbac/cluster-roles.yaml`
```yaml
# Cluster role for monitoring
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: aswa-monitoring
  labels:
    app.kubernetes.io/name: aswa
rules:
  - apiGroups: [""]
    resources: ["nodes", "nodes/metrics", "pods", "services", "endpoints"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get"]
  - nonResourceURLs: ["/metrics", "/metrics/cadvisor"]
    verbs: ["get"]
---
# Cluster role for external secrets operator
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: aswa-external-secrets
  labels:
    app.kubernetes.io/name: aswa
rules:
  - apiGroups: ["external-secrets.io"]
    resources: ["externalsecrets", "secretstores", "clustersecretstores"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "list", "watch", "create", "update", "delete"]
---
# Cluster role for cert-manager integration
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: aswa-cert-manager
  labels:
    app.kubernetes.io/name: aswa
rules:
  - apiGroups: ["cert-manager.io"]
    resources: ["certificates", "certificaterequests", "issuers", "clusterissuers"]
    verbs: ["get", "list", "watch", "create", "update", "delete"]
```

### 8. Create `/infrastructure/kubernetes/rbac/developer-access.yaml`
```yaml
# Developer read-only access to staging
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: developer-readonly
  namespace: aswa-staging
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "services", "endpoints", "configmaps"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets", "statefulsets"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["batch"]
    resources: ["jobs", "cronjobs"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["networking.k8s.io"]
    resources: ["ingresses"]
    verbs: ["get", "list", "watch"]
---
# Developer full access to development
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: developer-full
  namespace: aswa-dev
rules:
  - apiGroups: ["", "apps", "batch", "networking.k8s.io", "autoscaling"]
    resources: ["*"]
    verbs: ["*"]
---
# SRE access to production
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: sre-access
  namespace: aswa-prod
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "pods/exec", "services", "endpoints", "configmaps", "events"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["delete"]  # For pod restarts
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets", "statefulsets"]
    verbs: ["get", "list", "watch", "patch"]  # Patch for scaling
  - apiGroups: ["apps"]
    resources: ["deployments/scale", "statefulsets/scale"]
    verbs: ["get", "update", "patch"]
  - apiGroups: ["batch"]
    resources: ["jobs", "cronjobs"]
    verbs: ["get", "list", "watch", "create", "delete"]
  - apiGroups: ["autoscaling"]
    resources: ["horizontalpodautoscalers"]
    verbs: ["get", "list", "watch", "patch"]
```

## Verification

1. Apply namespace configurations: `kubectl apply -f infrastructure/kubernetes/namespaces/`
2. Apply RBAC configurations: `kubectl apply -f infrastructure/kubernetes/rbac/`
3. Verify service accounts: `kubectl get serviceaccounts -n aswa-prod`
4. Test role bindings: `kubectl auth can-i --list --as=system:serviceaccount:aswa-prod:aswa-api-gateway -n aswa-prod`
5. Verify resource quotas: `kubectl describe resourcequota -n aswa-prod`
