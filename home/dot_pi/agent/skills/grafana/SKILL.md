---
name: grafana
description: 'Inspect Grafana with gcx (Grafana CLI). Query metrics, logs, and traces (PromQL, LogQL, TraceQL); debug incidents, errors, and latency; investigate why an alert is firing; inspect and snapshot dashboards; check SLO status, error budget, burn rate, and breaching SLOs. Points to the upstream gcx skills to create or change dashboards, SLOs, and alert rules. Use when asked: "query prometheus/loki/tempo", "why is this alert firing", "debug with grafana", "create a dashboard for X", "how are my SLOs doing", or any observability task.'
version: 1
updated: 2026-11-03
compatibility: Requires gcx (checked against v1.7.1) with a configured context.
---

# Grafana via gcx

This file covers common workflows. For deep or rare workflows, load the full upstream skill:

```bash
gcx agent skills list -o json --jq '.skills[].name'
gcx agent skills get <name> -o text                       # e.g. debug-with-grafana, create-dashboard, slo-manage
gcx agent skills get <name> references/<file>.md -o text  # e.g. debug-with-grafana references/traceql-patterns.md
```

## Rules

- Never guess a command or flag. Discover: `gcx help-tree --depth 1 -o text`, `gcx help-tree <group> -o text`, `gcx <group> <cmd> --help`.
- Prefer dedicated commands over `gcx api`. Prefer `gcx metrics|logs|traces` over `gcx datasources <type>`.
- Pass `--context <name>` when the user names a context. Never switch the global context.
- Never read raw gcx config files. Use `gcx config view`.
- Never use Grafana Assistant (`gcx assistant`).
- Run independent gcx calls in parallel.
- gcx runs in agent mode. If output is a human table, set `GCX_AGENT_MODE=true`.
- Output: `-o json` to parse, `--json f1,f2` or `--jq '<expr>'` (built in) to cut output, `-o graph` to show a trend. If output spills (`gcx.spill_reference`), read the spilled file.
- List commands have default limits (`alert rules list`: 50). Use server-side filters or `--limit 0` before concluding something is missing.
- Empty is not zero, healthy, or down. Distinguish empty, error, no access, and capped sample.

## Context and errors

Unless specified, use the default context. Only check config when the target is ambiguous or a call fails:

```bash
gcx config list-contexts
gcx config current-context
gcx config check --context <ctx>
```

### Common errors

* 401: bad, expired, or missing credentials.
* 403: missing permission.

Stop and report the error, the context, and the failing command. For a 401, give the user the command to run (`gcx login <context>`) or load the `setup-gcx` upstream skill for guidance. For a 403, name the missing permission if the error shows it. Never run login, edit config, or change credentials or permissions yourself.

## Query metrics, logs, traces

Resolve the datasource UID first (reuse it from an alert, SLO, or dashboard when available):

```bash
gcx datasources list -o json --json uid,name,type     # --type may return empty on some stacks; retry without it
```

Discover only what the next query needs, then query with fixed bounds:

```bash
gcx metrics list-names -d <prom> --match '{job="api"}' --contains request --limit 20
gcx metrics labels -d <prom> --metric <name> --label <label>
gcx metrics query  -d <prom> '<promql>' --from <t1> --to <t2> --step 1m     # trend
gcx metrics query  -d <prom> '<promql>' --time <t>                          # instant; exclusive with --from/--to/--since

gcx logs labels  -d <loki> [-l <label>]
gcx logs query   -d <loki> '{service_name="api"} | json | level="error"' --from <t1> --to <t2> --limit 20
gcx logs metrics -d <loki> 'sum(rate({service_name="api"} |= "error" [5m]))' --from <t1> --to <t2> --step 1m

gcx traces labels -d <tempo> --scope resource
gcx traces query  -d <tempo> '{ resource.service.name = "api" && status = error }' --from <t1> --to <t2> --limit 10
gcx traces get    -d <tempo> <trace-id> [--from <t1> --to <t2>] --llm -o json [--filter '{ status = error }' --keep-hierarchy] [--prune]   # reuse the search range; omit if unknown
```

`--since 1h` for live triage; RFC3339 bounds for comparisons; `--share-link` for an Explore link. Read [references/queries.md](references/queries.md) before writing non-trivial PromQL, LogQL, or TraceQL.

