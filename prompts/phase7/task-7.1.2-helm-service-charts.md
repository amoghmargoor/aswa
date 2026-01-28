# Task 7.1.2: Helm Charts - Service Charts

## Context

You are working on ASWA Helm charts at `/infrastructure/helm/`. The base chart structure is complete (Task 7.1.1). Now we need to create individual service charts.

## Objective

Create service-specific Helm charts that:
1. Define service deployments
2. Configure health checks
3. Set up service networking
4. Enable horizontal autoscaling
5. Support environment-specific configuration

## Requirements

### 1. Create `/infrastructure/helm/charts/aswa/templates/api-gateway/deployment.yaml`
```yaml
{{- if .Values.apiGateway.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "aswa.fullname" . }}-api-gateway
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
    app.kubernetes.io/component: api-gateway
spec:
  {{- if not .Values.apiGateway.autoscaling.enabled }}
  replicas: {{ .Values.apiGateway.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "aswa.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: api-gateway
  template:
    metadata:
      annotations:
        {{- include "aswa.podAnnotations" . | nindent 8 }}
      labels:
        {{- include "aswa.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: api-gateway
    spec:
      {{- with .Values.global.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "aswa.serviceAccountName" . }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
        - name: api-gateway
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          image: "{{ .Values.image.registry }}/{{ .Values.apiGateway.image.repository }}:{{ .Values.apiGateway.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.apiGateway.service.port }}
              protocol: TCP
            - name: metrics
              containerPort: 9090
              protocol: TCP
          envFrom:
            {{- include "aswa.envFrom" . | nindent 12 }}
          env:
            - name: SERVICE_NAME
              value: "api-gateway"
            - name: PORT
              value: {{ .Values.apiGateway.service.port | quote }}
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/ready
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
          resources:
            {{- toYaml .Values.apiGateway.resources | nindent 12 }}
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
      {{- with .Values.apiGateway.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.apiGateway.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.apiGateway.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
{{- end }}
```

### 2. Create `/infrastructure/helm/charts/aswa/templates/api-gateway/service.yaml`
```yaml
{{- if .Values.apiGateway.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "aswa.fullname" . }}-api-gateway
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
    app.kubernetes.io/component: api-gateway
spec:
  type: {{ .Values.apiGateway.service.type }}
  ports:
    - port: {{ .Values.apiGateway.service.port }}
      targetPort: http
      protocol: TCP
      name: http
    {{- if .Values.monitoring.enabled }}
    - port: 9090
      targetPort: metrics
      protocol: TCP
      name: metrics
    {{- end }}
  selector:
    {{- include "aswa.selectorLabels" . | nindent 4 }}
    app.kubernetes.io/component: api-gateway
{{- end }}
```

### 3. Create `/infrastructure/helm/charts/aswa/templates/api-gateway/hpa.yaml`
```yaml
{{- if and .Values.apiGateway.enabled .Values.apiGateway.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "aswa.fullname" . }}-api-gateway
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
    app.kubernetes.io/component: api-gateway
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "aswa.fullname" . }}-api-gateway
  minReplicas: {{ .Values.apiGateway.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.apiGateway.autoscaling.maxReplicas }}
  metrics:
    {{- if .Values.apiGateway.autoscaling.targetCPUUtilizationPercentage }}
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.apiGateway.autoscaling.targetCPUUtilizationPercentage }}
    {{- end }}
    {{- if .Values.apiGateway.autoscaling.targetMemoryUtilizationPercentage }}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{ .Values.apiGateway.autoscaling.targetMemoryUtilizationPercentage }}
    {{- end }}
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Percent
          value: 100
          periodSeconds: 15
        - type: Pods
          value: 4
          periodSeconds: 15
      selectPolicy: Max
{{- end }}
```

### 4. Create `/infrastructure/helm/charts/aswa/templates/ingestion-service/deployment.yaml`
```yaml
{{- if .Values.ingestionService.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "aswa.fullname" . }}-ingestion
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
    app.kubernetes.io/component: ingestion
spec:
  {{- if not .Values.ingestionService.autoscaling.enabled }}
  replicas: {{ .Values.ingestionService.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "aswa.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: ingestion
  template:
    metadata:
      annotations:
        {{- include "aswa.podAnnotations" . | nindent 8 }}
      labels:
        {{- include "aswa.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: ingestion
    spec:
      {{- with .Values.global.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "aswa.serviceAccountName" . }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
        - name: ingestion
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          image: "{{ .Values.image.registry }}/{{ .Values.ingestionService.image.repository }}:{{ .Values.ingestionService.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.ingestionService.service.port }}
              protocol: TCP
            - name: metrics
              containerPort: 9090
              protocol: TCP
          envFrom:
            {{- include "aswa.envFrom" . | nindent 12 }}
          env:
            - name: SERVICE_NAME
              value: "ingestion-service"
            - name: PORT
              value: {{ .Values.ingestionService.service.port | quote }}
            - name: WORKER_CONCURRENCY
              value: {{ .Values.ingestionService.workerConcurrency | default "4" | quote }}
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/ready
              port: http
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
          resources:
            {{- toYaml .Values.ingestionService.resources | nindent 12 }}
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            - name: uploads
              mountPath: /uploads
      volumes:
        - name: tmp
          emptyDir: {}
        - name: uploads
          emptyDir:
            sizeLimit: 5Gi
      {{- with .Values.ingestionService.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.ingestionService.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.ingestionService.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
{{- end }}
```

