# Historical GitHub Actions workflows

This repository reached its first stable release as [v1.0.0](https://github.com/heller-adrian/Bibliothekar/tree/v1.0.0) on 2026-11-05.

The original **54 workflow YAML files** are preserved in that immutable release source tree under [`.github/workflows` at v1.0.0](https://github.com/heller-adrian/Bibliothekar/tree/v1.0.0/.github/workflows).

In the post-1.0 maintenance branch, the default-branch workflow directory is reduced to five entry points. No historical YAML source is rewritten, and no test implementation under `qa/` or `tests/` is removed by this change.

## Workflows still present in the current development tree

| Workflow | Purpose |
| --- | --- |
| `qa-tests.yml` | Ordinary pull-request and main-branch backend regression, using GitHub-hosted runners for untrusted pull requests |
| `qa-100-stabilization.yml` | Historical exact-source 1.0.0 full qualification retained temporarily as a release-test reference; requires migration to a reusable release workflow |
| `publish-container.yml` | Controlled stable publishing by explicit dispatch on `main`, or reusable patch publishing |
| `publish-patch-request.yml` | Explicit patch-image publication request from `patch/**` |
| `audit-public-history.yml` | Read-only source-history inventory before making the repository public |

## What moved out of the active workflow directory

Historical `qa-pre*`, `qa-rc*`, `qa-f*`, security-wave, one-off patch QA and `publish-rc*` / `publish-pre` registrations are still accessible at the v1.0.0 tag. These files were release-candidate-specific execution entry points, **not** the underlying regression tests. Their source and the original source-tree paths remain inspectable with:

```sh
git show v1.0.0:.github/workflows/qa-pre5-operation-recovery.yml
git show v1.0.0:.github/workflows/publish-rc14.yml
git ls-tree -r --name-only v1.0.0 .github/workflows
```

Keep `qa/` and `tests/` unchanged until an independent code-level dependency check justifies any move. In particular, the final qualification runner still invokes `qa/rc13/regression.py`.

## Safety and migration notes

- A workflow removed from the default branch may still exist and execute on an old development branch; cleaning branches and open pull requests is a **separate** reviewed step.
- Past Actions runs and artifacts are separate GitHub records and are not deleted by this cleanup.
- The v1.0.0 release tag, corresponding Git history and published container image must not be rewritten.
- The retained 1.0.0 qualification and stable publisher contain **release-specific commit and run checks**. A later stable version needs a new, reviewed release gate, not just a version-number edit.
- Publication of the repository itself must wait for review of reachable history, Actions logs, artifacts, PR comments and private metadata.
- The cleanup branch has not been merged to `main` by this action.
