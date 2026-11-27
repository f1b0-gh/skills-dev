# async-try-join

> Use `try_join!` for concurrent fallible operations with early return on error

## Why It Matters

When running multiple fallible operations concurrently, `try_join!` returns `Err` as soon as a branch returns an error. It polls branches on the same task: concurrency does not imply parallel execution, and a blocking branch stalls its siblings. For dynamic collections, `futures::future::try_join_all` has similar fail-fast semantics; bound admission separately for large inputs.

## Bad

```rust
// Sequential - slow and no early return benefit
async fn fetch_all() -> Result<(A, B, C)> {
    let a = fetch_a().await?;  // If this fails, we wait for nothing
    let b = fetch_b().await?;  // But if this fails, we waited for A
    let c = fetch_c().await?;
    Ok((a, b, c))
}

// join! waits for every branch and returns their individual Results
async fn fetch_all() -> (Result<A>, Result<B>, Result<C>) {
    let (a, b, c) = join!(fetch_a(), fetch_b(), fetch_c());
    // All complete even if first one failed
    (a, b, c)  // Now we have to handle three Results
}
```

## Good

```rust
use tokio::try_join;

async fn fetch_all() -> Result<(A, B, C)> {
    // Concurrent AND fail-fast
    let (a, b, c) = try_join!(
        fetch_a(),
        fetch_b(),
        fetch_c(),
    )?;

    Ok((a, b, c))
}

// For dynamic collections
use futures::future::try_join_all;

async fn fetch_users(ids: &[u64]) -> Result<Vec<User>> {
    let futures: Vec<_> = ids.iter()
        .map(|id| fetch_user(*id))
        .collect();

    try_join_all(futures).await
}
```

## Error Handling Patterns

```rust
// Different error types - need common error type
use futures::TryFutureExt;

async fn mixed_operations() -> Result<(A, B), Error> {
    let (a, b) = try_join!(
        fetch_a().map_err(Error::from),  // Convert errors
        fetch_b().map_err(Error::from),
    )?;
    Ok((a, b))
}

// Return on the first error; otherwise collect every successful value.
// This does not roll back side effects from completed operations.
async fn all_or_nothing(ids: &[u64]) -> Result<Vec<User>> {
    try_join_all(ids.iter().map(|id| fetch_user(*id))).await
}

// Collect successes, log failures
async fn best_effort(ids: &[u64]) -> Vec<User> {
    let results = futures::future::join_all(
        ids.iter().map(|id| fetch_user(*id))
    ).await;

    results.into_iter()
        .filter_map(|r| match r {
            Ok(user) => Some(user),
            Err(e) => {
                log::warn!("Failed to fetch user: {}", e);
                None
            }
        })
        .collect()
}
```

## Cancellation Behavior

On error, directly owned sibling futures are dropped and never polled again;
they do not resume at a later `.await`. Synchronous drop guards run, but async
cleanup after an `.await` may never execute. Dropping a spawned task's
`JoinHandle` only detaches that task; external operations and completed side
effects also need their own cancellation or recovery policy.

```rust
async fn with_cancellation() -> Result<()> {
    try_join!(
        async {
            fetch_a().await?;
            cleanup_a().await;  // May not run if other future fails
            Ok::<_, Error>(())
        },
        async {
            fetch_b().await?;
            cleanup_b().await;  // May not run if other future fails
            Ok::<_, Error>(())
        },
    )?;

    Ok(())
}

// Use Drop for synchronous release; supervise and await required async cleanup.
```

## With Timeout

Wrap the join in an async block so the timer owns a future. Pass one absolute
deadline when preparation and multiple stages share a budget; creating a fresh
duration at each stage would restart it. Keep operation errors distinct from
deadline expiry. The complete example below is compiled and executed by the
behavioral checks.

```rust
use std::future::Future;
use tokio::time::{timeout, timeout_at, Duration, Instant};

#[derive(Debug, PartialEq, Eq)]
enum FetchError {
    Backend(&'static str),
    Timeout,
}

async fn join_before<A, B>(
    deadline: Instant,
    first: impl Future<Output = Result<A, FetchError>>,
    second: impl Future<Output = Result<B, FetchError>>,
) -> Result<(A, B), FetchError> {
    timeout_at(deadline, async { tokio::try_join!(first, second) })
        .await
        .map_err(|_| FetchError::Timeout)?
}

// Separate per-operation budgets, starting when these branches are polled.
async fn individual_timeouts<A, B>(
    budget: Duration,
    first: impl Future<Output = Result<A, FetchError>>,
    second: impl Future<Output = Result<B, FetchError>>,
) -> Result<(A, B), FetchError> {
    tokio::try_join!(
        async { timeout(budget, first).await.map_err(|_| FetchError::Timeout)? },
        async { timeout(budget, second).await.map_err(|_| FetchError::Timeout)? },
    )
}
```

Tokio timers cannot preempt code that does not yield. A timeout drops the
directly owned future; it does not prove that a spawned task or blocking job
has stopped. See Tokio's [try_join!](https://docs.rs/tokio/latest/tokio/macro.try_join.html)
and [timeout](https://docs.rs/tokio/latest/tokio/time/fn.timeout.html) documentation.

## try_join! vs FuturesUnordered

```rust
use futures::stream::{FuturesUnordered, StreamExt};

// try_join!: wait for all, fail fast
let (a, b, c) = try_join!(fa, fb, fc)?;

// FuturesUnordered: process as they complete
let mut futures = FuturesUnordered::new();
futures.push(fetch_a());
futures.push(fetch_b());
futures.push(fetch_c());

while let Some(result) = futures.next().await {
    match result {
        Ok(data) => process(data),
        Err(e) => return Err(e),  // Can fail fast manually
    }
}
```

## See Also

- [async-join-parallel](./async-join-parallel.md) - Non-fallible concurrent futures
- [async-select-racing](./async-select-racing.md) - First-to-complete semantics
- [err-question-mark](./err-question-mark.md) - Error propagation
