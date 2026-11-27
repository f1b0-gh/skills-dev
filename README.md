# skills-dev

Reusable development skills for Rust and ClickHouse, with focused references,
explicit evidence requirements and checks for the examples corrected here.

| Skill | Purpose |
|---|---|
| [rust-discipline](skills/rust-discipline/SKILL.md) | Strict production defaults: safe Rust, typed failures, bounded ownership, focused validation |
| [rust-skills](skills/rust-skills/SKILL.md) | Selective access to 265 Rust rules and memory/concurrency review guidance |
| [clickhouse-sql](skills/clickhouse-sql/SKILL.md) | Query correctness, physical access, workload measurement and scoped optimization |

Use **rust-discipline** as the policy entry point for our Rust projects, with
**rust-skills** as its reference library. Imported examples never override a
consumer's explicit constraints. ClickHouse guidance scales from a short SQL
explanation to a measured optimization review.

## Use the skills

Clone the repository:

```sh
git clone https://github.com/f1b0-gh/skills-dev.git
```

Each directory under `skills/` is a skill package. Install whole directories,
including references and license files, using your agent's skill installer or
supported local skill directory. Install the two Rust skills together for full
reference access; `rust-discipline` still states its core contract without the
companion. ClickHouse is independent. Keep an existing installation until you
have compared it with the version you intend to install.

An agent with repository access can also read the entry points directly. For
example, adapt these paths to the consuming project's checkout:

```text
For Rust implementation and review, read ../skills-dev/skills/rust-discipline/SKILL.md,
then the relevant references in ../skills-dev/skills/rust-skills/.
For ClickHouse SQL, read ../skills-dev/skills/clickhouse-sql/SKILL.md.
Project-specific commands, targets and contracts remain in this project's instructions.
```

Example requests:

- “Use rust-discipline to review this parser's errors and cancellation behavior.”
- “Use rust-skills to inspect whether this queue really bounds retained memory.”
- “Use clickhouse-sql to check this rewrite before accepting its benchmark claim.”

Pin a commit for reproducible use. Update deliberately after reviewing changes;
this repository does not modify consuming repositories or installed skills.

## Validate changes

Structural checks require Python 3.11 or later:

```sh
python3 scripts/validate.py
```

They check required metadata, local file links, declared import changes and the
265-rule index. They do not validate remote links, Markdown anchors, SQL execution
or every technical statement.

The executable checks use Python, Rust and Cargo. The runtime dependencies are
pinned in `tests/runtime/Cargo.toml` and its lockfile. To run the full selected
suite, provision the toolchains first:

```sh
rustup toolchain install 1.99.1 --profile minimal
rustup toolchain install nightly-2026-10-29 --profile minimal
RUSTUP_TOOLCHAIN=1.99.1 cargo fetch --locked --manifest-path tests/runtime/Cargo.toml
RUSTUP_TOOLCHAIN=1.99.1 SKILLS_DEV_NIGHTLY=nightly-2026-10-29 SKILLS_DEV_RUNTIME=1 \
  python3 -m unittest discover -s tests -v
```

The tests extract actual Markdown examples. They cover raw-pointer API contracts,
division overflow, matrix dimensions, lock/commit ordering, macro export, SIMD
slice alignment/tails, arena reuse, stream termination, broadcast recovery and
watch notification races.
Repository-check tests exercise malformed packaging and references. Optional
nightly/runtime tests report skips if their environment flags are absent.
Test scratch is owned under `/tmp/skills-dev/`; no source project build is needed.

This is focused evidence, not an exhaustive qualification of all 265 rules, every
snippet, toolchain, target or dependency. Some imported examples are illustrative
fragments. Historical Antalya findings are diagnostic leads; their original
runtime evidence is not bundled and no ClickHouse service is required by this
repository's checks.

## Maintain the collection

Keep each entry point concise and route to detailed references only when useful.
Preserve user scope, project policy and dependency constraints. Correct concrete
failures rather than adding universal rules for every anecdote. For behavioral
changes to guidance, exercise realistic tasks; passing a metadata check does not
prove that an agent will make the right decision.

Record imported changes in [provenance/imports.json](provenance/imports.json).
Keep source hashes immutable and update the `modified`/`omitted` inventory when
intentionally changing that import. The original upstream manifest is separate.
See [PROVENANCE.md](PROVENANCE.md) and [NOTICE](NOTICE) for attribution and licensing.
