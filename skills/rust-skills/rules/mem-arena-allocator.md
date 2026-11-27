# mem-arena-allocator

> Consider arena allocation when many values share a bounded lifetime

## Why It Matters

An arena can amortize allocations when a batch of values becomes unreachable
at the same time. Its retained chunks, peak allocation and escaping results still
need budgets. An arena is a measured representation choice, not a default for
every parser or request handler.

`bumpalo::Bump::alloc` does **not** run allocated values' destructors when the arena
resets or drops. A normal `String`, `Vec`, file or other owning field placed there
can leak its external resources. Prefer borrowed/arena-backed data, or keep an
appropriate dropping owner such as `bumpalo::boxed::Box` alive outside the arena.
That optional API requires its crate feature. See [Bump's destructor contract](https://docs.rs/bumpalo/latest/bumpalo/struct.Bump.html#no-drops).

## Good

```rust
use bumpalo::Bump;

fn lengths(input: &str) -> Vec<usize> {
    let arena = Bump::new();
    // Borrowed str values have no owned resources requiring Drop.
    let words: Vec<&str> = input.split_whitespace()
        .map(|word| &*arena.alloc_str(word))
        .collect();
    words.iter().map(|word| word.len()).collect()
}
```

This deliberately simple example copies strings to demonstrate ownership, not a
speedup over iterating the input directly. Retain an arena only when the real
workload benefits.

## Reusable scratch ownership

```rust
use bumpalo::Bump;
use std::cell::{BorrowMutError, RefCell};

thread_local! {
    static SCRATCH: RefCell<Bump> = RefCell::new(Bump::with_capacity(4096));
}

fn with_scratch<T>(f: impl FnOnce(&Bump) -> T) -> Result<T, BorrowMutError> {
    SCRATCH.with(|scratch| {
        let mut arena = scratch.try_borrow_mut()?;
        arena.reset(); // Also clears remnants of an earlier unwinding callback.
        let result = f(&arena); // T cannot borrow from the callback's arena argument.
        arena.reset(); // Callback borrow has ended before reset.
        Ok(result)
    })
}
```

The owner resets after the callback returns; the callback must not reset the
same arena through another `RefCell` borrow. Reentrant use returns a borrow error.
An unwinding callback delays reset until a later invocation or thread exit;
this does not run destructors for bump-allocated values. Retain owned resources
outside the arena. Bound batch allocation separately from this reuse policy.

## Measure the tradeoff

Record allocation count, retained chunk capacity, tiny-input cost and peak overlap
when copying results out. Reset can release multiple chunks; do not promise a
universal O(1) reset or complete resource cleanup. Preserve a simple owned
representation when shared lifetime is not the measured bottleneck.

## See Also

- [mem-with-capacity](mem-with-capacity.md) - admission before allocation
- [mem-reuse-collections](mem-reuse-collections.md) - reuse existing buffers
- [perf-profile-first](perf-profile-first.md) - measure the actual workload
