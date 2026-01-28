# Task 7.1.3: Helm Charts - Environment Values

## Context

You are working on ASWA Helm charts at `/infrastructure/helm/`. Base chart and service charts are complete. Now we need environment-specific value files.

## Objective

Create environment-specific values files that:
1. Configure development environment
2. Configure staging environment
3. Configure production environment
4. Support external services
5. Enable proper security settings

## Requirements

### 1. Create `/infrastructure/helm/charts/aswa/values-dev.yaml`
```yaml
# Development environment values
environment: development

# Image settings
image:
  registry: ghcr.io
  pullPolicy: Always
  tag: "dev"

# Reduced replicas for development
apiGateway:
  enabled: true
  replicaCount: 1
  autoscaling:
    enabled: false
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi
  ingress:
    enabled: true
    className: nginx
    hosts:
      - host: api.aswa.dev
        paths:
          - path: /
            pathType: Prefix

ingestionService:
  enabled: true
  replicaCount: 1
  autoscaling:
    enabled: false
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 1Gi

queryService:
  enabled: true
  replicaCount: 1
  autoscaling:
    enabled: false
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 1Gi

insightService:
  enabled: true
  replicaCount: 1
  autoscaling:
    enabled: false
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 1Gi

webDashboard:
  enabled: true
  replicaCount: 1
  resources:
    requests:
      cpu: 25m
      memory: 32Mi
    limits:
      cpu: 100m
      memory: 64Mi
  ingress:
    enabled: true
    className: nginx
    hosts:
      - host: app.aswa.dev
        paths:
          - path: /
            pathType: Prefix

# In-cluster dependencies
postgresql:
  enabled: true
  auth:
    postgresPassword: "dev-password"
    database: aswa_dev
  primary:
    persistence:
      enabled: true
      size: 5Gi
  metrics:
    enabled: false

redis:
  enabled: true
  auth:
    enabled: true
    password: "dev-redis-password"
  master:
    persistence:
      enabled: true
      size: 1Gi
  replica:
    replicaCount: 0
  metrics:
    enabled: false

elasticsearch:
  enabled: true
  master:
    replicaCount: 1
    persistence:
      enabled: true
      size: 5Gi
  data:
    replicaCount: 1
    persistence:
      enabled: true
      size: 10Gi
  metrics:
    enabled: false

# Logging
logLevel: DEBUG
logFormat: text

# Security - relaxed for development
podSecurityContext:
  fsGroup: 1000
  runAsNonRoot: false
  runAsUser: 1000

securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  readOnlyRootFilesystem: false

# Network policies disabled for development
networkPolicies:
  enabled: false

# Pod disruption budgets disabled
podDisruptionBudget:
  enabled: false

# Monitoring
monitoring:
  enabled: true
  serviceMonitor:
    enabled: false
  prometheusRule:
    enabled: false

# Feature flags
featureFlags:
  enableDebugEndpoints: true
  enableSwaggerUI: true
  enableProfiling: true
```

