# Measurement and runtime

## Identify the operating regime before blaming SQL

Record image/build, query settings, CPU quota/affinity, service memory, query
memory, Elasticsearch heap when applicable, parts/merges and cache policy.
Equal resource limits can activate different internal behavior.

A combination of high system CPU, many minor page faults and little disk-read
time calls for allocator/page-reclamation diagnostics. Inspect startup logs,
`system.jemalloc_stats` when available, RSS/cgroup usage and actual arena decay.
Minor faults do not imply disk IO. JIT being enabled does not establish that
compilation caused the overhead.

In a historical Antalya 26.6.8.20004 investigation, a 1.5 GiB service envelope activated
`dirty_decay_ms=0`, whereas a 4 GiB control retained delayed decay. Actual arena
decay differed from that image's configured 5,000 ms default, and immediate
reclamation was reported as a major cost. This is not jemalloc's universal default
or a threshold established for other images. The original image digest and runtime
captures are not bundled here; treat this observation as a hypothesis to reproduce.
Check the running engine instead of assuming this threshold or policy is universal.
The [upstream memory worker](https://github.com/ClickHouse/ClickHouse/blob/master/src/Common/MemoryWorker.cpp)
and [jemalloc decay semantics](https://jemalloc.net/jemalloc.3.html#opt.dirty_decay_ms)
explain the mechanisms; pinned runtime evidence establishes applicability.

For a causal probe, preserve SQL, data and query caps while varying the service
memory envelope; then restore immediate decay at the larger envelope as a separate
control if supported. Compare faults, system CPU and memory, not just elapsed time.
Do not silently disable memory safeguards or prescribe 4 GiB as universal sizing.
When changing the comparison envelope, rerun both engines and disclose heap changes.

## Separate clocks and work

Use client wall time for the real request/decoding boundary and query-log counters
for server behavior. Capture `query_duration_ms`, `read_rows`, `read_bytes`,
`memory_usage` and relevant `ProfileEvents`, tied to an explicit query ID/comment.
CPU and processor intervals overlap across threads; their sum is not server wall
time. Logical read bytes are not necessarily physical disk bytes. See
[system.query_log](https://clickhouse.com/docs/reference/system-tables/query_log).

Inspect plans outside timed samples. Keep conversion, ingestion/preparation,
execution, transfer, triage and destination delivery separate before reporting a
complete end-to-end result. pySigma conversion time is not Elasticsearch execution
time. Distinguish Elasticsearch ES|QL and Lucene routes, keyword versus wildcard
mappings, and count-only versus full-result queries.

### When completion requires a query-log record

If the client polls for `QueryFinish`, measure wall time through confirmation and
result handling. For each request, pair the data SELECT duration with the wait
for its own terminal record by query ID. Keep individual client timings within
each concurrent burst so a long wait on one lane stays visible. Compute throughput
from completed requests and elapsed burst spans. Independent phase medians cannot
reconstruct a median request.

When testing `query_log.flush_interval_milliseconds`, count application polls
and keep benchmark observer queries out of the log with query-scoped
`log_queries=0`. Through a defined post-run drain, count query-log parts and
on-disk output bytes separately for `NewPart` and completed `MergeParts` events.
Report bytes per completed request and parts per elapsed second. Smaller initial
parts can still cost more in merge output. Merges can include older parts, and
late merges and device writes need separate observation under sustained load
before choosing a deployment interval. [system.part_log](https://clickhouse.com/docs/reference/system-tables/part_log)

## Reproducible comparisons

Use identical logical inputs and an independent result oracle. When outputs
represent occurrences, compare their identities; count equality alone can conceal
different matches. For aggregate-only contracts, verify the required aggregate and
its boundaries without adding unrelated identity requirements. Gate
all warmups and measured samples. Exclude partial results, conversion refusals and
semantic mismatches instead of assigning them execution times.

Rotate paired query order, warm each admitted route, repeat on fresh services and
record host contention. State which query/result/condition/filesystem caches are
disabled and which mark/index/OS caches may remain warm. Record merges, storage and
preparation costs. With seven samples, nearest-rank p95 is the maximum; interpolated
estimators use the upper observations. Neither establishes a reliable production
tail. Retain raw timings and name the estimator.

Treat a native handwritten query as a diagnostic lower-cost witness only for its
proved profile. It may omit required timestamp bounds, drift guards, deduplication
or replay behavior. Measure expression ablations without assuming their gains add
or that the entire generated/native gap is removable.

Keep a small-memory profile when it is a real deployment requirement, but label it
as such. Avoid universal engine rankings from one fixture or a shared laptop host.
