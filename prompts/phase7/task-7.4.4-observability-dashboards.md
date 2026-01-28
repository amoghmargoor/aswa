# Task 7.4.4: Observability - Grafana Dashboards

## Context

You are setting up observability for ASWA at `/infrastructure/kubernetes/`. Tracing is complete. Now we need Grafana dashboards for visualization.

## Objective

Create Grafana dashboard configurations that:
1. Visualize service health metrics
2. Display business KPIs
3. Show resource utilization
4. Enable drill-down capabilities
5. Support alerting integration

## Requirements

### 1. Create `/infrastructure/kubernetes/monitoring/dashboards/aswa-overview.json`
```json
{
  "annotations": {
    "list": [
      {
        "builtIn": 1,
        "datasource": "-- Grafana --",
        "enable": true,
        "hide": true,
        "iconColor": "rgba(0, 211, 255, 1)",
        "name": "Annotations & Alerts",
        "type": "dashboard"
      }
    ]
  },
  "editable": true,
  "gnetId": null,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "panels": [
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "red", "value": null},
              {"color": "yellow", "value": 0.95},
              {"color": "green", "value": 0.99}
            ]
          },
          "unit": "percentunit"
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 0, "y": 0},
      "id": 1,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": ["lastNotNull"],
          "fields": "",
          "values": false
        },
        "textMode": "auto"
      },
      "pluginVersion": "9.0.0",
      "targets": [
        {
          "expr": "1 - (sum(rate(http_requests_total{status=\"error\", job=~\"aswa-.*\"}[5m])) / sum(rate(http_requests_total{job=~\"aswa-.*\"}[5m])))",
          "refId": "A"
        }
      ],
      "title": "Overall Availability",
      "type": "stat"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "unit": "reqps"
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 6, "y": 0},
      "id": 2,
      "options": {
        "colorMode": "value",
        "graphMode": "area"
      },
      "targets": [
        {
          "expr": "sum(rate(http_requests_total{job=~\"aswa-.*\"}[5m]))",
          "refId": "A"
        }
      ],
      "title": "Total Request Rate",
      "type": "stat"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "unit": "s"
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 12, "y": 0},
      "id": 3,
      "options": {
        "colorMode": "value"
      },
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job=~\"aswa-.*\"}[5m])) by (le))",
          "refId": "A"
        }
      ],
      "title": "P95 Latency",
      "type": "stat"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "unit": "short"
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 18, "y": 0},
      "id": 4,
      "options": {
        "colorMode": "value"
      },
      "targets": [
        {
          "expr": "sum(kube_pod_status_phase{namespace=~\"aswa-.*\", phase=\"Running\"})",
          "refId": "A"
        }
      ],
      "title": "Running Pods",
      "type": "stat"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {
            "lineWidth": 1,
            "fillOpacity": 10
          }
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 4},
      "id": 5,
      "options": {
        "legend": {"displayMode": "list", "placement": "bottom"}
      },
      "targets": [
        {
          "expr": "sum(rate(http_requests_total{job=~\"aswa-.*\"}[5m])) by (job)",
          "legendFormat": "{{job}}",
          "refId": "A"
        }
      ],
      "title": "Request Rate by Service",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {
            "lineWidth": 1,
            "fillOpacity": 10
          },
          "unit": "s"
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 4},
      "id": 6,
      "options": {
        "legend": {"displayMode": "list", "placement": "bottom"}
      },
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job=~\"aswa-.*\"}[5m])) by (le, job))",
          "legendFormat": "{{job}}",
          "refId": "A"
        }
      ],
      "title": "P95 Latency by Service",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {
            "lineWidth": 1,
            "fillOpacity": 30
          },
          "unit": "percentunit"
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 12},
      "id": 7,
      "options": {
        "legend": {"displayMode": "list", "placement": "bottom"}
      },
      "targets": [
        {
          "expr": "sum(rate(http_requests_total{status=\"error\", job=~\"aswa-.*\"}[5m])) by (job) / sum(rate(http_requests_total{job=~\"aswa-.*\"}[5m])) by (job)",
          "legendFormat": "{{job}}",
          "refId": "A"
        }
      ],
      "title": "Error Rate by Service",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {
            "lineWidth": 1,
            "fillOpacity": 10
          },
          "unit": "bytes"
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 12},
      "id": 8,
      "options": {
        "legend": {"displayMode": "list", "placement": "bottom"}
      },
      "targets": [
        {
          "expr": "sum(container_memory_working_set_bytes{namespace=~\"aswa-.*\", container!=\"\"}) by (pod)",
          "legendFormat": "{{pod}}",
          "refId": "A"
        }
      ],
      "title": "Memory Usage by Pod",
      "type": "timeseries"
    }
  ],
  "refresh": "30s",
  "schemaVersion": 30,
  "style": "dark",
  "tags": ["aswa", "overview"],
  "templating": {
    "list": [
      {
        "current": {},
        "datasource": "Prometheus",
        "definition": "label_values(kube_pod_info{namespace=~\"aswa-.*\"}, namespace)",
        "hide": 0,
        "includeAll": true,
        "label": "Namespace",
        "multi": true,
        "name": "namespace",
        "options": [],
        "query": "label_values(kube_pod_info{namespace=~\"aswa-.*\"}, namespace)",
        "refresh": 1,
        "regex": "",
        "skipUrlSync": false,
        "sort": 1,
        "type": "query"
      }
    ]
  },
  "time": {"from": "now-1h", "to": "now"},
  "timepicker": {},
  "timezone": "browser",
  "title": "ASWA Overview",
  "uid": "aswa-overview",
  "version": 1
}
```

