# async-bounded-channel

> Bound queue length and account separately for payloads and waiting producers

## Why It Matters

Unbounded channels can exhaust memory when producers outpace consumers. Bounded channels limit queued items and apply backpressure, but do not bound bytes held by arbitrary waiting producers, active workers or retained results. A system-wide memory claim needs limits for those owners and for each payload's allocated capacity.

## Bad

```rust
use tokio::sync::mpsc;

// Unbounded channel - can grow forever
let (tx, mut rx) = mpsc::unbounded_channel::<Message>();

// Fast producer, slow consumer = unbounded memory growth
tokio::spawn(async move {
    loop {
        let msg = generate_message();
        tx.send(msg).unwrap();  // No backpressure; fails if the receiver closes.
    }
});

tokio::spawn(async move {
    while let Some(msg) = rx.recv().await {
        slow_process(msg).await;  // Can't keep up
    }
});
// Memory grows unboundedly until crash
```

## Good

```rust
use tokio::sync::mpsc;

// Bounded channel - backpressure when full
let (tx, mut rx) = mpsc::channel::<Message>(100);  // Max 100 items

// Producer waits when channel full
tokio::spawn(async move {
    loop {
        let msg = generate_message();
        // Suspends this task when full; does not block the executor thread.
        if tx.send(msg).await.is_err() {
            break; // Receiver closure is a normal stop condition.
        }
    }
});

tokio::spawn(async move {
    while let Some(msg) = rx.recv().await {
        slow_process(msg).await;
    }
});
// At most 100 queued messages; this producer and consumer also hold messages.
```

## Choosing Buffer Size

Acquire admission before constructing large payloads or spawning unbounded
producer tasks. `reserve().await` can protect construction order, but arbitrary
waiting tasks still need their own bound. Use `try_send`/`try_reserve` when
overload should be rejected. If a byte budget covers processing too, retain
its permit until the payload and any covered copies are released.

```rust
// Too small: frequent blocking, reduced throughput
let (tx, rx) = mpsc::channel::<Item>(1);

// Too large: delayed backpressure, memory waste
let (tx, rx) = mpsc::channel::<Item>(1_000_000);

// Guidelines:
// - Start with expected burst size
// - Measure actual usage in production
// - Err on the smaller side initially

// Small items, high throughput
let (tx, rx) = mpsc::channel::<u64>(1000);

// Large items, moderate throughput
let (tx, rx) = mpsc::channel::<LargeStruct>(100);

// Low latency requirement
let (tx, rx) = mpsc::channel::<Command>(10);
```

## Handling Full Channel

Choose an explicit policy: `try_send` returns the payload on `Full`/`Closed`,
`send` waits for capacity, and `send_timeout` returns it on timeout or closure.
Wrapping `send(message)` in an external timeout drops the message when the send
future is cancelled. This absolute-deadline version reserves first and returns
the original payload on an admission failure:

```rust
use tokio::sync::mpsc;
use tokio::time::{timeout_at, Instant};

#[derive(Debug)]
enum AdmissionError<T> {
    Closed(T),
    TimedOut(T),
}

async fn send_before<T>(
    tx: &mpsc::Sender<T>,
    message: T,
    deadline: Instant,
) -> Result<(), AdmissionError<T>> {
    match timeout_at(deadline, tx.reserve()).await {
        Ok(Ok(permit)) => {
            permit.send(message);
            Ok(())
        }
        Ok(Err(_)) => Err(AdmissionError::Closed(message)),
        Err(_) => Err(AdmissionError::TimedOut(message)),
    }
}
```

Dropping this entire function's future still drops its owned message. To retain
it across external cancellation, keep the payload in the caller and race only
`reserve()` before moving the payload into the permit. Cancelling a reservation
loses its position in the waiter queue.

A permit acquired before `Receiver::close()` can still send. Its send method
has no error return, but neither it nor `send` returning `Ok` proves the receiver
processed the message. Use a separate completion acknowledgement when needed.
See [Sender](https://docs.rs/tokio/latest/tokio/sync/mpsc/struct.Sender.html).

## Channel Types

```rust
// mpsc: many producers, single consumer
let (tx, rx) = mpsc::channel::<Message>(100);
let tx2 = tx.clone();  // Can clone sender

// oneshot: single value, one producer, one consumer
let (tx, rx) = oneshot::channel::<Response>();
tx.send(response);  // Can only send once

// broadcast: multiple consumers, each gets all messages
let (tx, _) = broadcast::channel::<Event>(100);
let mut rx1 = tx.subscribe();
let mut rx2 = tx.subscribe();

// watch: single latest value, multiple consumers
let (tx, rx) = watch::channel::<State>(initial);
// Receivers see latest value, not all values
```

## Worker Pool Pattern

Use one receiver owner to dispatch into a bounded `JoinSet`. This avoids
sharing a single-consumer receiver through a mutex, returns every processing
outcome, and preserves task panics as `JoinError`. The input channel supplies
queue backpressure; `parallelism` bounds active or completed-but-unjoined tasks.
Results are returned in join-completion order, not input order.
The returned `Vec` collects every outcome: this example bounds queued and active
work, not the total result history. For an indefinite stream, use a bounded
result consumer and include completed, unread results in the byte budget.

```rust
use std::{future::Future, num::NonZeroUsize};
use tokio::{sync::mpsc, task::{JoinError, JoinSet}};

type Outcome<R, E> = Result<Result<R, E>, JoinError>;

async fn process_with_workers<T, R, E, F, Fut>(
    mut items: mpsc::Receiver<T>,
    parallelism: NonZeroUsize,
    process: F,
) -> Vec<Outcome<R, E>>
where
    T: Send + 'static,
    R: Send + 'static,
    E: Send + 'static,
    F: Fn(T) -> Fut,
    Fut: Future<Output = Result<R, E>> + Send + 'static,
{
    let mut workers = JoinSet::new();
    let mut results = Vec::new();
    loop {
        if workers.len() == parallelism.get()
            && let Some(result) = workers.join_next().await
        {
            results.push(result);
        }
        match items.recv().await {
            Some(item) => { workers.spawn(process(item)); }
            None => break,
        }
    }
    while let Some(result) = workers.join_next().await {
        results.push(result);
    }
    results
}
```

This is a finite-batch, collect-all policy: producers must eventually close the
input. It deliberately continues after a processing error or task panic. The
result `Vec` and producer-held inputs still require memory budgets; for an
unbounded stream, consume outcomes incrementally instead. Dropping the pool
future requests abort of its async tasks but does not join their cleanup. For
blocking encoders, use the separately owned blocking-worker lifecycle described
in [async-mpsc-queue](./async-mpsc-queue.md), not this async pool.

## See Also

- [async-mpsc-queue](./async-mpsc-queue.md) - Multi-producer patterns
- [async-oneshot-response](./async-oneshot-response.md) - Request-response pattern
- [async-watch-latest](./async-watch-latest.md) - Latest-value broadcasting
