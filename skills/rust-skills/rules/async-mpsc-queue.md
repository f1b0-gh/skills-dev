# async-mpsc-queue

> Use `mpsc` channels for async message queues between tasks

## Why It Matters

`tokio::sync::mpsc` (multi-producer, single-consumer) is the workhorse channel for async Rust. It provides async send/receive, backpressure via bounded capacity, and efficient cloning of senders. It's the default choice for task-to-task communication.

## Bad

```rust
use std::sync::mpsc;

let (tx, rx) = std::sync::mpsc::channel();

tokio::spawn(async move {
    tx.send("hello").unwrap();  // Unbounded send does not wait for receiver capacity.
});

tokio::spawn(async move {
    let msg = rx.recv().unwrap();  // BLOCKS the executor thread!
});
```

## Good

```rust
use tokio::sync::mpsc;

let (tx, mut rx) = mpsc::channel::<String>(100);

tokio::spawn(async move {
    tx.send("hello".to_string()).await.unwrap();
});

tokio::spawn(async move {
    while let Some(msg) = rx.recv().await {
        println!("Received: {}", msg);
    }
});
```

## Sender Cloning

```rust
use tokio::sync::mpsc;

let (tx, mut rx) = mpsc::channel::<Event>(100);

// Multiple producers
for i in 0..10 {
    let tx = tx.clone();  // Cheap clone
    tokio::spawn(async move {
        tx.send(Event { source: i }).await.unwrap();
    });
}

// Drop original sender so channel closes when all clones dropped
drop(tx);

// Consumer
while let Some(event) = rx.recv().await {
    process(event);
}
// Exit after all strong senders are gone and buffered/reserved messages drain.
```

## Message Handler Pattern

A successful channel send only admits the message. Send a reply after the
promised work completes; the response may itself be a business `Result`.
`ReplyLost` means the caller has no outcome, not that the operation had no effect.
A durable acknowledgement must follow the actual durable commit. Use stable
request IDs and reconciliation if a mutation can outlive its caller.

```rust
use std::future::Future;
use tokio::sync::{mpsc, oneshot};

struct Request<T, R> {
    body: T,
    reply: oneshot::Sender<R>,
}

#[derive(Debug, PartialEq, Eq)]
enum RequestError {
    Closed,
    ReplyLost,
}

async fn run_store<T, R, F, Fut>(mut requests: mpsc::Receiver<Request<T, R>>, process: F)
where
    F: Fn(T) -> Fut,
    Fut: Future<Output = R>,
{
    while let Some(Request { body, reply }) = requests.recv().await {
        let result = process(body).await;
        let _ = reply.send(result); // Caller disappearance does not undo processing.
    }
}

async fn call<T, R>(tx: &mpsc::Sender<Request<T, R>>, body: T) -> Result<R, RequestError> {
    let (reply, response) = oneshot::channel();
    tx.send(Request { body, reply }).await.map_err(|_| RequestError::Closed)?;
    response.await.map_err(|_| RequestError::ReplyLost)
}
```

Bound waiting callers and define deadlines for admission and reply separately,
or carry one absolute deadline through both. Timing out on the reply does not
cancel an already-admitted mutation.

## Graceful Shutdown

Stop new admissions with `close()`, then drain using `recv().await` until
`None`. `try_recv()` returning `Empty` is only a snapshot: outstanding permits
can still deliver work. A `Some(task)` pattern with an enabled shutdown branch
also prevents `else` from detecting a closed channel.

```rust
use std::future::Future;
use tokio::sync::mpsc;
use tokio_util::sync::CancellationToken;

async fn worker<T, F, Fut>(
    mut rx: mpsc::Receiver<T>,
    shutdown: CancellationToken,
    mut process: F,
)
where
    F: FnMut(T) -> Fut,
    Fut: Future<Output = ()>,
{
    let mut draining = false;
    loop {
        tokio::select! {
            biased;
            _ = shutdown.cancelled(), if !draining => {
                rx.close();
                draining = true;
            }
            task = rx.recv() => match task {
                Some(task) => process(task).await,
                None => break,
            }
        }
    }
}
```

This policy finishes the in-flight handler, then processes queued messages and
messages sent with permits obtained before closure. Producers must release or
use those permits; otherwise draining can wait indefinitely. Bound permit
lifetimes and handler duration, or report a grace expiry and the resulting
abandonment policy. Closing or dropping the receiver does not interrupt code
already processing a message. Await the worker to confirm completion.
See [Receiver::close](https://docs.rs/tokio/latest/tokio/sync/mpsc/struct.Receiver.html#method.close).

## WeakSender for Optional Producers

```rust
use tokio::sync::mpsc;

let (tx, mut rx) = mpsc::channel::<Message>(100);
let weak = tx.downgrade();  // Doesn't keep channel alive

tokio::spawn(async move {
    // Strong sender - keeps channel alive
    tx.send("from strong".into()).await.unwrap();
});

tokio::spawn(async move {
    // Weak sender - may fail if strong senders dropped
    if let Some(tx) = weak.upgrade() {
        tx.send("from weak".into()).await.unwrap();
    }
});
```

## Permit Pattern

```rust
// Reserve slot before preparing message
let permit = tx.reserve().await?;

// Now we have guaranteed capacity
let message = expensive_to_create_message();
permit.send(message);  // Uses reserved capacity; does not acknowledge processing.

// Useful when message creation is expensive
// and you don't want to create it if channel is full
```

## Synchronous Producers and Async Consumers

For a synchronous `Write` encoder such as an archive compressor, move the
encoder to an admitted blocking worker and send bounded byte chunks with
`blocking_send`. Never call it from a runtime task. Bound both chunk size and
queue length, counting the producer's blocked chunk and the consumer's current
chunk as well as internal encoder buffers. The consumer owns the async sink.

On sink failure or cancellation, drop the receiver to wake a blocked producer,
then await its handle. A started `spawn_blocking` closure cannot be stopped by
`abort`; closing the channel only interrupts its next send, not arbitrary CPU
work or other blocking I/O. Keep admission owned by the closure until it exits.
Require successful encoder finalization **and** sink completion before publishing
success: channel EOF alone can also mean producer error or panic. An enqueue-only
`Write::flush` does not establish async persistence. Define and acknowledge any
required flush/commit barrier at the consumer.

## See Also

- [async-bounded-channel](./async-bounded-channel.md) - Why bounded channels
- [async-oneshot-response](./async-oneshot-response.md) - Request-response with oneshot
- [async-broadcast-pubsub](./async-broadcast-pubsub.md) - Multiple consumers