### 2. Create `/infrastructure/kubernetes/monitoring/dashboards/aswa-business.json`
```json
{
  "annotations": {"list": []},
  "editable": true,
  "gnetId": null,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "panels": [
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "unit": "short"
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 0, "y": 0},
      "id": 1,
      "options": {"colorMode": "value", "graphMode": "area"},
      "targets": [
        {
          "expr": "sum(increase(documents_processed_total{status=\"success\"}[24h]))",
          "refId": "A"
        }
      ],
      "title": "Documents Processed (24h)",
      "type": "stat"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "unit": "short"
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 6, "y": 0},
      "id": 2,
      "options": {"colorMode": "value", "graphMode": "area"},
      "targets": [
        {
          "expr": "sum(increase(insights_generated_total[24h]))",
          "refId": "A"
        }
      ],
      "title": "Insights Generated (24h)",
      "type": "stat"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "unit": "short"
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 12, "y": 0},
      "id": 3,
      "options": {"colorMode": "value", "graphMode": "area"},
      "targets": [
        {
          "expr": "sum(increase(queries_total[24h]))",
          "refId": "A"
        }
      ],
      "title": "Queries Processed (24h)",
      "type": "stat"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "unit": "short"
        }
      },
      "gridPos": {"h": 4, "w": 6, "x": 18, "y": 0},
      "id": 4,
      "options": {"colorMode": "value", "graphMode": "area"},
      "targets": [
        {
          "expr": "sum(increase(query_tokens_used_total[24h]))",
          "refId": "A"
        }
      ],
      "title": "LLM Tokens Used (24h)",
      "type": "stat"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {"lineWidth": 2, "fillOpacity": 20}
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 4},
      "id": 5,
      "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
      "targets": [
        {
          "expr": "sum(rate(documents_processed_total[5m])) by (tenant_id)",
          "legendFormat": "{{tenant_id}}",
          "refId": "A"
        }
      ],
      "title": "Document Processing Rate by Tenant",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {"lineWidth": 2, "fillOpacity": 20}
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 4},
      "id": 6,
      "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
      "targets": [
        {
          "expr": "sum(rate(insights_generated_total[5m])) by (insight_type)",
          "legendFormat": "{{insight_type}}",
          "refId": "A"
        }
      ],
      "title": "Insights by Type",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "unit": "s"
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 12},
      "id": 7,
      "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum(rate(document_processing_duration_seconds_bucket[5m])) by (le, document_type))",
          "legendFormat": "{{document_type}}",
          "refId": "A"
        }
      ],
      "title": "P95 Processing Time by Document Type",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "unit": "s"
        }
      },
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 12},
      "id": 8,
      "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum(rate(query_duration_seconds_bucket[5m])) by (le, tenant_id))",
          "legendFormat": "{{tenant_id}}",
          "refId": "A"
        }
      ],
      "title": "P95 Query Response Time by Tenant",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "unit": "percentunit"
        }
      },
      "gridPos": {"h": 8, "w": 8, "x": 0, "y": 20},
      "id": 9,
      "options": {},
      "targets": [
        {
          "expr": "histogram_quantile(0.5, sum(rate(insight_confidence_score_bucket[1h])) by (le, insight_type))",
          "legendFormat": "{{insight_type}}",
          "refId": "A"
        }
      ],
      "title": "Median Insight Confidence by Type",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "unit": "short"
        }
      },
      "gridPos": {"h": 8, "w": 8, "x": 8, "y": 20},
      "id": 10,
      "options": {},
      "targets": [
        {
          "expr": "documents_queued",
          "legendFormat": "{{tenant_id}}",
          "refId": "A"
        }
      ],
      "title": "Document Processing Queue",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "unit": "percentunit"
        }
      },
      "gridPos": {"h": 8, "w": 8, "x": 16, "y": 20},
      "id": 11,
      "options": {},
      "targets": [
        {
          "expr": "sum(rate(cache_hits_total[5m])) / (sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))",
          "legendFormat": "Cache Hit Rate",
          "refId": "A"
        }
      ],
      "title": "Cache Hit Rate",
      "type": "timeseries"
    }
  ],
  "refresh": "30s",
  "schemaVersion": 30,
  "style": "dark",
  "tags": ["aswa", "business"],
  "templating": {
    "list": [
      {
        "current": {},
        "datasource": "Prometheus",
        "definition": "label_values(documents_processed_total, tenant_id)",
        "hide": 0,
        "includeAll": true,
        "label": "Tenant",
        "multi": true,
        "name": "tenant_id",
        "options": [],
        "query": "label_values(documents_processed_total, tenant_id)",
        "refresh": 1,
        "type": "query"
      }
    ]
  },
  "time": {"from": "now-24h", "to": "now"},
  "timepicker": {},
  "timezone": "browser",
  "title": "ASWA Business Metrics",
  "uid": "aswa-business",
  "version": 1
}
```

