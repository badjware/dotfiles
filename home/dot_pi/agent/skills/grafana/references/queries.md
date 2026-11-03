# Query patterns and pitfalls

Substitute real metric names and labels found by discovery. Never invent them.

## PromQL

Error ratio. Aggregate both sides to the same labels, or unaggregated division matches each error series to itself:

```promql
sum by (job) (rate(http_requests_total{job="api",status=~"5.."}[5m]))
/ sum by (job) (rate(http_requests_total{job="api"}[5m]))
```

Classic histogram p95. Sum buckets across instances before the quantile and keep `le`:

```promql
histogram_quantile(0.95, sum by (job, le) (rate(http_request_duration_seconds_bucket{job="api"}[5m])))
```

Native histogram: use the base metric, no `_bucket`, no `le`. If only `_sum`/`_count` exist, their ratio is the mean, not a percentile.

Window total at one time: instant query with `--time`, not summed range points:

```bash
gcx metrics query -d <prom> 'sum(increase(http_requests_total{job="api"}[30m]))' --time <t>
```

Top offenders: `topk(5, sum by (route) (rate(...[5m])))`.

Scrape health: `up` = 1 means the scrape worked, not that the app is healthy. Empty means no series. `absent(up{job="api"})` returns 1 only when no series matches.

Pitfalls:
- Repeated `--match` selectors are a union. Put AND conditions in one selector.
- Rate before aggregating. Do not average per-instance percentiles.
- Look at total request rate too, so a ratio change is not mistaken for a volume change.
- Check returned timestamps and spacing. If the step you asked for is not what came back, report the actual resolution.
- Grafana Cloud aggregated metrics may reject raw selectors. Reuse the working recording-rule or dashboard query; labels aggregated away cannot be filtered back in.
- Resolve dashboard variables and macros (`$__rate_interval`, `$cluster`) before running a panel query outside Grafana.

## LogQL

| Kind | Where it lives | How to filter |
| --- | --- | --- |
| Indexed label | `stream` | inside `{...}` |
| Structured metadata (e.g. `detected_level`, often `trace_id`) | entry `structuredMetadata` | after a pipe, no parser |
| Parsed field | after `\| json` / `\| logfmt` | after the parser |

```bash
gcx logs query -d <loki> '{service_name="api"} | json | status >= 500 | __error__=""' --from <t1> --to <t2> --limit 20
gcx logs metrics -d <loki> 'sum by (level) (count_over_time({service_name="api"} | json | __error__="" [5m]))' --from <t1> --to <t2> --step 1m
gcx logs query-patterns -d <loki> '{service_name="api"}' --since 1h      # cluster similar lines
```

Pitfalls:
- The selector needs a matcher that cannot match empty. Never `{}`.
- `logs query` returns at most 50 lines by default. A sample proves neither frequency nor first occurrence. Use `logs metrics` for counts and rates.
- Put `__error__=""` after parse or numeric conversion stages.
- `logs metrics` has no `--time`. Use explicit ranges.
- Count at one request boundary (gateway or backend), not across hops and retries.

## TraceQL

| Expression | Meaning |
| --- | --- |
| `resource.service.name` | resource attribute (always scope custom attributes) |
| `span.http.route`, `span.http.response.status_code` | span attributes, names depend on instrumentation |
| `name`, `duration`, `kind` | span intrinsics; `kind` is `server`, `client`, ... |
| `status` | `error`, `ok`, `unset` (unquoted) |
| `trace:rootService`, `trace:rootName`, `trace:duration` | trace-level intrinsics |

```bash
gcx traces query -d <tempo> '{ resource.service.name = "api" && kind = server && duration > 2s }' --from <t1> --to <t2> --limit 10
gcx traces metrics -d <tempo> '{ resource.service.name = "api" && status = error } | rate() by (span.http.route)' --since 1h
gcx traces labels -d <tempo> -l span.http.route -q '{ resource.service.name = "api" }' --llm -o json
```

Pitfalls:
- Conditions inside one `{ }` must match the same span. `{ a } && { b }` can match different spans.
- Search is capped (default 20) and unranked. Do not estimate shares by counting results; use `traces metrics`.
- The trace ID is positional. Search has no `--service` flag; put it in TraceQL.
- For a missing trace ID, check datasource, retention, and time bounds once, then search the cohort instead.
