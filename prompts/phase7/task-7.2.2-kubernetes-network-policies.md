# Task 7.2.2: Kubernetes - Network Policies

## Context

You are setting up Kubernetes infrastructure for ASWA at `/infrastructure/kubernetes/`. Namespaces and RBAC are complete. Now we need network policies for security.

## Objective

Create network policies that:
1. Implement zero-trust networking
2. Restrict pod-to-pod communication
3. Allow only necessary traffic
4. Enable external access where needed
5. Support monitoring and observability

## Requirements

### 1. Create `/infrastructure/kubernetes/network-policies/default-deny.yaml`
```yaml
# Default deny all ingress traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: aswa-prod
spec:
  podSelector: {}
  policyTypes:
    - Ingress
---
# Default deny all egress traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-egress
  namespace: aswa-prod
spec:
  podSelector: {}
  policyTypes:
    - Egress
---
# Allow DNS for all pods
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: aswa-prod
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

### 2. Create `/infrastructure/kubernetes/network-policies/api-gateway.yaml`
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-gateway-ingress
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: api-gateway
  policyTypes:
    - Ingress
  ingress:
    # Allow from ingress controller
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
          podSelector:
            matchLabels:
              app.kubernetes.io/name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8000
    # Allow from other ASWA services (for health checks)
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: aswa
      ports:
        - protocol: TCP
          port: 8000
    # Allow Prometheus scraping
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: monitoring
          podSelector:
            matchLabels:
              app.kubernetes.io/name: prometheus
      ports:
        - protocol: TCP
          port: 9090
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-gateway-egress
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: api-gateway
  policyTypes:
    - Egress
  egress:
    # Allow to ingestion service
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: ingestion
      ports:
        - protocol: TCP
          port: 8001
    # Allow to query service
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: query
      ports:
        - protocol: TCP
          port: 8002
    # Allow to insight service
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: insight
      ports:
        - protocol: TCP
          port: 8003
    # Allow to Redis
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: redis
      ports:
        - protocol: TCP
          port: 6379
    # Allow external Redis (ElastiCache)
    - to:
        - ipBlock:
            cidr: 10.0.0.0/8
      ports:
        - protocol: TCP
          port: 6379
```

### 3. Create `/infrastructure/kubernetes/network-policies/ingestion-service.yaml`
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ingestion-ingress
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: ingestion
  policyTypes:
    - Ingress
  ingress:
    # Allow from API gateway
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: api-gateway
      ports:
        - protocol: TCP
          port: 8001
    # Allow from batch jobs
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: batch
      ports:
        - protocol: TCP
          port: 8001
    # Allow Prometheus scraping
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: monitoring
          podSelector:
            matchLabels:
              app.kubernetes.io/name: prometheus
      ports:
        - protocol: TCP
          port: 9090
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ingestion-egress
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: ingestion
  policyTypes:
    - Egress
  egress:
    # Allow to PostgreSQL
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: postgresql
      ports:
        - protocol: TCP
          port: 5432
    # Allow external PostgreSQL (RDS)
    - to:
        - ipBlock:
            cidr: 10.0.0.0/8
      ports:
        - protocol: TCP
          port: 5432
    # Allow to Redis
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: redis
      ports:
        - protocol: TCP
          port: 6379
    # Allow external Redis (ElastiCache)
    - to:
        - ipBlock:
            cidr: 10.0.0.0/8
      ports:
        - protocol: TCP
          port: 6379
    # Allow to Elasticsearch
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: elasticsearch
      ports:
        - protocol: TCP
          port: 9200
    # Allow external Elasticsearch (OpenSearch)
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 169.254.169.254/32  # Block metadata service
      ports:
        - protocol: TCP
          port: 443
    # Allow to S3 (via VPC endpoint or NAT)
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 169.254.169.254/32
      ports:
        - protocol: TCP
          port: 443
    # Allow to insight service
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: insight
      ports:
        - protocol: TCP
          port: 8003
