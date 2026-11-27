# own-rwlock-readers

> Choose `RwLock<T>` when measured concurrent reads justify its overhead and writer latency

## Why It Matters

`Mutex<T>` grants one guard at a time; `RwLock<T>` permits multiple readers or one exclusive writer. Concurrent reads can improve throughput when protected work is substantial, but reader bookkeeping and cache contention can outweigh that benefit. Read/write ratios alone do not determine the better choice; measure throughput and writer latency on the intended workload and hardware.

## Bad

The mistake is choosing from the read ratio alone, not using a mutex for reads:

```rust
use std::sync::{Arc, Mutex};

// Configuration rarely changes but is read constantly
let config = Arc::new(Mutex::new(Config::load()));

// Assuming this is slower without measuring contention is the mistake.
fn get_setting(config: &Mutex<Config>, key: &str) -> String {
    let guard = config.lock().unwrap();
    guard.get(key).to_string()
}

// Guards serialize access, but that can be cheap for brief/uncontended reads.
```

## Good

Use this pattern if measurements justify concurrent readers:

```rust
use std::sync::{Arc, RwLock};

// Multiple readers can proceed concurrently
let config = Arc::new(RwLock::new(Config::load()));

fn get_setting(config: &RwLock<Config>, key: &str) -> String {
    let guard = config.read().unwrap(); // Multiple threads can hold read lock
    guard.get(key).to_string()
}

fn update_setting(config: &RwLock<Config>, key: &str, value: &str) {
    let mut guard = config.write().unwrap(); // Exclusive access for writes
    guard.set(key, value);
}

// Multiple reader guards are allowed; scheduling and hardware limit parallelism.
```

## parking_lot::RwLock

Evaluate `parking_lot::RwLock` if its API or measured performance fits the
application. It does not poison on panic, so changing lock implementations can
change the recovery contract as well as performance:

```rust
use parking_lot::RwLock;
use std::sync::Arc;

let data = Arc::new(RwLock::new(HashMap::new()));

// Read - no unwrap needed
let value = data.read().get("key").cloned();

// Write
data.write().insert("key".to_string(), "value".to_string());

// parking_lot supports an upgradeable read guard.
let upgradeable = data.upgradable_read();
if upgradeable.get("key").is_none() {
    let mut write = parking_lot::RwLockUpgradableReadGuard::upgrade(upgradeable);
    write.insert("key".to_string(), "default".to_string());
}
```

## When RwLock Hurts

There is no universal write-percentage cutoff. Compare implementations using
realistic thread counts, critical-section work and read/write bursts. Measure
throughput, lock wait/hold times, and writer p95/p99 latency, including under load.

| Scenario | What to compare |
|----------|---------------|
| Frequent writes or brief reads | `Mutex` may avoid reader-tracking overhead |
| Substantial concurrent reads | `RwLock` may permit useful overlap |
| Writer latency matters | Measure waiting writers under sustained reader load |
| Single-threaded ownership | Direct borrowing; `RefCell` if runtime borrowing is needed |

## Write Starvation

The standard library's [RwLock](https://doc.rust-lang.org/std/sync/struct.RwLock.html)
does not guarantee a priority policy; it depends on the OS implementation.
Check the exact version of alternative implementations too:

- [parking_lot 0.12.5](https://docs.rs/parking_lot/0.12.5/parking_lot/type.RwLock.html)
  documents eventual fairness rather than strict FIFO on every acquisition.
- [parking_lot 0.13.0](https://docs.rs/parking_lot/0.13.0/parking_lot/type.RwLock.html)
  documents unfair unlocking by default, with explicit `unlock_fair` available.

Neither a fairness policy nor a write-to-read downgrade supplies a wall-clock
latency bound. Downgrading changes guard access, not the lock's fairness policy.
Avoid recursively acquiring read guards or trying to acquire a write guard
while retaining an ordinary read guard: queued writers can make these deadlock.

## Real-World Pattern: Cached Computation

This policy permits duplicate computation on concurrent misses. Recheck under
the write guard and return the published winner. Use it only when computation
can safely run more than once; initialization with side effects needs a different
protocol. A cache with invalidation also needs generation/version validation.

```rust
use parking_lot::RwLock;
use std::sync::Arc;

struct CachedData {
    cache: RwLock<Option<ExpensiveResult>>,
}

impl CachedData {
    fn get(&self) -> ExpensiveResult {
        // Fast path: read lock
        if let Some(cached) = self.cache.read().as_ref() {
            return cached.clone();
        }

        // Slow path: compute and cache
        let result = compute_expensive();
        let mut cache = self.cache.write();
        cache.get_or_insert(result).clone()
    }
}
```

## See Also

- [own-mutex-interior](./own-mutex-interior.md) - When writes are frequent
- [async-no-lock-await](./async-no-lock-await.md) - RwLock in async contexts
