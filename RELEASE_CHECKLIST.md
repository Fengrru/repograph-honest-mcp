# Release checklist

Use this checklist when publishing a new version of RepoGraph-Honest.

## Pre-release

- [ ] All tests pass: `pytest`
- [ ] Lint passes: `ruff check repograph_honest tests scripts examples`
- [ ] Format check passes: `ruff format --check repograph_honest tests scripts examples`
- [ ] Wheel builds cleanly: `python -m build --wheel`
- [ ] `CHANGELOG.md` is updated with the new version and release date.
- [ ] `pyproject.toml` version is bumped.

## Open source on GitHub

- [ ] Create a public repository at `https://github.com/Fengrru/repograph-honest-mcp`.
- [ ] Push the local project to the `main` branch:
  ```bash
  git init
  git add .
  git commit -m "Initial open-source release"
  git branch -M main
  git remote add origin https://github.com/Fengrru/repograph-honest-mcp.git
  git push -u origin main
  ```
- [ ] Verify CI passes on GitHub Actions.
- [ ] Add repository topics/keywords on GitHub (e.g. `mcp`, `llm`, `hallucination-detection`).
- [ ] (Optional) Enable GitHub Discussions for Q&A.

## PyPI release

- [ ] Install/upgrade build tools: `pip install --upgrade build twine`
- [ ] Build distribution artifacts:
  ```bash
  python -m build
  ```
- [ ] Check artifacts:
  ```bash
  twine check dist/*
  ```
- [ ] Upload to PyPI:
  ```bash
  twine upload dist/*
  ```
- [ ] Create a GitHub Release from the version tag and attach the CHANGELOG notes.

## Post-release

- [ ] Verify `pip install repograph-honest-mcp` works in a fresh environment.
- [ ] Verify the installed CLI works: `repograph-honest-mcp --help`.
- [ ] Announce the release in relevant channels.
