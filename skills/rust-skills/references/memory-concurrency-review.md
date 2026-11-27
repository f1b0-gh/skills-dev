# Memory bounds and concurrent resource lifetimes

Use this reference when reviewing retention, overload, shutdown, blocked workers,
or concurrency correctness. Keep the review scoped to the requested code; a
finding in one adapter does not justify replacing the application's runtime.

## Establish ownership and the claimed bound

For each relevant resource, identify its owner, admission point, release event,
and what happens if the caller times out, drops its future, or panics. Follow
ownership into spawned tasks, blocking closures, channels, and child processes.
`Arc`, RAII, `Send`/`Sync`, and safe Rust do not by themselves bound retention or
prove termination. State separately what covers application code, generated
code, and dependencies.

| Mechanism | What it establishes | What still needs checking |
|-----------|---------------------|---------------------------|
| Result timeout | A waiting deadline, subject to cooperative polling for futures | Whether the underlying operation stops and releases resources |
| Bounded channel | A maximum number of queued items | Item capacities, waiting producers, processing and retained results |
| Semaphore | Admission while its permit remains owned | Whether timeout releases the permit before the work actually ends |
| Async mutex | Serialized access, including intentional async operations | Transaction boundaries, cancellation and contention |
| Buffer accounting | The stated allocation scope | Stacks, allocator overhead, caches and whole-process RSS |

## Blocking work and process pipes

Dropping a `std::thread::JoinHandle` detaches the thread. A receive timeout does
not interrupt its `read_to_end` or `write_all`; adding an unconditional `join`
can instead make shutdown hang. A started `spawn_blocking` closure also survives
aborting or dropping its handle. Cancellation tokens require the operation to
cooperate; they cannot interrupt an arbitrary blocking syscall.

For subprocess IPC, track stdin, stdout, process status, helper threads and
descendants separately. A descendant can keep a pipe open after the direct
child exits. Use an appropriate interruptible transport, such as nonblocking
pipes with readiness waits, or an explicitly cancellable platform API. Apply
one absolute deadline to partial reads, writes and exit observation; cap output
before accumulating it. Drive both directions when either side can fill its pipe.
Keep termination/reaping ownership explicit and preserve the API's error
precedence. Closing local pipes is not proof that every descendant terminated.

For blocking pools, acquire capacity before submission and move the permit into
the closure. If work cannot be interrupted, report that it remains active after
the caller's timeout. A dedicated bounded owner can also be appropriate for
synchronous storage behind an async trait.

## Aggregate memory and lock scope

Account for queued payload capacities, waiting producers, active operations,
copies and serialization buffers, retained results, and worker stacks. A queue
of eight items is not a total memory bound when arbitrary producer tasks each
allocate a large payload before awaiting admission. Reserve before allocation
where possible; choose rejection or bounded waiting, and keep byte permits
through the lifetime covered by the budget. `Vec::capacity()` can exceed `len()`;
preallocating the maximum for every small response has a concurrency cost.

A synchronous lock should not span an await. A Tokio mutex may intentionally
span asynchronous database or protocol operations. Before shortening its scope,
identify the invariant it protects: revision checks, durable commit and local
publication may need to remain one serialized operation. Moving I/O outside
requires a protocol such as version revalidation/CAS or a serialized owner,
including reconciliation of cancellation after commit. Contention alone is not
evidence of a deadlock or permission to remove serialization.

## Admission before decoding and independently driven cleanup

At HTTP entry points, admission must precede body polling and decoding to cover
those allocations. Reserve the maximum admitted body cost, or charge incremental
buffers before growing them. Validate the relation between per-message limits,
aggregate bytes and operation counts; document transport/header allocations
outside that budget. Release an abandoned request's reservation when the covered
buffers/work are released; surviving work must retain its own admission.

A structural check after constructing a JSON `Value` does not bound rejected
input allocations. Use seeded visitors to enforce depth and node limits before
constructing children. Check duplicate keys before their values. Escaped strings
can grow decoder scratch before a visitor runs: bound that stage too, while
leaving JSON grammar, Unicode and number interpretation to the established
parser. Test exact boundaries and any narrowly scoped protocol exception.

Expiry checked only on the next stream poll does not reclaim an abandoned
queue. Keep server-owned payloads in a registry that maintenance can remove
independently, or use an equivalent ownership design. A maintenance task should
not keep its owner alive across idle waits. Preserve the delivery/acknowledgment
contract when moving ownership; freeing a queue is not proof of delivery.

For native callbacks, follow ownership into the foreign runtime's queue and
promise settlement/GC callbacks. Cancellation of a Rust receiver does not imply
that JavaScript stopped. Bound the queue and active callbacks separately and
inspect enqueue-error and environment-shutdown paths in the pinned binding.
Failure to attach a settlement handler does not prove the foreign work stopped;
for example, a Promise species/constructor hook can throw while it is pending.
Keep uncertain work admitted or close admission before reporting that failure.
A semaphore at the start of an async function runs only when that future is
polled; an FFI binding may already have queued the task and copied its arguments.
Where queue admission is intended, acquire it in the synchronous entry point
before scheduling the future, and reject overload without scheduling more work.
Attach admission to the actual retaining owner, including completed unread
replies. Prefer bounded ownership over spawning unbounded detached supervisors.

When growing secret buffers, a zeroizing final owner does not erase an old
allocation freed by ordinary reallocation. Use bounded replacement buffers and
explicitly zeroize the old owner; account for the temporary old/new overlap.
For process cleanup, release admission only after confirmed exit/reaping. If
cleanup ownership fails, retaining or retiring capacity can preserve the bound,
but it reduces availability and must be reported as a degraded outcome.

## Verify observable behavior

- For a timeout fix, reproduce stalled input, retained output pipes, EOF before
  process exit, and output overflow where relevant. Check that deadlines do not
  fire early, not only that calls return quickly.
- Check actual thread/task/descriptor recovery and capacity reuse after return.
  Isolate process-wide counts from unrelated tests; a timed-out result alone
  does not prove cleanup.
- Verify both directions of a full-duplex exchange, including exact received
  input and output. Use handshakes or barriers to reach race conditions reliably.
- When tests control processes, use private, exclusively created temporary
  directories and owned handles; do not trust a PID file in a shared path.
- Preserve transactional behavior under competing writers, errors and
  cancellation. Use Loom for supported synchronization models; it does not
  replace OS process/I/O tests or memory measurements.

Report confirmed defects separately from unmeasured performance limits. Include
the reproducer, affected scope, checks actually run, skipped qualifications and
remaining uncertainty. A focused harness can exercise the real module quickly;
label it and still validate integration with the affected crate.

For a broad audit, use the [evidence and coverage checklist](memory-audit-evidence.md).
It adds decoded-versus-encoded budgets, returned results, FFI queues, and the
limits of allocation counters and Cargo test summaries.

## Related rules and primary sources

- [Blocking work](../rules/async-spawn-blocking.md),
  [channel bounds](../rules/async-bounded-channel.md),
  [cancellation](../rules/async-cancellation-token.md),
  [lock scope](../rules/async-no-lock-await.md).
- Rust standard library: [thread JoinHandle](https://doc.rust-lang.org/std/thread/struct.JoinHandle.html).
- Tokio: [spawn_blocking](https://docs.rs/tokio/latest/tokio/task/fn.spawn_blocking.html),
  [Mutex](https://docs.rs/tokio/latest/tokio/sync/struct.Mutex.html),
  [CancellationToken](https://docs.rs/tokio-util/latest/tokio_util/sync/struct.CancellationToken.html).