### 2. Create `/infrastructure/helm/charts/aswa/values-staging.yaml`
```yaml
# Staging environment values
environment: staging

# Image settings
image:
  registry: ghcr.io
  pullPolicy: Always
  tag: "staging"

# Moderate replicas for staging
apiGateway:
  enabled: true
  replicaCount: 2
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 5
    targetCPUUtilizationPercentage: 70
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 512Mi
  ingress:
    enabled: true
    className: nginx
    annotations:
      nginx.ingress.kubernetes.io/proxy-body-size: "50m"
      cert-manager.io/cluster-issuer: letsencrypt-staging
    hosts:
      - host: api.staging.aswa.io
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: api-staging-tls
        hosts:
          - api.staging.aswa.io

ingestionService:
  enabled: true
  replicaCount: 2
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 60
  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 2Gi

queryService:
  enabled: true
  replicaCount: 2
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 8
    targetCPUUtilizationPercentage: 70
  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 2Gi

insightService:
  enabled: true
  replicaCount: 2
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 5
    targetCPUUtilizationPercentage: 70
  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 2Gi

webDashboard:
  enabled: true
  replicaCount: 2
  resources:
    requests:
      cpu: 50m
      memory: 64Mi
    limits:
      cpu: 200m
      memory: 128Mi
  ingress:
    enabled: true
    className: nginx
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt-staging
    hosts:
      - host: app.staging.aswa.io
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: app-staging-tls
        hosts:
          - app.staging.aswa.io

# In-cluster dependencies
postgresql:
  enabled: true
  auth:
    existingSecret: aswa-staging-db-credentials
    database: aswa_staging
  primary:
    persistence:
      enabled: true
      size: 20Gi
  metrics:
    enabled: true

redis:
  enabled: true
  auth:
    enabled: true
    existingSecret: aswa-staging-redis-credentials
  master:
    persistence:
      enabled: true
      size: 5Gi
  replica:
    replicaCount: 1
  metrics:
    enabled: true

elasticsearch:
  enabled: true
  master:
    replicaCount: 1
    persistence:
      enabled: true
      size: 20Gi
  data:
    replicaCount: 2
    persistence:
      enabled: true
      size: 50Gi
  metrics:
    enabled: true

# Logging
logLevel: INFO
logFormat: json

# Security
podSecurityContext:
  fsGroup: 1000
  runAsNonRoot: true
  runAsUser: 1000

securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  readOnlyRootFilesystem: true

# Network policies enabled
networkPolicies:
  enabled: true

# Pod disruption budgets enabled
podDisruptionBudget:
  enabled: true
  minAvailable: 1

# Monitoring
monitoring:
  enabled: true
  serviceMonitor:
    enabled: true
    interval: 30s
  prometheusRule:
    enabled: true

# External secrets
externalSecrets:
  enabled: true
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore

# Feature flags
featureFlags:
  enableDebugEndpoints: false
  enableSwaggerUI: true
  enableProfiling: false
```

