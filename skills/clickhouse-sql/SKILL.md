---
name: clickhouse-sql
description: Use when writing, reviewing, debugging, or benchmarking ClickHouse SQL, including Altinity Antalya, generated detection/correlation queries, MergeTree access paths, and SQL over Iceberg.
license: MIT
---

# ClickHouse SQL

Optimize the executed plan under an explicit data and result contract. A shorter
query, an available index, or a passing cold execution is not sufficient evidence.

## Match the depth to the request

For an explanation or syntax question, answer directly with a small example and
relevant documentation. A live database or benchmark is not a prerequisite.
For a query review, distinguish issues visible in the SQL from hypotheses needing
a schema or plan. For an optimization or performance claim, use the applicable
contract and measurement checks below. Ask only for missing inputs that affect
the decision; do not turn every SQL question into a qualification campaign.

## Establish the contract

Identify the pinned engine/build, storage tier, physical schema, source coverage,
clock/window bounds and required output. Distinguish hot MergeTree, Iceberg and
mixed sources; a cold storage tier does not imply a cold cache. For comparisons,
record each compared configuration's mappings, resource envelope and result shape.

Preserve native types when observed schema proves equivalent semantics. Retain
NULL/missing/empty distinctions, Unicode/case behavior, overflow handling,
occurrence multiplicity and required errors. In Sigma integrations, typed source
qualification does not authorize changing canonical equality, window boundaries,
replay identities or late-event behavior.

## Choose the relevant checks

| Situation | Read |
|---|---|
| Latency, CPU/faults, memory limits, pySigma/Elasticsearch comparison | [Measurement and runtime](references/measurement.md) |
| Full scans, invisible indexes, timestamp guards, projections or Iceberg pruning | [Physical access](references/physical-access.md) |
| Numeric/time rewrites, warm-only failures, windows, shared scans or state reuse | [Correctness and correlation](references/correctness.md) |

Use `EXPLAIN actions=1`, `EXPLAIN indexes=1` and `EXPLAIN PIPELINE` as appropriate
on the actual pinned engine. Follow the read columns, filters, selected
parts/granules and aggregation/join strategies. CTEs, aliases and `SELECT *` in
source text are not proof of repeated work: inspect their executed consequences.
See the [EXPLAIN reference](https://clickhouse.com/docs/reference/statements/explain).

When an expression is constant by schema, verify that its successful branch
actually folds. Placing a throwing function inside the condition can retain an
opaque expression even when the type is known. Preserve drift rejection while
exposing the admissible physical expression.

## Admit a change

Compare one intervention at a time against an equivalent baseline. Gate every
measured execution on the required results; record semantic failures, expected
refusals and unavailable routes separately. Test rewrites with interpreted and
compiled expressions, including repeated warm execution, when JIT is supported.
A warm mismatch blocks performance promotion.

Measure the workload and result contract that will be deployed. For detection and
correlation, include compatible rule batches, dense groups, window widths and
complete finding/evidence outputs. Count-only timing is sufficient only when the
required result really is a count and its semantics have been verified.
Charge acquisition, index/materialization preparation, storage and cleanup where
relevant. State separately which costs remain outside the clock.

Return the concrete finding, supporting SQL/plan/counters, admitted scope and
remaining limits. Keep exact samples, versions and source/query hashes in the
project's evidence location. During audits, use query-scoped settings and owned
fixtures; the skill itself grants no authority to change production layout or
publish changes.

Version-specific observations in the references are diagnostic leads. Their
historical runtime evidence is not bundled; reproduce applicable claims on the
target build before using them to justify a change.