### 3. Create `/infrastructure/kubernetes/monitoring/dashboards/configmap.yaml`
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: aswa-grafana-dashboards
  namespace: monitoring
  labels:
    app.kubernetes.io/name: grafana
    grafana_dashboard: "1"
data:
  aswa-overview.json: |
    {{ .Files.Get "dashboards/aswa-overview.json" | indent 4 }}

  aswa-business.json: |
    {{ .Files.Get "dashboards/aswa-business.json" | indent 4 }}
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-datasources
  namespace: monitoring
  labels:
    grafana_datasource: "1"
data:
  datasources.yaml: |
    apiVersion: 1
    datasources:
      - name: Prometheus
        type: prometheus
        access: proxy
        url: http://prometheus-server:80
        isDefault: true

      - name: Loki
        type: loki
        access: proxy
        url: http://loki-gateway:80

      - name: Jaeger
        type: jaeger
        access: proxy
        url: http://aswa-jaeger-query:16686
```

### 4. Create `/infrastructure/kubernetes/monitoring/dashboards/alertmanager-config.yaml`
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: alertmanager-config
  namespace: monitoring
stringData:
  alertmanager.yml: |
    global:
      resolve_timeout: 5m
      slack_api_url: '{{ .Values.slack.webhookUrl }}'

    route:
      receiver: 'default-receiver'
      group_by: ['alertname', 'job', 'severity']
      group_wait: 30s
      group_interval: 5m
      repeat_interval: 4h

      routes:
        - match:
            severity: critical
          receiver: 'critical-alerts'
          continue: true

        - match:
            severity: warning
          receiver: 'warning-alerts'

        - match:
            alertname: ASWADocumentProcessingBacklog
          receiver: 'business-alerts'

    receivers:
      - name: 'default-receiver'
        slack_configs:
          - channel: '#aswa-alerts'
            send_resolved: true
            title: '{{ template "slack.default.title" . }}'
            text: '{{ template "slack.default.text" . }}'

      - name: 'critical-alerts'
        slack_configs:
          - channel: '#aswa-critical'
            send_resolved: true
            color: '{{ if eq .Status "firing" }}danger{{ else }}good{{ end }}'
            title: '🚨 Critical Alert: {{ .GroupLabels.alertname }}'
            text: |
              *Alert:* {{ .GroupLabels.alertname }}
              *Severity:* {{ .CommonLabels.severity }}
              *Description:* {{ .CommonAnnotations.description }}

              {{ range .Alerts }}
              • {{ .Annotations.summary }}
              {{ end }}
        pagerduty_configs:
          - service_key: '{{ .Values.pagerduty.serviceKey }}'
            severity: critical

      - name: 'warning-alerts'
        slack_configs:
          - channel: '#aswa-alerts'
            send_resolved: true
            color: '{{ if eq .Status "firing" }}warning{{ else }}good{{ end }}'
            title: '⚠️ Warning: {{ .GroupLabels.alertname }}'
            text: |
              *Alert:* {{ .GroupLabels.alertname }}
              *Description:* {{ .CommonAnnotations.description }}

      - name: 'business-alerts'
        slack_configs:
          - channel: '#aswa-business'
            send_resolved: true
            title: '📊 Business Alert: {{ .GroupLabels.alertname }}'
            text: '{{ .CommonAnnotations.description }}'

    templates:
      - '/etc/alertmanager/templates/*.tmpl'
```

## Verification

1. Import dashboards to Grafana
2. Configure datasources
3. Verify metrics are displayed
4. Test alert notifications
5. Check drill-down functionality
