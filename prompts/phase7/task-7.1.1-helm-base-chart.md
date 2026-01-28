# Task 7.1.1: Helm Charts - Base Chart Structure

## Context

You are setting up Helm charts for ASWA deployment at `/infrastructure/helm/`. This will enable consistent Kubernetes deployments across environments.

## Objective

Create a base Helm chart structure that:
1. Defines common templates and helpers
2. Supports multiple environments
3. Provides consistent naming conventions
4. Enables secure secret management
5. Supports horizontal pod autoscaling

## Requirements

### 1. Create chart structure

```
/infrastructure/helm/
├── charts/
│   └── aswa/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-dev.yaml
│       ├── values-staging.yaml
│       ├── values-prod.yaml
│       ├── templates/
│       │   ├── _helpers.tpl
│       │   ├── configmap.yaml
│       │   ├── secret.yaml
│       │   ├── deployment.yaml
│       │   ├── service.yaml
│       │   ├── ingress.yaml
│       │   ├── hpa.yaml
│       │   ├── pdb.yaml
│       │   ├── serviceaccount.yaml
│       │   └── NOTES.txt
│       └── charts/
│           ├── api-gateway/
│           ├── ingestion-service/
│           ├── query-service/
│           ├── insight-service/
│           └── web-dashboard/
└── helmfile.yaml
```

### 2. Create `/infrastructure/helm/charts/aswa/Chart.yaml`
```yaml
apiVersion: v2
name: aswa
description: ASWA - AI-Powered Document Intelligence Platform
type: application
version: 0.1.0
appVersion: "1.0.0"
keywords:
  - ai
  - document-intelligence
  - rag
  - nlp
maintainers:
  - name: ASWA Team
    email: team@aswa.io
dependencies:
  - name: postgresql
    version: "12.x.x"
    repository: https://charts.bitnami.com/bitnami
    condition: postgresql.enabled
  - name: redis
    version: "17.x.x"
    repository: https://charts.bitnami.com/bitnami
    condition: redis.enabled
  - name: elasticsearch
    version: "19.x.x"
    repository: https://charts.bitnami.com/bitnami
    condition: elasticsearch.enabled
```

### 3. Create `/infrastructure/helm/charts/aswa/values.yaml`
```yaml
# Global settings
global:
  imageRegistry: ""
  imagePullSecrets: []
  storageClass: ""

# Common settings
nameOverride: ""
fullnameOverride: ""

# Environment
environment: development

# Image defaults
image:
  registry: ghcr.io
  repository: aswa
  pullPolicy: IfNotPresent
  tag: ""

# Service account
serviceAccount:
  create: true
  annotations: {}
  name: ""

# Pod security context
podSecurityContext:
  fsGroup: 1000
  runAsNonRoot: true
  runAsUser: 1000

# Container security context
securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  readOnlyRootFilesystem: true

# Common annotations
commonAnnotations: {}

# Common labels
commonLabels: {}

# API Gateway
apiGateway:
  enabled: true
  replicaCount: 2
  image:
    repository: aswa/api-gateway
    tag: ""
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 512Mi
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
    targetMemoryUtilizationPercentage: 80
  service:
    type: ClusterIP
    port: 8000
  ingress:
    enabled: true
    className: nginx
    annotations:
      nginx.ingress.kubernetes.io/proxy-body-size: "50m"
      nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    hosts:
      - host: api.aswa.local
        paths:
          - path: /
            pathType: Prefix
    tls: []

# Ingestion Service
ingestionService:
  enabled: true
  replicaCount: 2
  image:
    repository: aswa/ingestion-service
    tag: ""
  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 2Gi
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 20
    targetCPUUtilizationPercentage: 60
  service:
    type: ClusterIP
    port: 8001

# Query Service
queryService:
  enabled: true
  replicaCount: 2
  image:
    repository: aswa/query-service
    tag: ""
  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 2Gi
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 15
    targetCPUUtilizationPercentage: 70
  service:
    type: ClusterIP
    port: 8002

# Insight Service
insightService:
  enabled: true
  replicaCount: 2
  image:
    repository: aswa/insight-service
    tag: ""
  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 2Gi
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
  service:
    type: ClusterIP
    port: 8003

# Web Dashboard
webDashboard:
  enabled: true
  replicaCount: 2
  image:
    repository: aswa/web-dashboard
    tag: ""
  resources:
    requests:
      cpu: 50m
      memory: 64Mi
    limits:
      cpu: 200m
      memory: 128Mi
  service:
    type: ClusterIP
    port: 80
  ingress:
    enabled: true
    className: nginx
    hosts:
      - host: app.aswa.local
        paths:
          - path: /
            pathType: Prefix
    tls: []

# PostgreSQL
postgresql:
  enabled: true
  auth:
    postgresPassword: ""
    database: aswa
    existingSecret: ""
  primary:
    persistence:
      enabled: true
      size: 20Gi
  metrics:
    enabled: true

# Redis
redis:
  enabled: true
  auth:
    enabled: true
    password: ""
    existingSecret: ""
  master:
    persistence:
      enabled: true
      size: 5Gi
  replica:
    replicaCount: 1
  metrics:
    enabled: true

# Elasticsearch
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

# External secrets
externalSecrets:
  enabled: false
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore

# Network policies
networkPolicies:
  enabled: true

# Pod disruption budgets
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
```

