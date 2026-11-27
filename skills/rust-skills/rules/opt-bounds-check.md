# opt-bounds-check

> Use iterators and patterns that eliminate bounds checks in hot paths

## Why It Matters

Rust's safety guarantees require bounds checking on array/slice indexing. In tight loops, these checks can cause measurable overhead (branch mispredictions, preventing vectorization). Patterns like iterators, `get_unchecked`, and index splitting can eliminate these checks while maintaining safety.

## Bad

```rust
fn sum_products(a: &[f64], b: &[f64]) -> f64 {
    let mut sum = 0.0;
    for i in 0..a.len() {
        sum += a[i] * b[i];  // Two bounds checks per iteration
    }
    sum
}

fn apply_filter(data: &mut [u8], kernel: &[u8; 3]) {
    for i in 1..data.len() - 1 {
        // Three bounds checks per iteration
        data[i] = (data[i - 1] + data[i] + data[i + 1]) / 3;
    }
}
```

## Good

```rust
fn sum_products(a: &[f64], b: &[f64]) -> f64 {
    assert_eq!(a.len(), b.len(), "dot product length mismatch");
    // zip truncates: establish the same-length contract before using it.
    a.iter().zip(b.iter()).map(|(x, y)| x * y).sum()
}

fn apply_filter(data: &mut [u8]) {
    // Windows pattern - no bounds checks
    for window in data.windows(3) {
        // window[0], window[1], window[2] are all valid
    }

    // Or use chunks
    for chunk in data.chunks_exact(4) {
        process_simd(chunk);
    }
}
```

## Iterator Patterns

```rust
// These give the compiler much better opportunities to eliminate bounds checks
// (and often do in practice), but elimination is not guaranteed — verify hot
// code with generated assembly (e.g. cargo-show-asm):

// zip - parallel iteration
for (a, b) in xs.iter().zip(ys.iter()) { ... }

// enumerate - index + value
for (i, x) in data.iter().enumerate() { ... }

// windows - sliding window
for window in data.windows(3) { ... }

// chunks - fixed-size groups
for chunk in data.chunks(4) { ... }
for chunk in data.chunks_exact(4) { ... }  // Guarantees exact size

// split_at - divide slice
let (left, right) = data.split_at(mid);
```

## Split for Parallel Access

```rust
fn parallel_sum(data: &[i32]) -> i32 {
    // Split into independent chunks
    let (left, right) = data.split_at(data.len() / 2);

    // Process chunks without bounds checks
    let sum_left: i32 = left.iter().sum();
    let sum_right: i32 = right.iter().sum();

    sum_left + sum_right
}
```

## Validate dimensions before indexing

Unchecked indexing requires a complete proof, including arithmetic overflow.
This safe implementation rejects invalid dimensions before touching the output.
A measured optimization must preserve these checks and the output contract.

```rust
fn matrix_multiply(a: &[f64], b: &[f64], c: &mut [f64], n: usize) -> Result<(), &'static str> {
    let cells = n.checked_mul(n).ok_or("matrix dimensions overflow")?;
    if a.len() < cells || b.len() < cells || c.len() < cells {
        return Err("matrix storage too short");
    }
    for i in 0..n {
        for j in 0..n {
            let mut sum = 0.0;
            for k in 0..n {
                sum += a[i * n + k] * b[k * n + j];
            }
            c[i * n + j] = sum;
        }
    }
    Ok(())
}
```

Use a domain error in an application API. If policy permits unchecked indexing,
prove all accessed ranges and arithmetic first; a safety comment is not a proof.

## Slice Patterns

```rust
fn process_header(data: &[u8]) -> Option<Header> {
    // Slice pattern - single length check, no per-field checks
    let [a, b, c, d, rest @ ..] = data else {
        return None;
    };

    Some(Header {
        magic: *a,
        version: *b,
        flags: u16::from_le_bytes([*c, *d]),
        payload: rest,
    })
}
```

## Verify Bounds Check Elimination

```bash
# Check generated assembly
cargo asm --release my_crate::hot_function

# Look for 'cmp' and 'ja'/'jbe' instructions near array access
# If eliminated, you'll see direct memory access
```

## When to Accept Bounds Checks

```rust
// Random access patterns - checks unavoidable
fn random_lookup(data: &[u8], indices: &[usize]) -> Vec<u8> {
    indices.iter()
        .filter_map(|&i| data.get(i).copied())  // Checked, but necessary
        .collect()
}

// Infrequent access - overhead negligible
fn get_config(&self, key: &str) -> Option<&Value> {
    self.config.get(key)  // Fine, not hot path
}
```

## See Also

- [opt-simd-portable](./opt-simd-portable.md) - SIMD and safe chunking
- [opt-cache-friendly](./opt-cache-friendly.md) - Cache-efficient patterns
- [perf-profile-first](./perf-profile-first.md) - Identify actual hot paths