### 3. Create `/infrastructure/helm/charts/aswa/values-prod.yaml`
```yaml
# Production environment values
environment: production

# Image settings
image:
  registry: ghcr.io
  pullPolicy: IfNotPresent
  # tag should be set during deployment

# Production replicas with autoscaling
apiGateway:
  enabled: true
  replicaCount: 3
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20
    targetCPUUtilizationPercentage: 70
    targetMemoryUtilizationPercentage: 80
  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 1Gi
  ingress:
    enabled: true
    className: nginx
    annotations:
      nginx.ingress.kubernetes.io/proxy-body-size: "50m"
      nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
      nginx.ingress.kubernetes.io/rate-limit: "100"
      nginx.ingress.kubernetes.io/rate-limit-window: "1m"
      cert-manager.io/cluster-issuer: letsencrypt-prod
    hosts:
      - host: api.aswa.io
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: api-prod-tls
        hosts:
          - api.aswa.io
  nodeSelector:
    node-type: application
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          podAffinityTerm:
            labelSelector:
              matchLabels:
                app.kubernetes.io/component: api-gateway
            topologyKey: kubernetes.io/hostname
  tolerations: []

ingestionService:
  enabled: true
  replicaCount: 3
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 30
    targetCPUUtilizationPercentage: 60
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 4Gi
  workerConcurrency: "8"
  nodeSelector:
    node-type: compute
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          podAffinityTerm:
            labelSelector:
              matchLabels:
                app.kubernetes.io/component: ingestion
            topologyKey: kubernetes.io/hostname

queryService:
  enabled: true
  replicaCount: 3
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20
    targetCPUUtilizationPercentage: 70
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 4Gi
  llmTimeout: "120"
  nodeSelector:
    node-type: application
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          podAffinityTerm:
            labelSelector:
              matchLabels:
                app.kubernetes.io/component: query
            topologyKey: kubernetes.io/hostname

insightService:
  enabled: true
  replicaCount: 3
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 15
    targetCPUUtilizationPercentage: 70
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 4Gi
  nodeSelector:
    node-type: application
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          podAffinityTerm:
            labelSelector:
              matchLabels:
                app.kubernetes.io/component: insight
            topologyKey: kubernetes.io/hostname

webDashboard:
  enabled: true
  replicaCount: 3
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 256Mi
  ingress:
    enabled: true
    className: nginx
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt-prod
      nginx.ingress.kubernetes.io/configuration-snippet: |
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
    hosts:
      - host: app.aswa.io
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: app-prod-tls
        hosts:
          - app.aswa.io
  nodeSelector:
    node-type: application

# External managed databases in production
postgresql:
  enabled: false

externalDatabase:
  url: "" # Set via external secret
  host: aswa-prod.cluster-xxxxx.us-east-1.rds.amazonaws.com
  port: 5432
  database: aswa_prod
  sslMode: require

redis:
  enabled: false

externalRedis:
  url: "" # Set via external secret
  host: aswa-prod.xxxxx.ng.0001.use1.cache.amazonaws.com
  port: 6379
  tls: true

elasticsearch:
  enabled: false

externalElasticsearch:
  url: "" # Set via external secret
  hosts:
    - https://aswa-prod-es.us-east-1.es.amazonaws.com:443
  username: "" # Set via external secret
  password: "" # Set via external secret

# Logging
logLevel: INFO
logFormat: json

# Strict security context
podSecurityContext:
  fsGroup: 1000
  runAsNonRoot: true
  runAsUser: 1000
  seccompProfile:
    type: RuntimeDefault

securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000

# Network policies enabled
networkPolicies:
  enabled: true

# Pod disruption budgets
podDisruptionBudget:
  enabled: true
  minAvailable: 2

# Monitoring
monitoring:
  enabled: true
  serviceMonitor:
    enabled: true
    interval: 15s
  prometheusRule:
    enabled: true

# Tracing
tracing:
  enabled: true
  samplingRate: 0.1
  endpoint: "http://jaeger-collector.observability:14268/api/traces"

# External secrets from AWS Secrets Manager
externalSecrets:
  enabled: true
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore

# LLM configuration
llm:
  provider: anthropic
  model: claude-3-sonnet-20240229
  maxTokens: 4096
  temperature: 0.7

# Storage
storage:
  provider: s3
  bucket: aswa-prod-documents
  region: us-east-1

# Feature flags
featureFlags:
  enableDebugEndpoints: false
  enableSwaggerUI: false
  enableProfiling: false
```

### 4. Create `/infrastructure/helm/charts/aswa/templates/external-secrets.yaml`
```yaml
{{- if .Values.externalSecrets.enabled }}
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: {{ include "aswa.fullname" . }}-secrets
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: {{ .Values.externalSecrets.secretStoreRef.name }}
    kind: {{ .Values.externalSecrets.secretStoreRef.kind }}
  target:
    name: {{ include "aswa.fullname" . }}-secrets
    creationPolicy: Owner
  data:
    - secretKey: DATABASE_URL
      remoteRef:
        key: {{ .Values.environment }}/aswa/database
        property: url
    - secretKey: REDIS_URL
      remoteRef:
        key: {{ .Values.environment }}/aswa/redis
        property: url
    - secretKey: OPENAI_API_KEY
      remoteRef:
        key: {{ .Values.environment }}/aswa/llm
        property: openai_api_key
    - secretKey: ANTHROPIC_API_KEY
      remoteRef:
        key: {{ .Values.environment }}/aswa/llm
        property: anthropic_api_key
    - secretKey: JWT_SECRET
      remoteRef:
        key: {{ .Values.environment }}/aswa/auth
        property: jwt_secret
    - secretKey: STORAGE_ACCESS_KEY
      remoteRef:
        key: {{ .Values.environment }}/aswa/storage
        property: access_key
    - secretKey: STORAGE_SECRET_KEY
      remoteRef:
        key: {{ .Values.environment }}/aswa/storage
        property: secret_key
{{- end }}
```

