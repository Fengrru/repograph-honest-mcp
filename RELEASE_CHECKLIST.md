# Release checklist

Use this checklist when publishing a new version of RepoGraph-Honest.

## Pre-release

- [ ] All tests pass locally: `pytest`
- [ ] Lint passes: `ruff check repograph_honest tests scripts examples`
- [ ] Format check passes: `ruff format --check repograph_honest tests scripts examples`
- [ ] Pre-commit passes: `pre-commit run --all-files`
- [ ] Wheel builds cleanly: `python -m build --wheel`
- [ ] `pyproject.toml` version is bumped (single source of truth).
- [ ] `CHANGELOG.md` has an `[Unreleased]` section with the new entries.
- [ ] CI is green on `main` (lint + 4-OS matrix + coverage ≥ 80% + build).

## Release (automated)

The [Publish workflow](.github/workflows/publish.yml) automates everything after
the pre-release checks. Run it via **Actions → Publish to PyPI → Run workflow**
(optionally pass a version to override `pyproject.toml`).

The workflow will:

1. Resolve the version from `pyproject.toml` (or the manual input).
2. Promote `[Unreleased]` → `[<version>] - <date>` in `CHANGELOG.md` and commit
   it (idempotent — skips if the version block already exists).
3. Build `sdist` + `wheel`, run `twine check`.
4. Generate `SHA256SUMS` and attach Artifact Attestations.
5. Create (or update) the GitHub Release `v<version>` with the CHANGELOG notes.
6. Publish to PyPI via **OIDC trusted publishing** (no token needed).
7. Verify the version is visible on PyPI.

Manual fallback (if the workflow cannot be used):

```bash
python -m build
twine check dist/*
twine upload dist/*
```

## Post-release

- [ ] Verify `pip install repograph-honest-mcp` works in a fresh environment.
- [ ] Verify the installed CLI works: `repograph-honest-mcp --help`.
- [ ] Announce the release in relevant channels.
