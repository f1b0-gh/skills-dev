# async-select-racing

> Use `select!` to race futures and handle the first to complete

## Why It Matters

Sometimes you need the first matching completion from multiple futures: timeout versus operation, cancellation versus work, or competing alternatives. `tokio::select!` polls branches concurrently on one task, then runs the selected handler. It drops directly owned losing futures; stopping spawned work and preserving partial progress require an explicit policy.

## Bad

```rust
// Can't express "whichever finishes first"
async fn fetch_with_fallback() -> Data {
    match fetch_primary().await {
        Ok(data) => data,
        Err(_) => fetch_fallback().await.unwrap(),  // Sequential, not racing
    }
}

// Manual timeout is error-prone
async fn fetch_with_timeout() -> Option<Data> {
    let start = Instant::now();
    loop {
        if start.elapsed() > Duration::from_secs(5) {
            return None;
        }
        // How do we check timeout while awaiting?
    }
}
```

## Good

```rust
use tokio::select;

async fn fetch_with_timeout() -> Result<Data, Error> {
    select! {
        result = fetch_data() => result,
        _ = tokio::time::sleep(Duration::from_secs(5)) => {
            Err(Error::Timeout)
        }
    }
}

async fn fetch_with_fallback() -> Data {
    select! {
        result = fetch_primary() => {
            match result {
                Ok(data) => data,
                Err(_) => fetch_fallback().await.unwrap()
            }
        }
        _ = tokio::time::sleep(Duration::from_secs(1)) => {
            // Primary too slow, use fallback
            fetch_fallback().await.unwrap()
        }
    }
}
```

## select! Syntax

```rust
select! {
    // Pattern = future => handler
    result = async_operation() => {
        // Handle result
        println!("Got: {:?}", result);
    }

    // Can bind with pattern matching
    Ok(data) = fallible_operation() => {
        process(data);
    }

    // Conditional branches with if guards
    msg = channel.recv(), if should_receive => {
        handle_message(msg);
    }

    // else branch for when all futures are disabled
    else => {
        println!("All branches disabled");
    }
}
```

## Cancellation Behavior

An owned losing future is dropped and never polled again; it does not resume
at its next `.await`. Synchronous drop guards run, but async cleanup may not.
Dropping a borrowed future reference leaves its owner intact. Dropping a
`JoinHandle` detaches the task, which can continue running. None of these actions
roll back external effects already performed.

```rust
use std::future::Future;

async fn race<T>(first: impl Future<Output = T>, second: impl Future<Output = T>) -> T {
    tokio::select! {
        result = first => result,
        result = second => result,
    }
}
```

Cancellation safety concerns preserving progress when an unfinished operation
is dropped and recreated. For example, `mpsc::Receiver::recv` is safe to use in
this loop; restarting `read_exact` or `write_all` can lose track of partially
transferred bytes. Retain state or finish the operation when partial progress
matters. See Tokio's [cancellation safety guidance](https://docs.rs/tokio/latest/tokio/macro.select.html#cancellation-safety).

## Biased Selection

```rust
// By default, select! randomly picks when multiple are ready
// Use biased mode for deterministic priority
select! {
    biased;  // Check branches in order

    msg = high_priority.recv() => handle_high(msg),
    msg = low_priority.recv() => handle_low(msg),
}

// Without biased, both channels have equal chance
// when both have messages ready
```

## Loop with select!

Match `None` explicitly. A `Some(cmd)` pattern disables the receive branch on
closure, but `else` still cannot run while the shutdown branch remains enabled.
This example drains buffered commands after sender closure unless shutdown is
requested. When both branches are ready, cancellation takes priority and
discards any queued commands.

```rust
use std::future::Future;
use tokio::sync::mpsc;
use tokio_util::sync::CancellationToken;

#[derive(Debug, PartialEq, Eq)]
enum StopReason {
    ChannelClosed,
    Cancelled,
}

async fn event_loop<T, F, Fut>(
    mut commands: mpsc::Receiver<T>,
    shutdown: CancellationToken,
    mut process_command: F,
) -> StopReason
where
    F: FnMut(T) -> Fut,
    Fut: Future<Output = ()>,
{
    loop {
        tokio::select! {
            biased; // Observe shutdown before an always-ready input queue.
            _ = shutdown.cancelled() => return StopReason::Cancelled,
            command = commands.recv() => {
                match command {
                    Some(command) => process_command(command).await,
                    None => return StopReason::ChannelClosed,
                }
            }
        }
    }
}
```

Once selected, the handler runs outside the race. This policy finishes the
current command before observing shutdown; it gives no shutdown deadline if
that handler never finishes. Pass cancellation into the handler or supervise
it separately if the application needs interruptible work, preserving its
partial-progress semantics.

## Racing Multiple of Same Type

Dynamic races need pinned futures and an explicit empty-input policy. The
first completion may be an error; this is not a search for the first success.

```rust
use std::future::Future;

async fn fastest_response<F: Future>(operations: Vec<F>) -> Option<F::Output> {
    if operations.is_empty() {
        return None;
    }
    let pinned = operations.into_iter().map(Box::pin);
    let (result, _index, remaining) = futures::future::select_all(pinned).await;
    drop(remaining); // Directly owned futures are dropped; task handles detach.
    Some(result)
}
```

Bound the number of inputs separately. If the contract requires the first
successful response, inspect completions until success or until all operations
fail, instead of treating the first error as the end of the race.

## Common Patterns

```rust
// Timeout
select! {
    result = operation() => result,
    _ = sleep(Duration::from_secs(5)) => Err(Timeout),
}

// Cancellation
select! {
    result = operation() => result,
    _ = cancel_token.cancelled() => Err(Cancelled),
}

// Interval with cancellation
let mut interval = tokio::time::interval(Duration::from_secs(1));
loop {
    select! {
        _ = shutdown.cancelled() => break,
        _ = interval.tick() => {
            do_periodic_work().await;
        }
    }
}
```

## See Also

- [async-cancellation-token](./async-cancellation-token.md) - Cancellation patterns
- [async-join-parallel](./async-join-parallel.md) - All futures, not racing
- [async-bounded-channel](./async-bounded-channel.md) - Channel operations in select
