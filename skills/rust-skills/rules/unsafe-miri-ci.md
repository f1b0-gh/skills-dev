# unsafe-miri-ci

> Use Miri for targeted undefined-behavior checks on supported executions

## Why It Matters

Miri interprets Rust programs and detects many forms of undefined behavior,
including invalid accesses and aliasing violations, on the executions it explores.
A passing run is evidence for the selected code, inputs and model, not proof of
absence of undefined behavior. Safe public APIs can exercise unsafe dependencies
or generated code, so handwritten `unsafe` is not the only useful coverage trigger.

## Select a useful check

Use the project's pinned compatible nightly and Miri component. Choose a focused
package, features and test filter that exercise the relevant memory contract:

```sh
cargo +nightly miri test -p PACKAGE TEST_FILTER
```

Replace the placeholders and nightly alias with the project's supported selection.
Provision tools through its normal workflow. Consult [Miri's documentation](https://github.com/rust-lang/miri)
for current options, aliasing models, seed variation and supported operations;
do not copy a stale set of flags as a universal requirement.

## Evidence limits

- Record the toolchain, feature set, tests actually selected and relevant options.
- Include boundary inputs and varied executions where appropriate. A test that
  never reaches the unsafe operation gives no evidence about it.
- Unsupported FFI, OS interactions or target behavior remain unqualified; keep
  native integration tests and code review for those boundaries.
- Dynamic testing and sanitizers complement rather than replace a safety argument.
  Timing and performance measured under interpretation are not production timings.
- If a broad suite is impractical, choose meaningful focused tests and report the
  omitted coverage. Safe-only caller code is not a reason by itself to skip them.

## See Also

- [unsafe-maybeuninit](unsafe-maybeuninit.md) - initialization invariants
- [unsafe-safety-comment](unsafe-safety-comment.md) - explicit safety arguments
- [test-loom-concurrency](test-loom-concurrency.md) - a different concurrency model
