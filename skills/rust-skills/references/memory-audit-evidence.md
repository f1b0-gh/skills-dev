# Evidence for a Rust memory audit

Use this reference for an explicit memory audit, an allocation regression, or
an aggregate resource claim. Ordinary Rust edits do not require a repository-wide
campaign. Keep project-specific findings and measurements in the project report.

## Follow the allocation, not only the operation

For each relevant path, record:

| Field | Evidence to collect |
| --- | --- |
| Scope | Entry point, deployed feature/backend/target, dependency or native runtime involved. |
| Owner | Who holds the input, decoded value, queue item, active work, result and previous generation? |
| Admission | Which gate is acquired before each expensive allocation? Is the gate per instance or shared? |
| Bound | Bytes and capacities, item count, active operations, waiting producers and retained results; checked arithmetic. |
| Release | Completion, receiver drop, result drop, next poll, expiry maintenance, worker exit or process reaping. |
| Evidence | Source location, executed command and workload, observed invariant, and what remains unmeasured. |

A worker permit released when work returns does not cover the returned snapshot
while the caller awaits another service. A channel slot released on receive does
not cover the response retained in a completed oneshot or ticket. If a budget is
intended to cover that interval, its ownership must follow the result or another
gate must cover it. Identify the existing contract before changing it.

Include independently constructed instances: one bounded store, pool, exporter
or bridge per client can still create an unbounded aggregate. Follow public
alternate entry points too; a bounded polling driver need not bound direct
`execute` calls on the same client.
For retries, count work surviving cancellation: a minimum retry interval bounds
launch rate, not outstanding work when no completion-time bound exists. Conversely,
an unbounded channel carrying a single completion signal can have a semantic
bound of one; establish its producer protocol before diagnosing growth.

## Count simultaneous representations

Input bytes, decoded trees, cloned state, serialized candidates, validation
scratch and encoded output can coexist. An encoded-storage quota is not a heap
quota. Check the order of materialization and validation:

- A structural JSON limit checked after `Value` construction limits acceptance,
  not the allocation peak of rejected input. A seeded decoder can stop collection
  growth earlier, but key strings and escaped-string scratch may still allocate
  before a visitor checks their decoded length.
- A page budget can bound returned records while a provider first downloads or
  decodes an entire oversized record. Inspect the provider, not just the page API.
- Cloning a snapshot before serialization can retain old tree, new tree and both
  encodings. Recovery may keep both a complete directory listing and an index.
- Maximum-sized preallocation costs that capacity even for a tiny response.
  `clear()` often preserves capacity; a small `Bytes` view can retain its backing.
- Count a shared backing once while any owner holds it; count deep clones
  separately. Do not classify required replay or deduplication state as a leak.

Distinguish per-object limits, total state limits, transient peaks and RSS. A
limit applied separately to each guest memory is not a limit on the whole VM,
host compilation, lifted values, native code or child processes.

## Diagnose async stack usage separately

A composed future can exhaust a thread stack while it is constructed, moved into
an executor, or polled through nested task-local scopes. Measure concrete future
sizes and inspect the failing frames: `size_of_val` alone is not the peak stack
usage. A dependency's stack-headroom guard may return an ordinary evaluation
error before another path reaches a hard stack overflow.

Box the proven large subfuture at a composition boundary while retaining the
same authorization guards, borrows, task ownership and cancellation behavior.
Check construction as well as polling; `Box::pin(large_future())` can still need
a large temporary stack frame. Verify with the normal runtime/test-thread stack.
A successful diagnostic run with a larger stack identifies sensitivity, not a
fix or a bound on heap use. Do not replace local awaits with detached tasks just
to reduce the parent future's size.

## Closure, expiry and native bridges

`close`, timeout and `Drop` can release different owners. Closing a sender does
not discard a live receiver's queue. Closing a logical subscription may leave
its last snapshot readable. A deadline checked inside `poll_next` does not run
when that stream is not polled. Test the intended retention contract explicitly.

Inspect native queues as well as Tokio channels: N-API thread-safe callbacks,
Python futures, crypto/device sessions and exporter workers have separate owners.
Verify the pinned API's meaning of zero/default capacity. Canceling a Rust
receiver need not remove an invocation already enqueued in another runtime.
Measure the relevant runtime's heap/external allocations in addition to Rust.

For binding failures, identify the high-level facade, native addon and test
fixture together. Rebuild a coherent set before attributing a failure from
pre-existing binaries to current Rust source; retain both runs. Passing those
functional tests still does not establish queue saturation or GC behavior.

A native module being present does not establish that it can be loaded. Check
transitive runtime dependencies in the actual test executable's environment;
distinguish loader failures from provider behavior and retain the failed run.

## Measure the claim being made

For allocation probes, warm up first and separate input ownership from the
operation. Instrument successful `alloc`, `alloc_zeroed`, `realloc` and `dealloc`;
do not allocate, log or unwind inside allocator hooks. Record both live requested
bytes and peak. State that these omit allocator overhead and native allocations;
a realloc counter may miss an internal overlap between old and new storage.

