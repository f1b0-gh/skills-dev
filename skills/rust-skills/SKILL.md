---
name: rust-skills
description: Use when choosing Rust ownership, error-handling, async, API, memory, or performance patterns during implementation, refactoring, or code review.
license: MIT
metadata:
  upstream-author: leonardomso
  upstream-version: "1.5.6"
---

# Rust reference

Use this library to answer a concrete design or implementation question. Read the
consumer's instructions and toolchain/dependency constraints first, then only the
relevant rules. The [complete index](references/rule-index.md) contains 265 rules;
search by topic or rule prefix instead of loading the whole collection.

## Choose the relevant material

| Task | Start here |
|---|---|
| Ownership, copies, shared data | [Borrowing](rules/own-borrow-over-clone.md), [clone review](rules/anti-clone-excessive.md) |
| Failures and API errors | [Typed sources](rules/err-source-chain.md), [Result](rules/err-result-over-panic.md) |
| Cancellation, blocking work, retained buffers | [Memory and concurrency review](references/memory-concurrency-review.md) |
| Explicit aggregate memory audit | [Evidence and coverage](references/memory-audit-evidence.md) |
| Performance change | [Profile first](rules/perf-profile-first.md), then the measured bottleneck's rules |
| Traits, conversions, serialization or layout | Search `api-`, `trait-`, `conv-`, `serde-`, `type-` in the index |
| Tests, lints, modules or documentation | Search `test-`, `lint-`, `proj-`, `doc-` in the index |

## Interpret examples in context

The consumer's explicit policy controls. “Good” in an imported rule illustrates
that rule's technique; it is not approval to introduce production panics, unsafe
code, new dependencies, a different runtime, or a different release profile.
Under a no-panic/no-unsafe policy, use typed failures and safe alternatives even
when an upstream example discusses an invariant panic or an unsafe implementation.

Some snippets are partial demonstrations and some require optional crates or a
nightly feature. Check the actual API, MSRV and feature set before adopting one.
Keep a stable implementation when the consumer requires stable Rust. Do not change
toolchains, panic strategy, LTO, or allocation dependencies merely to match an
example. Do not treat a historical benchmark number as a prediction.

Preserve semantics when optimizing: `zip` truncates to the shorter input; an
approximation, changed overflow behavior, or earlier permit release is not an
equivalent implementation. Verify the relevant contract with focused tests and
measure the claimed improvement. For a small question, answer from the relevant
rule without starting a repository-wide audit.

The imported source revision and original hashes are recorded in
[UPSTREAM.json](UPSTREAM.json). Local revisions and their scope are documented in
the repository's provenance records. The library is reviewed guidance, not a claim
that all examples have been compiled or every supported platform qualified.
