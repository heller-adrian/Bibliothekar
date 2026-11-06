# Contributing to Bibliothekar

Thank you for your interest in improving Bibliothekar. The project is a self-hosted camera-file management tool; protecting original media and the integrity of stored data takes priority over convenience.

## Before proposing a change

- Read the [README](README.md), the [documentation index](docs/README.md) and the [release policy](docs/RELEASING.md).
- Open a focused issue for non-sensitive bugs or feature proposals before significant redesigns. For security vulnerabilities, follow the [private security policy](.github/SECURITY.md) instead.
- Never publish real photos, customer data, database exports, secrets, private network details or unredacted logs as test material.
- Prefer a small, understandable pull request with a clear description of the problem, changes and how they were verified.

## Development and testing

The application is written in Python and deployed as a Docker container. Typical local development requires Python 3.12 and external utilities such as ExifTool. Consult the current dependency files and container configuration before setting up an environment.

The backend regression suite resides in `tests/backend/`. To run it in an **isolated disposable test environment**:

```sh
python -m pip install -r requirements.txt -c requirements-rc.constraints.txt pytest httpx tinycss2
python -m pytest -q -o addopts='' tests/backend
```

Do **not** run integration, archive or recovery tests against production datasets or production TrueNAS mounts. Tests that require containers, privileged helpers, removable devices or specific historical images need their own isolated setup. A passing backend run alone is not a complete storage/recovery release qualification.

## Pull-request checklist

- Keep the change focused; avoid unrelated application version bumps or image publishing.
- Document any migration, SQLite schema or filesystem behavior change, including recovery and rollback considerations.
- Use synthetic fixtures, and explain which tests ran and which were not run.
- Do not weaken existing data-loss prevention, read-only archive boundaries or authorization checks to make a test pass.
- Do not upload sensitive GitHub Actions artifacts or private infrastructure paths.
- Respect [AGPL-3.0](LICENSE) and ensure contributed code and assets can be redistributed under compatible terms.

## AI-assisted development

Bibliothekar has been developed with extensive AI assistance. AI-generated suggestions and code contributions are welcome, but the contributor must review and understand their changes and must not claim unperformed testing or independent verification.

## Releases

Only maintainers publish GHCR images and immutable release tags. Contributors should not trigger or modify stable publication workflows. The published `v1.0.0` release remains immutable.
