# SLO recording metrics

Written to the SLO's destination datasource, keyed by `grafana_slo_uuid`:

| Metric | Meaning |
| --- | --- |
| `grafana_slo_sli_window` | SLI over the objective window |
| `grafana_slo_sli_1h`, `grafana_slo_sli_1d` | short-window SLI |
| `grafana_slo_success_rate_5m`, `grafana_slo_total_rate_5m` | ratio SLOs only |
| `grafana_slo_objective` | objective (0-1) |

```promql
# Error budget remaining (fraction)
(grafana_slo_sli_window{grafana_slo_uuid="<u>"} - grafana_slo_objective{grafana_slo_uuid="<u>"})
/ (1 - grafana_slo_objective{grafana_slo_uuid="<u>"})

# Burn rate over 1h
(1 - grafana_slo_sli_1h{grafana_slo_uuid="<u>"}) / (1 - grafana_slo_objective{grafana_slo_uuid="<u>"})
```