## Debug an incident

1. Reuse what the user gave (alert, panel query, trace ID, time, service). Ask only for what blocks progress.
2. Pick the cheapest check that can refute the leading explanation: metrics for onset and scope, traces for execution, targeted logs for mechanism.
3. Follow the strongest lead first. Check counterevidence. Separate symptom, suspected mechanism, and established cause. Stay read-only.
4. Report: answer first, time window, decisive evidence with IDs and links, confidence, gaps, next action.

For trace baselines and diffs (`gcx traces baseline`, `gcx traces diff`), load `debug-with-grafana references/trace-comparison.md`.

## Investigate an alert

Prometheus rules (rule files, prometheus-operator) are visible only through the datasource:

```bash
gcx alert instances list --datasource <prom> --name '^<name>$' -o json    # firing/pending instances, labels, annotations, value
gcx api "/api/prometheus/<prom>/api/v1/rules?type=alert&rule_name[]=<name>" -o json \
  --jq '[.data.groups[] | {group: .name, file, rules: [.rules[] | {name, query, duration, labels, annotations}]}]'
gcx metrics query -d <prom> 'count by (alertstate) (ALERTS{alertname="<name>"})' --from <t1> --to <t2> --step 5m   # state over time
```

- These rules have no UID, so `--rule`, `rules get`, and `state-history` do not apply. `state` can be numeric (`3` is firing). `duration` is the `for` in seconds.
- Edit them in the source repo named by `file`, not with gcx.

Grafana-managed rules:

```bash
gcx alert rules list --state firing -o json --jq '.[] | .rules[]? | select(.name == "<name>")'
gcx alert rules get <uid> -o json
gcx alert instances list --rule <uid> --state firing -o json        # or --name '<regex>'
gcx alert state-history list --rule <uid> --from <t1> --to <t2>
```

- `type: recording` means it never fires. Report and stop.
- `state: inactive` and healthy: report what it monitors and stop unless asked.
- Firing or pending: run the rule `query` against its datasource over the last 1h to 6h (`-o json` for values, `-o graph` for the user). Firing time is not onset; account for the `for` duration and lookback.
- Read `annotations` for `runbook_url`, `dashboard_url`, description.
- Report tersely: state, labels, what it monitors, current value, trend (spike, gradual, sustained), likely causes, impact, runbook, dashboard, next actions.

## Dashboards

Inspect:

```bash
gcx dashboards search "<text>" [--tag <t>] [--folder <name>] -o json
gcx dashboards get <name> -o json                  # <name> is metadata.name (UID), not the title
gcx dashboards list-versions <name>
gcx dashboards snapshot <name> --output-dir /tmp/grafana-skill/snapshots --since 6h [--var k=v] [--panel <id>]
```

Check `apiVersion` first: v1 has `spec.panels`/`spec.templating.list`, v2 has `spec.elements`/`spec.variables`. Pin with `--api-version dashboard.grafana.app/v1beta1`. After a snapshot, open the PNG and describe it.

## SLOs

```bash
gcx slo definitions list
gcx slo definitions status [<uuid>] -o wide        # SLI, error budget, burn rate, SLI_1H, SLI_1D
gcx slo definitions timeline [<uuid>] --since 7d   # use 28d for 28d/30d windows
gcx slo definitions get <uuid> -o json
```

- OK: report numbers and stop.
- NODATA: recording rules are not producing data. Check `.spec.destinationDatasource.uid`. On remote-write stacks `up` has no series; that is not a fault.
- BREACHING: get the definition, then break down the SLI by `groupByLabels` (or `cluster`, `namespace`, `service`, `endpoint`, `status_code`) with `gcx metrics query` on the destination datasource. Find related alert rules by name or `labels.grafana_slo_uuid`. Collect runbook and dashboard URLs from `.spec.alerting.*.annotations`.
- A timeline may cover less than the requested window on young SLOs. Report the actual observed span.

SLO PromQL on recording metrics (`grafana_slo_sli_window`, `grafana_slo_objective`, ...) is in [references/slo.md](references/slo.md).

## Changes

To create, update, or delete resources, load the upstream skill (`create-dashboard`, `manage-dashboards`, `slo-manage`, `gcx`). Get explicit user approval before any write.
