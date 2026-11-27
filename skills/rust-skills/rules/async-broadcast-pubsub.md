# async-broadcast-pubsub

> Use bounded broadcast for pub/sub with an explicit lag policy

## Why It Matters

Tokio broadcast gives each subscribed receiver its own cursor into bounded
history. It does not guarantee every subscriber receives every message: a slow
receiver loses old messages and receives `RecvError::Lagged`. A closed channel is
a different condition. `while let Ok(event) = recv().await` silently terminates on
lag, permanently losing subsequent updates.

## Good

This consumer explicitly reports loss and continues with the retained events.
It is appropriate for best-effort notifications. A correctness-critical consumer
needs a replay or resynchronization policy rather than simply continuing.

```rust
use tokio::sync::broadcast::{self, error::RecvError};

async fn receive_events<T: Clone>(
    rx: &mut broadcast::Receiver<T>,
    mut on_event: impl FnMut(T),
    mut on_lag: impl FnMut(u64),
) {
    loop {
        match rx.recv().await {
            Ok(event) => on_event(event),
            Err(RecvError::Lagged(count)) => on_lag(count),
            Err(RecvError::Closed) => break,
        }
    }
}
```

Create receivers before sending if they must observe those sends. A send succeeds
when at least one receiver exists; it is not an acknowledgement that each receiver
processed the event. Messages need `Clone` because receivers receive owned values.
If spawning consumers, retain their task handles and define shutdown ownership.

## Choose the channel by the contract

| Need | Candidate |
|---|---|
| One consumer receives each queued item | Bounded mpsc |
| Multiple subscribers observe events, with explicit loss/replay handling | Broadcast |
| Consumers only need the latest state | Watch |
| Durable delivery or acknowledged processing | A protocol/storage layer providing those guarantees |

Channel capacity is an item limit, not a byte budget for payloads, clones and
consumer-held results. Measure and bound those owners separately.

Test lag followed by resumed receipt, sender closure, subscriber timing and the
chosen resynchronization behavior. See [Tokio's broadcast contract](https://docs.rs/tokio/latest/tokio/sync/broadcast/index.html#lagging).

## See Also

- [async-mpsc-queue](async-mpsc-queue.md) - bounded work distribution
- [async-watch-latest](async-watch-latest.md) - latest-state delivery
- [async-cancel-safety](async-cancel-safety.md) - retained receive state
