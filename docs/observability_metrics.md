# Observability: Prometheus Metrics and Grafana

This page documents the metrics exported by the service, how they are updated, and how to visualize them in Grafana.

Overview
- Endpoint: GET /metrics
- Content type: Prometheus exposition format (runtime uses precise Prometheus content type; OpenAPI advertises text/plain)
- Protection: Open by default. If METRICS_TOKEN is set, callers must send header X-Metrics-Token: $METRICS_TOKEN
- Scrape exclusion: /metrics itself is excluded from request counters to avoid scrape feedback.

Exported metrics
- app_requests_total{endpoint, status}
  - Counter of HTTP requests processed.
  - Labels: endpoint (path), status (HTTP status code)
  - Emitted by middleware in app/main.py; excludes endpoint=="/metrics".
- app_request_latency_seconds{endpoint}
  - Histogram of request duration in seconds.
  - Labels: endpoint
  - Buckets: 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5
  - Emitted by middleware in app/main.py; excludes endpoint=="/metrics".
  - Note: Prometheus exposes _bucket/_sum/_count time series derived from this histogram.
- app_tokens_total{endpoint}
  - Counter of tokens accounted (prompt + completion) per endpoint.
  - Updated by /query router after responses.
- app_cost_usd_total{endpoint}
  - Counter of estimated USD cost per endpoint.
  - Updated by /query router after responses.

Where metrics are defined
- Code: app/utils/metrics.py defines the CollectorRegistry and metric instruments.
- Emission:
  - request_count and request_latency are updated in app/main.py middleware.
  - tokens_total and cost_usd_total are updated in app/routers/query.py.
- Exposure: app/routers/metrics.py serves the registry at /metrics with optional token protection.

Prometheus configuration
A minimal scrape job (prometheus.yml):

scrape_configs:
  - job_name: 'ai-monitor'
    static_configs:
      - targets: ['api:8000']
    metrics_path: /metrics
    # If METRICS_TOKEN is set in the API, you can pass it via headers:
    # scheme: http
    # headers:
    #   X-Metrics-Token: ${METRICS_TOKEN}

Grafana
- Default: http://localhost:3000 (admin/admin)
- Datasource: Prometheus at http://prometheus:9090 (provisioned via grafana/provisioning)
- Dashboard: grafana/dashboards/ai-monitor-dashboard.json (also mirrored under docs/grafana)
  - Example queries used by the dashboard:
    - sum(rate(app_requests_total[1m]))
    - sum by (endpoint, status) (rate(app_requests_total[1m]))
    - histogram_quantile(0.95, sum(rate(app_request_latency_seconds_bucket[5m])) by (le, endpoint))
    - sum by (endpoint) (rate(app_tokens_total[1m]))
    - sum by (endpoint) (rate(app_cost_usd_total[1m]))

Quick verification
- curl -sS http://localhost:8000/metrics | head -n 50
- After a few requests, you should see app_requests_total, app_request_latency_seconds_*, app_tokens_total, and app_cost_usd_total.

Behavioral notes
- /metrics is not counted in app_requests_total to avoid scrape amplification.
- When METRICS_TOKEN is set, /metrics returns 403 unless the header X-Metrics-Token matches.

Changes since v0.9.0
- No metrics were removed. The following remain unchanged:
  - app_requests_total, app_request_latency_seconds, app_tokens_total, app_cost_usd_total
- Improvements since v0.9.0:
  - /metrics OpenAPI/content-type alignment and explicit text/plain in API schema
  - Test coverage added to ensure /metrics is excluded from request counters
  - Documentation was reshuffled; this page restores a complete metrics reference

See also
- docs/api.md (token protection note for /metrics)
- docs/manual_e2e_test.md (end-to-end validation steps)
- grafana/provisioning for automated datasource/dashboard setup