### 4. Create `/infrastructure/helm/charts/aswa/templates/_helpers.tpl`
```yaml
{{/*
Expand the name of the chart.
*/}}
{{- define "aswa.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "aswa.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "aswa.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "aswa.labels" -}}
helm.sh/chart: {{ include "aswa.chart" . }}
{{ include "aswa.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "aswa.selectorLabels" -}}
app.kubernetes.io/name: {{ include "aswa.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Component labels
*/}}
{{- define "aswa.componentLabels" -}}
{{ include "aswa.labels" . }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Component selector labels
*/}}
{{- define "aswa.componentSelectorLabels" -}}
{{ include "aswa.selectorLabels" . }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "aswa.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "aswa.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create image reference
*/}}
{{- define "aswa.image" -}}
{{- $registry := .global.imageRegistry | default .image.registry -}}
{{- $repository := .image.repository -}}
{{- $tag := .image.tag | default .appVersion -}}
{{- if $registry }}
{{- printf "%s/%s:%s" $registry $repository $tag }}
{{- else }}
{{- printf "%s:%s" $repository $tag }}
{{- end }}
{{- end }}

{{/*
Common annotations
*/}}
{{- define "aswa.annotations" -}}
{{- with .Values.commonAnnotations }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Pod annotations
*/}}
{{- define "aswa.podAnnotations" -}}
{{- include "aswa.annotations" . }}
checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
checksum/secret: {{ include (print $.Template.BasePath "/secret.yaml") . | sha256sum }}
{{- end }}

{{/*
Environment variables from ConfigMap and Secret
*/}}
{{- define "aswa.envFrom" -}}
- configMapRef:
    name: {{ include "aswa.fullname" . }}-config
- secretRef:
    name: {{ include "aswa.fullname" . }}-secrets
{{- end }}

{{/*
Database URL
*/}}
{{- define "aswa.databaseUrl" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "postgresql://%s:%s@%s-postgresql:5432/%s" .Values.postgresql.auth.username .Values.postgresql.auth.password (include "aswa.fullname" .) .Values.postgresql.auth.database }}
{{- else }}
{{- .Values.externalDatabase.url }}
{{- end }}
{{- end }}

{{/*
Redis URL
*/}}
{{- define "aswa.redisUrl" -}}
{{- if .Values.redis.enabled }}
{{- printf "redis://:%s@%s-redis-master:6379" .Values.redis.auth.password (include "aswa.fullname" .) }}
{{- else }}
{{- .Values.externalRedis.url }}
{{- end }}
{{- end }}

{{/*
Elasticsearch URL
*/}}
{{- define "aswa.elasticsearchUrl" -}}
{{- if .Values.elasticsearch.enabled }}
{{- printf "http://%s-elasticsearch:9200" (include "aswa.fullname" .) }}
{{- else }}
{{- .Values.externalElasticsearch.url }}
{{- end }}
{{- end }}
```