### 5. Create `/infrastructure/helm/charts/aswa/templates/query-service/deployment.yaml`
```yaml
{{- if .Values.queryService.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "aswa.fullname" . }}-query
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
    app.kubernetes.io/component: query
spec:
  {{- if not .Values.queryService.autoscaling.enabled }}
  replicas: {{ .Values.queryService.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "aswa.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: query
  template:
    metadata:
      annotations:
        {{- include "aswa.podAnnotations" . | nindent 8 }}
      labels:
        {{- include "aswa.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: query
    spec:
      {{- with .Values.global.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "aswa.serviceAccountName" . }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
        - name: query
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          image: "{{ .Values.image.registry }}/{{ .Values.queryService.image.repository }}:{{ .Values.queryService.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.queryService.service.port }}
              protocol: TCP
            - name: metrics
              containerPort: 9090
              protocol: TCP
          envFrom:
            {{- include "aswa.envFrom" . | nindent 12 }}
          env:
            - name: SERVICE_NAME
              value: "query-service"
            - name: PORT
              value: {{ .Values.queryService.service.port | quote }}
            - name: LLM_TIMEOUT
              value: {{ .Values.queryService.llmTimeout | default "60" | quote }}
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/ready
              port: http
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
          resources:
            {{- toYaml .Values.queryService.resources | nindent 12 }}
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            - name: cache
              mountPath: /cache
      volumes:
        - name: tmp
          emptyDir: {}
        - name: cache
          emptyDir:
            sizeLimit: 1Gi
      {{- with .Values.queryService.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.queryService.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.queryService.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
{{- end }}
```

### 6. Create `/infrastructure/helm/charts/aswa/templates/insight-service/deployment.yaml`
```yaml
{{- if .Values.insightService.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "aswa.fullname" . }}-insight
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
    app.kubernetes.io/component: insight
spec:
  {{- if not .Values.insightService.autoscaling.enabled }}
  replicas: {{ .Values.insightService.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "aswa.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: insight
  template:
    metadata:
      annotations:
        {{- include "aswa.podAnnotations" . | nindent 8 }}
      labels:
        {{- include "aswa.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: insight
    spec:
      {{- with .Values.global.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "aswa.serviceAccountName" . }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
        - name: insight
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          image: "{{ .Values.image.registry }}/{{ .Values.insightService.image.repository }}:{{ .Values.insightService.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.insightService.service.port }}
              protocol: TCP
            - name: metrics
              containerPort: 9090
              protocol: TCP
          envFrom:
            {{- include "aswa.envFrom" . | nindent 12 }}
          env:
            - name: SERVICE_NAME
              value: "insight-service"
            - name: PORT
              value: {{ .Values.insightService.service.port | quote }}
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/ready
              port: http
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
          resources:
            {{- toYaml .Values.insightService.resources | nindent 12 }}
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
      {{- with .Values.insightService.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.insightService.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.insightService.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
{{- end }}
```

### 7. Create `/infrastructure/helm/charts/aswa/templates/web-dashboard/deployment.yaml`
```yaml
{{- if .Values.webDashboard.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "aswa.fullname" . }}-web
  labels:
    {{- include "aswa.labels" . | nindent 4 }}
    app.kubernetes.io/component: web
spec:
  replicas: {{ .Values.webDashboard.replicaCount }}
  selector:
    matchLabels:
      {{- include "aswa.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: web
  template:
    metadata:
      labels:
        {{- include "aswa.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: web
    spec:
      {{- with .Values.global.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "aswa.serviceAccountName" . }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
        - name: web
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          image: "{{ .Values.image.registry }}/{{ .Values.webDashboard.image.repository }}:{{ .Values.webDashboard.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.webDashboard.service.port }}
              protocol: TCP
          env:
            - name: API_URL
              value: {{ .Values.webDashboard.apiUrl | default "/api" | quote }}
          livenessProbe:
            httpGet:
              path: /
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
          resources:
            {{- toYaml .Values.webDashboard.resources | nindent 12 }}
      {{- with .Values.webDashboard.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.webDashboard.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
{{- end }}
```

## Verification

1. Template each service: `helm template aswa infrastructure/helm/charts/aswa --set apiGateway.enabled=true`
2. Verify HPA configuration: Check autoscaling behavior settings
3. Test with values overrides
