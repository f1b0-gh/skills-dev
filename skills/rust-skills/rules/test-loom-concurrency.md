# test-loom-concurrency

> Use `loom` to check concurrency invariants within an explicit instrumented model

## Why It Matters

Stress tests can miss failures that depend on rare schedules or memory orderings. Loom explores alternative executions of a small instrumented model so that assertions can expose such failures. A passing run is evidence within that model, its exploration limits and Loom's supported behaviors; it is not a proof for every execution of the production system.

## Bad

```rust
// Stress test: might pass a billion times, still doesn't prove correctness
#[test]
fn stress_test_flag() {
    use std::sync::{Arc, atomic::{AtomicBool, Ordering}};
    let flag = Arc::new(AtomicBool::new(false));
    for _ in 0..1_000_000 {
        let flag = Arc::clone(&flag);
        std::thread::spawn(move || {
            flag.store(true, Ordering::Relaxed);
        });
    }
    // races may never surface under the OS scheduler used here
}
```

## Good

This complete `src/lib.rs` example uses the same publication methods in ordinary
and modeled builds. Its contract is a single producer publishing once per
instance; it does not implement reusable messages or multiple producers.
The payload stays atomic so that weakening the flag ordering demonstrates a
logical publication error without introducing unsafe Rust.

```rust
#[cfg(feature = "loom-model")]
use loom::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
#[cfg(not(feature = "loom-model"))]
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

struct Publication {
    ready: AtomicBool,
    payload: AtomicUsize,
}

impl Publication {
    fn new() -> Self {
        // Loom constructors require an active model and are not const.
        Self {
            ready: AtomicBool::new(false),
            payload: AtomicUsize::new(0),
        }
    }

    fn publish(&self, value: usize) {
        self.payload.store(value, Ordering::Relaxed);
        self.ready.store(true, Ordering::Release);
    }

    fn try_read(&self) -> Option<usize> {
        if self.ready.load(Ordering::Acquire) {
            Some(self.payload.load(Ordering::Relaxed))
        } else {
            None
        }
    }
}

#[cfg(all(test, feature = "loom-model"))]
#[test]
fn publication_is_visible() {
    use loom::sync::Arc;
    loom::model(|| {
        let publication = Arc::new(Publication::new());
        let producer = publication.clone();
        let writer = loom::thread::spawn(move || {
            producer.publish(42);
        });

        // Assert before join: join would add its own synchronization.
        if let Some(value) = publication.try_read() {
            assert_eq!(value, 42, "published payload missing");
        }
        writer.join().unwrap();
    });
}
```

Add this configuration to the model example's `Cargo.toml`:

```toml
[features]
loom-model = ["dep:loom"]

[dependencies]
loom = { version = "0.7", optional = true }
```

Then compile the ordinary version and run the model:

```bash
cargo check --lib
cargo test --lib --features loom-model publication_is_visible
```

The example-specific feature avoids setting global `RUSTFLAGS=--cfg loom` for
unrelated dependencies such as Tokio. This is test-only instrumentation; do not
run production services with it enabled. A dedicated `cfg(loom)` setup is also
valid when dependencies and test targets are configured deliberately.

As a negative control, change either the flag's `Release` store or `Acquire`
load to `Relaxed`, one at a time: this test must report `published payload
missing`. The skill's behavioral checks generate both mutations from this exact
block and require the counterexample. If a weakened version passes, inspect the
test, its exploration bounds and any synchronization that masks the bug.

## Key Points

- Keep models small and deterministic; include an assertion of the actual
  invariant, not merely a successful thread join.
- Use Loom primitives for every synchronization operation relevant to the
  model. Mock external I/O and other sources of nondeterminism.
- Record bounds on branches, permutations, preemptions and duration when
  configuring exploration. Exhausting a configured budget is not full coverage.
- Loom has documented memory-model limitations, including incomplete coverage
  of some relaxed-order behaviors. Combine it with other relevant validation;
  do not equate model success with whole-program memory safety or liveness.

See Loom's [limitations and caveats](https://docs.rs/loom/0.7.3/loom/#limitations-and-caveats).

## See Also

- [conc-atomic-ordering](conc-atomic-ordering.md) - choose correct memory orderings
- [test-criterion-bench](test-criterion-bench.md) - benchmark concurrent code after verifying correctness
