# async-cancellation-token

> Use `CancellationToken` for graceful shutdown and task cancellation

## Why It Matters

Dropping a `JoinHandle` doesn't cancel the task—it just detaches it. For graceful shutdown, you need explicit cancellation. `tokio_util::sync::CancellationToken` provides a cooperative cancellation mechanism that tasks can check and respond to, enabling clean resource cleanup.

Dropping the token itself does not request cancellation. Use `cancel()` or a
`drop_guard()` for that policy, then await owned tasks when completion must be
confirmed. A token cannot interrupt an arbitrary blocking read or a started
`spawn_blocking` closure; those need their own interruption or lifetime policy.

## Bad

```rust
// Dropping handle doesn't stop the task
let handle = tokio::spawn(async {
    loop {
        do_work().await;
    }
});

drop(handle);  // Task continues running in background!

// Using bool flag - not async-aware
let running = Arc::new(AtomicBool::new(true));

tokio::spawn({
    let running = running.clone();
    async move {
        while running.load(Ordering::Relaxed) {
            do_work().await;  // Can't wake up if blocked here
        }
    }
});

running.store(false, Ordering::Relaxed);
// Task won't stop until current do_work() completes
```

## Good

```rust
use tokio_util::sync::CancellationToken;

let token = CancellationToken::new();

let handle = tokio::spawn({
    let token = token.clone();
    async move {
        loop {
            tokio::select! {
                _ = token.cancelled() => {
                    println!("Shutting down gracefully");
                    cleanup().await;
                    break;
                }
                _ = do_work() => {
                    // Work completed
                }
            }
        }
    }
});

// Later: trigger cancellation
token.cancel();
handle.await?;  // Task completes cleanly
```

## CancellationToken API

```rust
use tokio_util::sync::CancellationToken;

// Create token
let token = CancellationToken::new();

// Clone for sharing (cheap Arc-based clone)
let token2 = token.clone();

// Check if cancelled (non-blocking)
if token.is_cancelled() {
    return;
}

// Wait for cancellation (async)
token.cancelled().await;

// Trigger cancellation
token.cancel();

// Child tokens - cancelled when parent is cancelled
let child = token.child_token();
```

## Hierarchical Cancellation

```rust
use tokio_util::sync::CancellationToken;

let child = {
    let parent = CancellationToken::new();
    let _cancel_on_exit = parent.clone().drop_guard();
    parent.child_token()
}; // The guard requests cancellation, including on error/unwind exits.
assert!(child.is_cancelled());

let uncancelled_child = {
    let parent = CancellationToken::new();
    parent.child_token()
}; // Dropping just the parent token does not request cancellation.
assert!(!uncancelled_child.is_cancelled());

// Cancellation is a request. Retain and await task handles separately when
// the owner must confirm that connection/worker cleanup actually completed.
```

## Graceful Shutdown Pattern

Own the task set and inspect every completion, including failures during
cleanup. This supervisor stops on cancellation or the first worker completion,
requests sibling cancellation, then gives the entire set one shared grace
period. Its report preserves failures and separately records grace expiry;
success means `!report.timed_out && report.failures.is_empty()`.

```rust
use std::time::Duration;
use tokio::{task::{JoinError, JoinSet}, time::timeout};
use tokio_util::sync::CancellationToken;

#[derive(Debug)]
enum TaskFailure {
    Work(&'static str),
    Join(JoinError),
}

#[derive(Debug, Default)]
struct ShutdownReport {
    timed_out: bool,
    failures: Vec<TaskFailure>,
}

fn record(result: Result<Result<(), &'static str>, JoinError>, report: &mut ShutdownReport) {
    match result {
        Ok(Ok(())) => {}
        Ok(Err(error)) => report.failures.push(TaskFailure::Work(error)),
        Err(error) => report.failures.push(TaskFailure::Join(error)),
    }
}

async fn supervise(
    mut tasks: JoinSet<Result<(), &'static str>>,
    shutdown: CancellationToken,
    grace: Duration,
) -> ShutdownReport {
    let _cancel_on_exit = shutdown.clone().drop_guard();
    let mut report = ShutdownReport::default();
    tokio::select! {
        _ = shutdown.cancelled() => {}
        result = tasks.join_next() => {
            if let Some(result) = result {
                record(result, &mut report);
            }
        }
    }
    shutdown.cancel();

    if timeout(grace, async {
        while let Some(result) = tasks.join_next().await {
            record(result, &mut report);
        }
    }).await.is_err() {
        report.timed_out = true;
        tasks.abort_all();
        // Abort is a request. Join to confirm synchronous resource release.
        while let Some(result) = tasks.join_next().await {
            if matches!(&result, Err(error) if error.is_cancelled()) {
                continue; // Forced cancellation is already reported by timed_out.
            }
            record(result, &mut report);
        }
    }
    report
}
```

Workers must observe a child token and yield to the runtime. Bound the number
of admitted tasks separately. Await the supervisor to obtain the report;
dropping its future requests cancellation/abort but cannot await cleanup.
After grace expiry, abort-and-join confirms task destruction, not successful
async cleanup. The grace period is not a hard bound on total shutdown time:
blocking code and started `spawn_blocking` jobs cannot be forcibly stopped this
way. Isolate such work or provide an operation-specific interruption mechanism.

If shutdown originates from an OS signal, own and supervise the listener too;
propagate listener errors instead of panicking inside a detached task. See
Tokio's [JoinSet](https://docs.rs/tokio/latest/tokio/task/struct.JoinSet.html).

## DropGuard Pattern

```rust
use tokio_util::sync::CancellationToken;

// Auto-cancel on drop
let token = CancellationToken::new();
let guard = token.clone().drop_guard();

tokio::spawn({
    let token = token.clone();
    async move {
        token.cancelled().await;
        println!("Cancelled!");
    }
});

drop(guard);  // Automatically calls token.cancel()
```

## See Also

- [async-joinset-structured](./async-joinset-structured.md) - Managing multiple tasks
- [async-select-racing](./async-select-racing.md) - select! for cancellation
- [async-tokio-runtime](./async-tokio-runtime.md) - Runtime shutdown