```

### 4. Create `/infrastructure/kubernetes/network-policies/query-service.yaml`
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: query-ingress
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: query
  policyTypes:
    - Ingress
  ingress:
    # Allow from API gateway
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: api-gateway
      ports:
        - protocol: TCP
          port: 8002
    # Allow Prometheus scraping
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: monitoring
          podSelector:
            matchLabels:
              app.kubernetes.io/name: prometheus
      ports:
        - protocol: TCP
          port: 9090
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: query-egress
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: query
  policyTypes:
    - Egress
  egress:
    # Allow to PostgreSQL
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: postgresql
      ports:
        - protocol: TCP
          port: 5432
    # Allow external PostgreSQL (RDS)
    - to:
        - ipBlock:
            cidr: 10.0.0.0/8
      ports:
        - protocol: TCP
          port: 5432
    # Allow to Redis
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: redis
      ports:
        - protocol: TCP
          port: 6379
    # Allow to Elasticsearch
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: elasticsearch
      ports:
        - protocol: TCP
          port: 9200
    # Allow to LLM APIs (OpenAI, Anthropic)
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 169.254.169.254/32
              - 10.0.0.0/8
              - 172.16.0.0/12
              - 192.168.0.0/16
      ports:
        - protocol: TCP
          port: 443
```

### 5. Create `/infrastructure/kubernetes/network-policies/insight-service.yaml`
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: insight-ingress
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: insight
  policyTypes:
    - Ingress
  ingress:
    # Allow from API gateway
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: api-gateway
      ports:
        - protocol: TCP
          port: 8003
    # Allow from ingestion service
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: ingestion
      ports:
        - protocol: TCP
          port: 8003
    # Allow Prometheus scraping
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: monitoring
          podSelector:
            matchLabels:
              app.kubernetes.io/name: prometheus
      ports:
        - protocol: TCP
          port: 9090
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: insight-egress
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: insight
  policyTypes:
    - Egress
  egress:
    # Allow to PostgreSQL
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: postgresql
      ports:
        - protocol: TCP
          port: 5432
    # Allow external PostgreSQL
    - to:
        - ipBlock:
            cidr: 10.0.0.0/8
      ports:
        - protocol: TCP
          port: 5432
    # Allow to Redis
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: redis
      ports:
        - protocol: TCP
          port: 6379
    # Allow to Elasticsearch
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: elasticsearch
      ports:
        - protocol: TCP
          port: 9200
```

### 6. Create `/infrastructure/kubernetes/network-policies/web-dashboard.yaml`
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: web-ingress
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: web
  policyTypes:
    - Ingress
  ingress:
    # Allow from ingress controller only
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
          podSelector:
            matchLabels:
              app.kubernetes.io/name: ingress-nginx
      ports:
        - protocol: TCP
          port: 80
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: web-egress
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: web
  policyTypes:
    - Egress
  # No egress needed - static content served by nginx
  egress: []
```

### 7. Create `/infrastructure/kubernetes/network-policies/databases.yaml`
```yaml
# PostgreSQL network policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: postgresql-ingress
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: postgresql
  policyTypes:
    - Ingress
  ingress:
    # Allow from ASWA services
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: aswa
      ports:
        - protocol: TCP
          port: 5432
---
# Redis network policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: redis-ingress
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: redis
  policyTypes:
    - Ingress
  ingress:
    # Allow from ASWA services
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: aswa
      ports:
        - protocol: TCP
          port: 6379
---
# Elasticsearch network policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: elasticsearch-ingress
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: elasticsearch
  policyTypes:
    - Ingress
  ingress:
    # Allow from ASWA services
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: aswa
      ports:
        - protocol: TCP
          port: 9200
    # Allow internal cluster communication
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: elasticsearch
      ports:
        - protocol: TCP
          port: 9300
```

### 8. Create `/infrastructure/kubernetes/network-policies/monitoring.yaml`
```yaml
# Allow monitoring namespace to scrape metrics
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-prometheus-scraping
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: aswa
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: monitoring
          podSelector:
            matchLabels:
              app.kubernetes.io/name: prometheus
      ports:
        - protocol: TCP
          port: 9090
---
# Allow Jaeger tracing
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-jaeger-tracing
  namespace: aswa-prod
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: aswa
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: observability
          podSelector:
            matchLabels:
              app.kubernetes.io/name: jaeger
      ports:
        - protocol: TCP
          port: 14268
        - protocol: UDP
          port: 6831
```

## Verification

1. Apply network policies: `kubectl apply -f infrastructure/kubernetes/network-policies/`
2. Verify policies: `kubectl get networkpolicies -n aswa-prod`
3. Test connectivity between services
4. Verify external access is blocked where expected
5. Test Prometheus can scrape metrics