Sample RSS/PSS separately. A high resident plateau after live allocations return
to baseline is not evidence that those payloads leaked. On Linux,
[`smaps_rollup`](https://www.kernel.org/doc/html/latest/filesystems/proc.html)
provides a different observation from the approximate RSS counters in
[`status`](https://man7.org/linux/man-pages/man5/proc_pid_status.5.html).
Sampling can miss peaks. Do not replace a point-in-time thread count with a
claim that all workers were joined. Include children/cgroup where the claim
concerns the whole deployment; keep pressure/OOM tests in an appropriate isolated
environment.

Vary size and cardinality independently. Exercise saturation, rejected input,
blocked consumers, cancellation before and after admission, completed unread
results, repeated open/close, recovery and replacement generations. A stable
plateau for one workload is evidence for that workload, not a universal bound.

## Keep coverage and verification distinct

In broad audits, map actual packages and entry points to review cases. A lexical
scan includes comments, tests and inactive cfg branches; a mapped package is not
an exhaustively reviewed package. Record static findings, reproduced behavior,
locally justified bounds and qualification gaps separately.

Attach test evidence to exact features, backend, target, source revision and
command. Check the number of tests actually executed: crate-level cfg can turn
an integration target into zero tests; a successful build or a library with tests
disabled is not an executed qualification. Features required by tests may be
different from those required to compile the production module.
Check library compilation as well as unit tests: a helper used only under
`cfg(test)` can otherwise fail the production build's dead-code lint, and a
private backend-specific method should follow the feature gate of its callers.

Before a long test suite, run the selected library compile/lint checks early to
catch feature-gate errors. For large builds, also run `cargo check --lib --tests`
with the intended packages and features before expensive code generation. This
catches test-only compilation errors but does not link or execute the tests.
A shared test module is compiled separately in each integration target: a helper
used in one target can still be dead code in another. Keep its API appropriate
for partial use (for example, a meaningful `Default` implementation), rather
than adding artificial calls just to silence a diagnostic.
Account for compilation and target-directory lock
wait separately from test execution: a build timeout is not a failing test.
Reuse compatible build graphs where useful, but document feature unification;
testing a union does not verify every configuration separately.

For time-gated protocols, fixtures must honor the advertised `not_before` or
retry deadline even when an upstream step completes quickly. Wait only the
remaining interval; do not disable production timing checks to make tests pass.
Negative tests should assert the intended rejection: a generic `is_err()` can
hide a broken authentication check behind an unrelated `TooEarly` error.
If a fixture advances virtual time during authorization, derive proof and token
boundaries from their actual issuance/signing instants. Exercise the last valid
instant, the first expired instant and rollback without resetting below a store's
retained clock floor accidentally. Prefer typed refusals over display-string
matching; accept an alternate transport wrapper only when it contains the exact
expected rejection and occurs in the intended withdrawal state.
For publication-race retries, distinguish repeating current-authority validation
from replaying an already admitted request. Bound attempts and preserve the
deadline across them, without repeating nonce admission or effects. State which
phase owns that deadline: a per-call budget is not an end-to-end request budget.
Publication activity grants no authority; every retry must validate current state
and preserve the distinction between expiration and temporary unavailability.

If the workspace can change during a long audit, retain the initial source
fingerprints, check for drift before the final report and re-read changed paths.
Do not present commands run across different source states as one immutable
build. Preserve other contributors' edits. Include known non-Rust build inputs
such as embedded JSON schemas in the fingerprint scope; a stable set of `.rs`
files does not imply a stable executable. After a concurrent API/enum change,
repeat the cheap selected compile gate before expensive code generation and
keep its integration failures distinct from the original reproduced failures.

When a test launches another libtest process, its summary appears inside the
parent output. Attribute summaries to their process/target rather than summing
every `test result` line as independent top-level tests. Record failed, ignored,
filtered and zero-test targets. A completed child does not establish completion
of a parent killed before its own summary; keep that target incomplete. A later
successful retry does not erase the original failure; explain its cause and why
the retry is meaningful.
Conversely, a recovery test can deliberately exit its child before that child's
summary while the parent completes successfully. Preserve the parent's explicit
result and record the missing child summary; do not count the child twice or
infer success for a parent with no unambiguous completion evidence.

For a warning-free claim, require completed successful commands and inspect
compiler/build-script output and lint diagnostics. `-D warnings` promotes enabled
compiler lint warnings to errors; Cargo/build-script diagnostics still require
log inspection. An empty warning search in an incomplete or failing build is not
a clean result. Record packages, features and targets: library-only Clippy does
not cover test-only lints or every feature combination.
Bind the conclusion to the current campaign's expected commands and available
logs. An older partial success or missing diagnostics is not current evidence.

Allocation instrumentation must respect the repository's source policy. An
existing unsafe allocator fixture is not authorization to add another one when
maintained Rust forbids unsafe. Keep such measurement probes in an explicitly
separate audit scope, and retain safe behavioral regressions in the crate.
Record cumulative allocations, live/peak bytes and largest allocation distinctly;
build the attack input before enabling measurement when measuring rejection.

For an isolated probe using real modules, record source hashes and compare
resolved dependency versions, sources and checksums with the application.
Features/profile/target can still differ; matching version identities alone
does not establish an identical executable. Functional tests of permits or
authorization do not measure heap or RSS.

Finish with the concrete supported conclusion and remaining qualification.
Hardware, external services, JS/Python GC, compatible sanitizer targets and long
combined workloads can require separate runs. Record those as unverified, with
their prerequisites, instead of converting inventory coverage into a claim of
global memory safety.
