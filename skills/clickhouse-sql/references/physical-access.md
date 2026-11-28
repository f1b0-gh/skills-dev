# Physical access and data representation

## Expose predicates the engine can use

Inspect both the physical index expression and the executed predicate. Conversion,
normalization and error-checking wrappers can hide the original column. Verify
constant folding and actual selected marks; do not optimize by SQL text length.

For a scalar String substring, compare an escaped `LIKE '%literal%'` with the
equivalent `position(...)` predicate on the actual indexed expression. Index use
depends on engine version, settings, tokenizer and pattern; either form may be
eligible. Record index DDL and selected granules before choosing a rewrite.
`%`, `_` and escape characters must retain literal semantics. Token membership
is not arbitrary substring matching. Consult the pinned engine and the
[text-index reference](https://clickhouse.com/docs/reference/engines/table-engines/mergetree-family/textindexes).

Separate three facts: an index exists, the plan selects it, and it eliminates
useful work. Measure rare and broad matches, repeated and unique values, selected
parts/granules, read rows/bytes, preparation and storage. One surviving 8,192-row
granule for one hit can still amplify work. Smaller granules/compression blocks
need ingestion, storage and broad-scan controls; they are not a universal default.

For time/numeric filters, compare native typed predicates with wrappers and
check primary/min-max conditions. Preserve exact lower/upper bounds and clock
fallback semantics. A schema-known successful clock branch should be visible to
the optimizer without weakening invalid-type rejection. Moving a guard or bound
requires output and refusal controls, including negative times, precision and zones.
Moving a throwing check into the failure branch is not by itself proof of primary
key pruning. Use a raw
typed-column witness to isolate that cost; removing its guard is only admissible
when the surrounding schema-validation contract preserves required errors.
For an already matching physical column, compare schema-constant branches using
`CAST` to `DateTime64(6, 'UTC')`, `toDateTime64`, and the raw column. Their folding
and index use must be established on the target build; no full guarded-expression
reproduction is bundled here. Verify selected granules on selective data and
retain drift refusals, lower-precision/timezone conversions and logical fallback.

Order keys, projections and PREWHERE follow actual tenant/source/time access and
payload selectivity. Keep occurrence identity as a separate contract. State whether
automatic PREWHERE/projection selection was enabled in the baseline; a disabled
control is not a comparison with engine defaults. See the
[PREWHERE reference](https://clickhouse.com/docs/reference/statements/select/prewhere).

## Pay repeated transformations once when justified

Qualified native integers can avoid string allocation and string distinct state,
but only when homogeneous physical values preserve the application's canonical
equality. Mixed string/number sources or multi-field keys require separate proof.
Exact `uniqExact` semantics cannot be replaced by approximation for a speed claim.

Stored search views may avoid per-scan Unicode conversion. Bind the transformation
and version explicitly, retain original/case-sensitive fields and charge write and
storage costs. ASCII lowercase from another library is not Unicode case folding;
URL/path/decoded views are separate semantics, not implicit Sigma transformations.

Necessary-fragment candidate filters must over-approximate true matches, retain an
exact recheck and widen for unsupported/unindexed/overflow cases. Bounded extraction
must not lose a match late in a long value. Selective staging needs a dense fallback
and full acquisition/cleanup costs, not just a faster second query.

## Qualify Iceberg separately

Inspect manifest/file bounds, Parquet row-group statistics, partition transforms,
read bytes and object-store requests for the actual generated predicates. A hot
MergeTree text index does not imply equivalent lake pruning. Missing statistics or
coverage must retain candidates; unanchored substrings do not automatically benefit
from min/max bounds. See the [Iceberg metrics specification](https://iceberg.apache.org/spec/#field-level-metrics-and-statistics).

Keep the snapshot, schema/field bindings, deletes, source overlap/identity rules,
complete lookbacks and cache state explicit. A pinned snapshot establishes
reproducibility, not complete coverage. Evaluate hot, cold and combined-source paths
with identical logical output obligations before comparing latency.

For a missing computed column in `ReadFromObjectStorage` with Iceberg v2 deletes,
isolate equality deletes on a snapshot whose metadata confirms zero position
deletes. Start with two rows matching the filter and equality-delete one of them.
Check the surviving ID and the exact nonempty result of the computed query.
Keep the original and position-only snapshots as controls when reducing a
mixed-delete failure.

Reduce the failing SQL to the computed column in both the projection and the
filter. Try removing the grouping while keeping that expression. Run the failing
SQL with default PREWHERE movement and again with only
`SETTINGS optimize_move_to_prewhere=0` changed. Record the snapshot, build,
missing expression and both outcomes.
A correct result with PREWHERE movement disabled identifies a query-scoped
workaround for that case. Measure its cost on the intended workload separately.
