# Correctness and correlation

## Test compiled expressions as well as cold results

A cold success can precede a wrong result after the compilation threshold. Read
the actual `compile_expressions` and `min_count_to_compile_expression` settings.
Compare repeated executions with query-scoped compilation off/on; where supported,
use a zero threshold to exercise compilation immediately. Check every result,
including warmups. A JIT mismatch blocks promotion even when the compiled query is
faster. Isolate arithmetic before blaming a join or window algorithm.

In a historical investigation, this standalone reduction reportedly returned the
Int64 minimum for every row on Antalya **26.6.8.20004** with compilation enabled.
The original image digest and result capture are not bundled; use the query as a
regression probe, not proof that a currently deployed binary is affected:

```sql
SELECT number,
       toString(greatest(
           toInt128('-9223372036854775808'),
           toInt128(number) + 99000000
       )) AS result
FROM numbers(4)
SETTINGS compile_expressions = 1,
         min_count_to_compile_expression = 0;
```

The mathematical results are `99000000` through `99000003`. This is a pinned-build
regression example, not a claim about all ClickHouse versions or all `greatest`
calls. That investigation reported that reversing arguments did not repair the
expression and that an explicit `if(diff < minimum, minimum, diff)` clamp passed
its interpreted/compiled controls. Those endpoint/window results are not reproduced
by this snippet; include them in the target build's qualification.
Qualify that candidate in the complete generated query before adopting it. Avoid
global JIT disablement as an unexplained performance fix.

## Match algorithms to the result contract

| Required result | Candidate to evaluate | Proof still needed |
|---|---|---|
| Complete fixed-bucket counts | Native aggregation | Bucket origin, negative times, precision, bounds, grouping and identity |
| Distinct values in homogeneous typed data | Native exact distinct state | Canonical equality, NULL/missing behavior and mixed-source rejection |
| Per-event simple sliding counts | Prefix counts and strict ASOF subtraction | Boundary inclusion, timestamp ties, IDs, saturation and complete trigger outputs |
| Ordered, reset/suppression or chained correlations | Explicit state/replay strategy | Ordering, transition semantics, evidence, limits and replay identity |

A fixed-bucket aggregate is not a general replacement for per-event sliding
outputs. Likewise, a prefix result with matching `(time, id, group, count)` does
not establish equivalence for evidence payloads, reset behavior or suppression.
Keep fallback routes for profiles outside a specialization's proof.

An ASOF specialization must respect the caller's join policy. Preserve eligibility
when query settings are transferred separately to the execution host; an explicit
incompatible algorithm should retain the supported fallback rather than fail later
or silently override resource policy. Qualify internal columns in outer projections:
permitted user labels can otherwise shadow tuple/metric aliases and silently change
results. Exercise adversarial labels and transferred settings in live controls.

Exercise dense groups as well as total volume. Vary events per group, active
window width, simultaneous timestamps and emitted findings. Inspect `arrayFold`
state for repeated queue filtering, distinct rebuilding and growing output arrays.
A short active window does not bound the cost of accumulating all emitted alerts.
Check whether a capacity guard bounds total input or active state. Measure scaling;
do not label an observed curve quadratic solely because array copies are possible.

## Share work without changing identities

Shared scans need compatible source coverage, clock bounds and field semantics.
Compare complete `(rule, occurrence, payload/evidence)` outputs, not just total
counts. Preserve matches belonging to multiple rules and apply source eligibility
before any identity deduplication. Include acquisition, materialization and output
costs; a faster four-rule count prototype does not prove a faster full catalog.

Reusable aggregate state needs an explicit replay/late-event contract: identities,
window expiration, rule/schema version, source snapshot/coverage and retention.
Replay an already processed batch and require the same result. Append-only state
that turns two distinct occurrences into three after replay is not an admissible
general incremental backend. Test overlapping windows, late arrivals, deletions
and resets according to the supported profile; state the remaining exclusions.
