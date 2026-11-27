# mem-thinvec

> Evaluate ThinVec for many small collection headers without changing absence semantics

## Why It Matters

`ThinVec` moves length and capacity metadata into the allocation and has a smaller
inline header than `Vec` on typical targets. This can help when a structure has
many collection fields, but adds indirection and changes allocation behavior.
Measure total memory and access cost on the pinned crate and target, rather than
assuming a smaller header makes every workload faster.

## Preserve the contract

```rust
use thin_vec::ThinVec;

struct Document {
    // None: not supplied; Some(empty): explicitly supplied with no tags.
    tags: Option<ThinVec<String>>,
}
```

Replacing `Option<Vec<T>>` with plain `ThinVec<T>` merges absent and empty states.
Retain `Option` whenever the distinction matters, including serialization and
validation. Empty collections and nullability are different concepts.

## Check representation and cost

```rust
use std::mem::size_of;
use thin_vec::ThinVec;

fn report_headers() {
    println!("Vec: {}, Option<Vec>: {}", size_of::<Vec<u8>>(), size_of::<Option<Vec<u8>>>());
    println!("ThinVec: {}, Option<ThinVec>: {}", size_of::<ThinVec<u8>>(), size_of::<Option<ThinVec<u8>>>());
}
```

`Vec` has a non-null pointer and can benefit from a niche in `Option`; do not claim
that nullable Vec necessarily needs another word. Concrete byte counts and a
third-party type's layout depend on the target, version and features. Header sizes
exclude heap storage, allocator overhead and spare capacity.

Use the [thin-vec API](https://docs.rs/thin-vec/latest/thin_vec/) for the pinned
version. Check mutation, conversion and serialization costs before changing a
public type. A measurement is not authorization to add a dependency.

## See Also

- [mem-smallvec](mem-smallvec.md) - inline small collections
- [mem-boxed-slice](mem-boxed-slice.md) - fixed-length owned storage
- [mem-with-capacity](mem-with-capacity.md) - capacity and admission
