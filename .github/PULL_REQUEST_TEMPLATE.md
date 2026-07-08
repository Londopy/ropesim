# Pull request

## What this changes

<!-- One or two sentences. Link the issue if there is one. -->

## Tests added

<!-- Which tests cover this change? "None" needs a justification. -->

## Physics model impact

- [ ] This PR changes physics behaviour (model, constants, formulas)
  - If checked: cite the source (paper / standard / published test data) and
    tag a maintainer for **domain review**:

## Public API impact

- [ ] This PR changes the public Python API, C FFI, or file formats
  - If checked: docs updated (docstrings + docs-site), CHANGELOG entry added

## Checklist

- [ ] `pytest` passes locally
- [ ] `cargo test` passes (if Rust touched)
- [ ] `ctest` passes (if C++ touched)
- [ ] `ruff` / `cargo clippy` / `clang-format` clean
- [ ] CHANGELOG.md updated under *Unreleased*
