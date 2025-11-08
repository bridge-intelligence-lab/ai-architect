# Observability notes (Architect memory)

- SSE meta event now includes memory read stats when memory flags are enabled:
  - memory_short_reads
  - memory_long_reads
- Audit payload normalizes memory fields to integers/booleans when flags are enabled.
- Set MEMORY_DEBUG=true to print suppressed exceptions from short/long memory operations for troubleshooting in non-production environments.

Metrics & Dashboards
- For Prometheus/Grafana metrics and how to configure scrapes and dashboards, see observability_metrics.md
