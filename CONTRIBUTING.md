# Contributing to RepoGraph-Honest

Thank you for your interest in making RepoGraph-Honest better! This document
outlines how to contribute code, report issues, and request features.

## Getting started

1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/<your-username>/repograph-honest-mcp.git
   cd repograph-honest-mcp
   ```
3. Create a virtual environment and install the package in editable mode:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # on Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

## Development workflow

1. Create a new branch for your change:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes, including tests when applicable.
3. Run the test suite and lint checks:
   ```bash
   pytest
   ruff check repograph_honest tests scripts
   ruff format --check repograph_honest tests scripts
   ```
4. Commit your changes with a clear, concise message.
5. Push to your fork and open a pull request against the `main` branch.

## Code style

- We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.
- Target Python version is 3.10+.
- Keep functions focused and add docstrings for public APIs.
- Prefer `pathlib.Path` over string paths.
- Avoid bare `except:`; catch specific exceptions or mark intentional broad
  catches with `# noqa: BLE001`.

## Writing tests

- Tests live in the `tests/` directory.
- Use `pytest` and the `tmp_path` fixture for filesystem fixtures.
- Aim to cover both happy paths and edge cases.
- If you fix a bug, add a regression test when possible.

## Reporting issues

When reporting a bug, please include:

- A clear description of the problem.
- Steps to reproduce.
- Expected vs. actual behavior.
- Your operating system and Python version.
- Relevant logs or error messages.

## Feature requests

Feature requests are welcome! Open an issue describing:

- The use case.
- The proposed API or behavior.
- Why it is useful for hallucination detection.

## Code of conduct

Be respectful, constructive, and inclusive. We want RepoGraph-Honest to be a
welcoming project for everyone.

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).