### 5. Create `/infrastructure/helm/charts/aswa/templates/configmap.yaml`
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "aswa.fullname" . }}-config
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
data:
  ENVIRONMENT: {{ .Values.environment | quote }}
  LOG_LEVEL: {{ .Values.logLevel | default "INFO" | quote }}
  LOG_FORMAT: {{ .Values.logFormat | default "json" | quote }}

  # Service URLs
  API_GATEWAY_URL: "http://{{ include "aswa.fullname" . }}-api-gateway:{{ .Values.apiGateway.service.port }}"
  INGESTION_SERVICE_URL: "http://{{ include "aswa.fullname" . }}-ingestion:{{ .Values.ingestionService.service.port }}"
  QUERY_SERVICE_URL: "http://{{ include "aswa.fullname" . }}-query:{{ .Values.queryService.service.port }}"
  INSIGHT_SERVICE_URL: "http://{{ include "aswa.fullname" . }}-insight:{{ .Values.insightService.service.port }}"

  # Feature flags
  ENABLE_METRICS: {{ .Values.monitoring.enabled | quote }}
  ENABLE_TRACING: {{ .Values.tracing.enabled | default false | quote }}

  # Elasticsearch
  ELASTICSEARCH_URL: {{ include "aswa.elasticsearchUrl" . | quote }}
  ELASTICSEARCH_INDEX_PREFIX: {{ .Values.elasticsearch.indexPrefix | default "aswa" | quote }}
```

### 6. Create `/infrastructure/helm/charts/aswa/templates/secret.yaml`
```yaml
{{- if not .Values.externalSecrets.enabled }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "aswa.fullname" . }}-secrets
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
type: Opaque
stringData:
  DATABASE_URL: {{ include "aswa.databaseUrl" . | quote }}
  REDIS_URL: {{ include "aswa.redisUrl" . | quote }}

  {{- if .Values.llm.openaiApiKey }}
  OPENAI_API_KEY: {{ .Values.llm.openaiApiKey | quote }}
  {{- end }}

  {{- if .Values.llm.anthropicApiKey }}
  ANTHROPIC_API_KEY: {{ .Values.llm.anthropicApiKey | quote }}
  {{- end }}

  {{- if .Values.auth.jwtSecret }}
  JWT_SECRET: {{ .Values.auth.jwtSecret | quote }}
  {{- end }}

  {{- if .Values.storage.accessKey }}
  STORAGE_ACCESS_KEY: {{ .Values.storage.accessKey | quote }}
  STORAGE_SECRET_KEY: {{ .Values.storage.secretKey | quote }}
  {{- end }}
{{- end }}
```

### 7. Create `/infrastructure/helm/charts/aswa/templates/serviceaccount.yaml`
```yaml
{{- if .Values.serviceAccount.create -}}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "aswa.serviceAccountName" . }}
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
  {{- with .Values.serviceAccount.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end }}
```

### 8. Create `/infrastructure/helm/charts/aswa/templates/NOTES.txt`
```
ASWA has been deployed!

{{- if .Values.apiGateway.ingress.enabled }}
API Gateway:
{{- range .Values.apiGateway.ingress.hosts }}
  http{{ if $.Values.apiGateway.ingress.tls }}s{{ end }}://{{ .host }}
{{- end }}
{{- end }}

{{- if .Values.webDashboard.ingress.enabled }}
Web Dashboard:
{{- range .Values.webDashboard.ingress.hosts }}
  http{{ if $.Values.webDashboard.ingress.tls }}s{{ end }}://{{ .host }}
{{- end }}
{{- end }}

To check the status of the deployment:
  kubectl get pods -l app.kubernetes.io/instance={{ .Release.Name }}

To view logs:
  kubectl logs -l app.kubernetes.io/instance={{ .Release.Name }} -f

{{- if .Values.postgresql.enabled }}
PostgreSQL is running in-cluster.
{{- end }}

{{- if .Values.redis.enabled }}
Redis is running in-cluster.
{{- end }}

{{- if .Values.elasticsearch.enabled }}
Elasticsearch is running in-cluster.
{{- end }}
```

## Verification

1. Lint chart: `helm lint infrastructure/helm/charts/aswa`
2. Template rendering: `helm template aswa infrastructure/helm/charts/aswa`
3. Dry run install: `helm install --dry-run --debug aswa infrastructure/helm/charts/aswa`
