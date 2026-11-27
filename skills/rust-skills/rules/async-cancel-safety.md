# async-cancel-safety

> Preserve partial progress and task ownership across select cancellation

## Why It Matters

`tokio::select!` drops losing branch futures. Whether restarting is safe depends
on which state remains outside those futures, whether data was consumed, and
whether cancellation loses queue position. A buffer outside `read_exact` is not
enough: its progress offset must survive too.

## Good

This stream is authoritative: clean EOF ends the operation; a partial final
frame is an error. Channel closure disables that branch while reading continues.

```rust
use tokio::io::{AsyncRead, AsyncReadExt};
use tokio::sync::mpsc;

async fn good_example<R: AsyncRead + Unpin>(
    stream: &mut R,
    rx: &mut mpsc::Receiver<u8>,
) -> std::io::Result<usize> {
    let mut buf = [0u8; 1024];
    let mut filled = 0;
    let mut frames = 0;
    let mut messages_open = true;
    loop {
        tokio::select! {
            n = stream.read(&mut buf[filled..]) => {
                let n = n?;
                if n == 0 {
                    return if filled == 0 { Ok(frames) } else {
                        Err(std::io::Error::new(std::io::ErrorKind::UnexpectedEof, "partial frame"))
                    };
                }
                filled += n;
                if filled == buf.len() {
                    // Consume this complete frame before reusing the buffer.
                    frames += 1;
                    filled = 0;
                }
            }
            msg = rx.recv(), if messages_open => {
                match msg {
                    Some(value) => { let _ = value; /* Handle the control message. */ }
                    None => messages_open = false,
                }
            }
        }
    }
}
```

## Cancellation contracts

| Operation in a repeatedly restarted select | What survives cancellation |
|---|---|
| `mpsc::Receiver::recv`, `broadcast::Receiver::recv` | No message consumed by the losing call |
| `watch::Receiver::changed` | No update marked seen by the losing call |
| `&mut oneshot::Receiver` retained outside select | Receiver stays open; dropping the owned receiver closes it |
| `&mut JoinHandle` retained outside select | Task and result owner remain; dropping the owned handle detaches the task |
| `AsyncReadExt::read` | Losing call reads no bytes; successful partial reads must update an external offset |
| `read_exact`, `read_to_end` | Not generally restart-safe; partial progress or buffer changes need explicit handling |
| `Mutex::lock`, semaphore acquisition | Cancellation loses queue position; repeated restarts can starve a waiter |
| Recreated `sleep(duration)` | Restarts the wait; retain a deadline or pinned timer for an overall timeout |

For non-restartable operations, retain and pin the same future across unrelated
select branches. Spawning an operation is not a free cancellation fix: retain its
handle, bound admission, and define shutdown and result ownership. A started
blocking closure needs its own lifetime or interruption mechanism.

Check the actual primitive's [Tokio cancellation contract](https://docs.rs/tokio/latest/tokio/macro.select.html#cancellation-safety).
Test EOF, partial frames, closed channels and repeated interruption, not just the
happy path. Cancellation safety is distinct from fairness and graceful cleanup.

## See Also

- [async-select-racing](async-select-racing.md) - deadlines and select policy
- [async-bounded-channel](async-bounded-channel.md) - admission and waiting producers
- [async-spawn-blocking](async-spawn-blocking.md) - surviving blocking work
