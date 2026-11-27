# Provenance and licensing

The repository's additions and extracted project guidance are licensed under
Apache-2.0. Imported Rust reference material retains its original MIT license and
copyright notice. Distribution must preserve both applicable notices.

## Rust reference

The reference originates in [leonardomso/rust-skills](https://github.com/leonardomso/rust-skills),
at revision `fd2a861ab0406a4ac536a55274d14ea6fd1ca9c9`. It was maintained in LO before
this extraction; the portable copy in rsigma-antalya matched that source subset.

- [LICENSE](skills/rust-skills/LICENSE) retains the original MIT notice.
- [LICENSE-APACHE](skills/rust-skills/LICENSE-APACHE) covers local contributions.
- [UPSTREAM.json](skills/rust-skills/UPSTREAM.json) records original upstream hashes,
  including files omitted from this portable package. It is historical import
  metadata, not a checksum manifest of the current edited tree.
- [imports.json](provenance/imports.json) records the local source snapshot hashes
  before this extraction's edits, with explicit modified and omitted paths.
  Trailing-whitespace normalization is listed separately; it is not a claim of
  substantive review of every affected file.

The extraction moves the full index into a reference, removes unconditional
release-profile defaults from the entry point, and corrects reviewed examples
involving unsafe preconditions, overflow, SIMD indexing, resource lifetimes,
async termination, traits and manifest syntax. It also corrects several numerical
and representation claims. Original rule IDs remain stable. A changed file does
not imply that every statement or example in that file has been runtime-tested.

## Rust discipline

This skill extracts reusable LO rules. Domain-specific invariants, LO package
names and LO validation scripts remain project concerns. The shared skill supplies
strict defaults and chooses checks according to the consuming project's actual
change. Resource guidance refers to the shared Rust references instead of a
second project-specific campaign guide.

## ClickHouse SQL

This skill came from a locally installed package developed alongside Antalya
work; it was not taken from a versioned `rsigma-antalya/skills/clickhouse-sql` path.
Its source hashes are recorded in the import manifest. Publication clarifies
ordinary SQL scope, exact-result requirements and historical observation limits.

The Antalya version strings and regression SQL are retained where informative.
Original image digests and measurement captures are not part of this package.
Unreproducible optimizer anecdotes are expressed as candidate experiments rather
than universal behavior. Links to current upstream code explain mechanisms;
they do not establish the identity of a historical downstream binary.
