# Contributing to ropesim

Thanks for helping make ropesim better. Contributions of all kinds are
welcome — physics corrections, rope specs, code, docs, and bug reports.
You do **not** need to know Rust or Python to contribute rope data or
report a physics discrepancy: use the issue templates.

## Development environment

ropesim has three codebases sharing one Rust core:

| Part | Language | Toolchain |
|---|---|---|
| `ropesim/` | Python 3.10+ | pip, maturin |
| `ropesim/_rustcore/` | Rust (2021) | stable rustc/cargo |
| `gui-cpp/` | C++20 + Qt6 | CMake 3.25+, Qt 6.6+ |
| `docs-site/` | TypeScript | Node 20+ |

### Python + Rust core

```bash
git clone https://github.com/Londopy/ropesim.git
cd ropesim
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install maturin
maturin develop --release        # builds the Rust core, installs editable
pip install -e ".[dev]"
```

### C++ GUI

Install Qt 6.6+ (via the Qt online installer, `brew install qt`, or
`apt install qt6-base-dev qt6-base-dev-tools libgl1-mesa-dev`), then:

```bash
cargo build --release --manifest-path ropesim/_rustcore/Cargo.toml
# this also regenerates gui-cpp/include/ropesim.h via cbindgen
cd gui-cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
./build/ropesim-gui
```

### Docs site

```bash
cd docs-site
npm install
python scripts/generate-api-docs.py   # extract Python docstrings
npm run dev                           # http://localhost:3000/ropesim
```

## Running tests

```bash
python -m pytest tests/ -m "not benchmark"        # Python suite
cargo test --manifest-path ropesim/_rustcore/Cargo.toml   # Rust unit tests
cd gui-cpp/build && ctest                          # C++ bridge tests
```

Tests marked `requires_rust` skip automatically when the extension isn't
compiled, so a pure-Python checkout still has a green suite.

## Code style

- **Python** — `ruff check .` and `black .` (line length 100). Type hints on
  public APIs.
- **Rust** — `cargo fmt` and `cargo clippy -- -D warnings`. Physics functions
  get a doc comment citing the model source.
- **C++** — `clang-format` (LLVM style, 4-space indent). Qt naming for
  Qt-derived classes, `camelCase` methods.

## Adding a rope to the database

1. Find the manufacturer's published EN 892 / UIAA 101 spec sheet.
2. Add an entry to `ropesim/database/ropes.json` — copy an existing entry
   and change every field. Numbers must come from the spec sheet, not
   estimates.
3. Run `python -m pytest tests/unit/test_rope_database.py`.
4. Open a PR citing the spec-sheet URL, or just file a
   **Rope spec submission** issue and we'll do the rest.

## Submitting a new gear type

Open a feature request first — gear changes touch the Rust world model
(`world.rs`), the FFI (`ffi.rs`), both GUIs, and the docs. We'll help scope it.

## Pull request checklist

- [ ] Tests pass locally (`pytest`, `cargo test`, and `ctest` if you touched C++)
- [ ] New behaviour has tests
- [ ] Physics changes cite a source (paper, standard, or published test data)
      and are flagged for domain review
- [ ] Public API changes are documented (docstrings + docs-site page)
- [ ] `CHANGELOG.md` updated under *Unreleased*

## Issue labels

| Label | Meaning |
|---|---|
| `physics` | Model correctness — needs domain review |
| `rope-data` | Rope database additions/corrections |
| `gui` | C++ Qt6 application |
| `core` | Rust engine |
| `python-api` | Python bindings/API surface |
| `docs` | Documentation site |
| `good-first-issue` | Self-contained, mentoring available |

## Safety note

ropesim informs judgement; it never replaces it. PRs that frame simulation
output as a guarantee of real-world safety will be asked to reword.
