---
name: rust-discipline
description: Use when implementing or reviewing Rust changes under strict production safety, typed-error, resource-ownership, and dependency constraints.
license: MIT
---

# Rust discipline

Apply strict Rust defaults to the requested change. First read the consumer's
instructions, manifests and relevant code: they define supported targets,
dependencies and validation commands. Explicit user requirements take precedence.
Keep the work proportional to the changed behavior.

## Production contract

- Forbid authored `unsafe` code and panicking `unwrap`, `expect`, `panic!`,
  `unreachable!` and `unimplemented!` in production. An invariant comment does not
  make a panic recoverable. Use a typed `Result`/`Option`, validate at the boundary,
  or encode the invariant so the invalid state is unrepresentable. Ordinary
  `unwrap_or` defaults are a separate choice: preserve required errors.
- Preserve error causes as typed sources. Reuse the existing error model; a new
  error crate or a stringified cause is not a substitute for understanding it.
- Keep pure logic separate from I/O. Preserve existing `no_std`/`alloc` boundaries;
  host adapters may use `std` where the project permits it.
- Reuse dependency versions, features and target restrictions. Preserve exact pins
  where required. Examples using a crate do not authorize adding it.
- Inherit workspace lints where present. Fix warnings at their source. A deliberate
  lint exception must follow project policy and be narrow and justified; it does
  not override the production panic or unsafe prohibition.

Tests may use assertions; additional restrictions on tests and examples come from
the consumer. Vendored code and dependency-generated code require separate scope
and attribution; do not silently weaken authored-code rules to accommodate them.

## Design and resource review

Prefer an existing module over another abstraction or crate. A new crate needs a
concrete consumer, release boundary, or dependency/portability boundary that a
module cannot preserve. Preserve public ownership and transaction contracts when
reducing clones or changing representations.

For concurrency, memory or cleanup changes, identify each retaining owner, its
admission limit and its release point. A bounded queue does not bound arbitrary
waiting producers or retained replies. A timeout does not stop started blocking
work. Keep permits with the work or data they cover, including completed unread
results. Destroy covered buffers before releasing their permits; struct fields
drop in declaration order. Measure allocation/performance claims on the relevant
workload, including small inputs and transient copies.

The optional companion [rust-skills](../rust-skills/SKILL.md) supplies detailed
rules. For resource changes, read its
[ownership checklist](../rust-skills/references/memory-concurrency-review.md).
If the companion is not installed, apply the contract above and the consumer's
existing guidance; do not invent a missing rule or fetch tools automatically.
Generic reference examples never relax this discipline's production constraints.

## Select validation by impact

| Change | Evidence to select |
|---|---|
| Prose only | Diff and affected links/commands; no Rust build for a spelling fix |
| Private implementation | Focused regression and error cases, affected formatting and production Clippy |
| Public API or shared types | Owner and directly affected consumer checks |
| Parsing or authorization | Malformed/adversarial input, boundaries and required refusals |
| Persistence, retries or concurrency | Failure, cancellation, replay and actual cleanup/capacity reuse |
| Dependencies or target support | Selected feature graph, toolchain and affected target checks |

Use the repository's actual commands. Where Cargo checks apply, select explicit
packages and supported production targets; for example `cargo fmt -p PACKAGE
--check` and `cargo clippy --locked -p PACKAGE --lib --bins --no-deps -- -D warnings`,
omitting target selectors that do not exist. Do not impose a foreign validation
script, whole-workspace campaign, all-features build or new test framework.

Report the concrete change or finding, evidence actually obtained, and material
remaining limits. Zero selected tests, compilation and executed behavioral tests
are different outcomes. Do not claim feature/platform/provider coverage that was
not exercised.
