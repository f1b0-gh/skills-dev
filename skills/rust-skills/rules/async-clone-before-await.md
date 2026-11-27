# async-clone-before-await

> Clone shared owners when ownership requires it; borrowing across await can be valid

## Why It Matters

An await does not by itself require cloning borrowed data. A shared reference
can be `Send` when its referent is `Sync`; owning an `Arc` can keep that referent
alive across suspension. Cloning `Rc` does not make it `Send`, and `Arc<T>` is
not a workaround for a `T` that lacks the required thread-safety traits.

## Bad

```rust
use std::sync::Arc;

async fn count_nonzero(values: Arc<Vec<u64>>) -> usize {
    // Unnecessary payload copy merely because an await follows.
    let copy = values.as_ref().clone();
    tokio::task::yield_now().await;
    copy.iter().filter(|value| **value != 0).count()
}
```

## Good

```rust
use std::sync::Arc;

async fn count_nonzero(values: Arc<Vec<u64>>) -> usize {
    let borrowed = values.as_slice();
    tokio::task::yield_now().await;
    borrowed.iter().filter(|value| **value != 0).count()
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), tokio::task::JoinError> {
    let values = Arc::new(vec![0, 2, 3]);
    // Clone the owner because the caller keeps it and the spawned task needs it.
    let worker = tokio::spawn(count_nonzero(Arc::clone(&values)));
    assert_eq!(worker.await?, 2);
    assert_eq!(values.len(), 3);
    Ok(())
}
```

## Choosing the Ownership Boundary

Move an already-owned value into the future when the caller no longer needs it.
Clone an `Arc` when owners must coexist. Clone a payload when an independent
snapshot is required, and account for its memory cost. Inspect the actual
compiler lifetime and `Send` diagnostic instead of adding clones preemptively.
Use a local task when the design intentionally retains non-`Send` state.

## Mutex Guards and Snapshots

For short operations, end synchronous guard scopes before an await. A Tokio
mutex can intentionally protect a complete asynchronous transaction. Extracting
a snapshot and reacquiring the mutex is valid only if interleaving is acceptable
or a version/CAS check rejects stale publication. Two increments separated by
an await are not equivalent to one serialized operation merely because both
versions compile. See the transaction guidance in `async-no-lock-await`.

## See Also

- [async-no-lock-await](./async-no-lock-await.md) - Preserve transactional lock scopes
- [own-arc-shared](./own-arc-shared.md) - Shared ownership and thread-safety bounds
- [own-rc-single-thread](./own-rc-single-thread.md) - Intentional single-thread ownership
- [async-spawn-blocking](./async-spawn-blocking.md) - Blocking work and cancellation