### 5. Create `/infrastructure/helm/charts/aswa/templates/ingress.yaml`
```yaml
{{- if .Values.apiGateway.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "aswa.fullname" . }}-api
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
    app.kubernetes.io/component: api-gateway
  {{- with .Values.apiGateway.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  ingressClassName: {{ .Values.apiGateway.ingress.className }}
  {{- if .Values.apiGateway.ingress.tls }}
  tls:
    {{- range .Values.apiGateway.ingress.tls }}
    - hosts:
        {{- range .hosts }}
        - {{ . | quote }}
        {{- end }}
      secretName: {{ .secretName }}
    {{- end }}
  {{- end }}
  rules:
    {{- range .Values.apiGateway.ingress.hosts }}
    - host: {{ .host | quote }}
      http:
        paths:
          {{- range .paths }}
          - path: {{ .path }}
            pathType: {{ .pathType }}
            backend:
              service:
                name: {{ include "aswa.fullname" $ }}-api-gateway
                port:
                  name: http
          {{- end }}
    {{- end }}
{{- end }}
---
{{- if .Values.webDashboard.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "aswa.fullname" . }}-web
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
    app.kubernetes.io/component: web
  {{- with .Values.webDashboard.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  ingressClassName: {{ .Values.webDashboard.ingress.className }}
  {{- if .Values.webDashboard.ingress.tls }}
  tls:
    {{- range .Values.webDashboard.ingress.tls }}
    - hosts:
        {{- range .hosts }}
        - {{ . | quote }}
        {{- end }}
      secretName: {{ .secretName }}
    {{- end }}
  {{- end }}
  rules:
    {{- range .Values.webDashboard.ingress.hosts }}
    - host: {{ .host | quote }}
      http:
        paths:
          {{- range .paths }}
          - path: {{ .path }}
            pathType: {{ .pathType }}
            backend:
              service:
                name: {{ include "aswa.fullname" $ }}-web
                port:
                  name: http
          {{- end }}
    {{- end }}
{{- end }}
```

### 6. Create `/infrastructure/helm/charts/aswa/templates/pdb.yaml`
```yaml
{{- if .Values.podDisruptionBudget.enabled }}
{{- if .Values.apiGateway.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "aswa.fullname" . }}-api-gateway
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
    app.kubernetes.io/component: api-gateway
spec:
  minAvailable: {{ .Values.podDisruptionBudget.minAvailable }}
  selector:
    matchLabels:
      {{- include "aswa.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: api-gateway
{{- end }}
---
{{- if .Values.ingestionService.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "aswa.fullname" . }}-ingestion
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
    app.kubernetes.io/component: ingestion
spec:
  minAvailable: {{ .Values.podDisruptionBudget.minAvailable }}
  selector:
    matchLabels:
      {{- include "aswa.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: ingestion
{{- end }}
---
{{- if .Values.queryService.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "aswa.fullname" . }}-query
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
    app.kubernetes.io/component: query
spec:
  minAvailable: {{ .Values.podDisruptionBudget.minAvailable }}
  selector:
    matchLabels:
      {{- include "aswa.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: query
{{- end }}
---
{{- if .Values.insightService.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "aswa.fullname" . }}-insight
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
    app.kubernetes.io/component: insight
spec:
  minAvailable: {{ .Values.podDisruptionBudget.minAvailable }}
  selector:
    matchLabels:
      {{- include "aswa.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: insight
{{- end }}
{{- end }}
```

## Verification

1. Validate values files: `helm lint infrastructure/helm/charts/aswa -f infrastructure/helm/charts/aswa/values-dev.yaml`
2. Test template rendering for each environment
3. Compare resource allocations across environments
4. Verify secret references are correct
