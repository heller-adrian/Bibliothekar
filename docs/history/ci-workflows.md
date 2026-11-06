# Historical GitHub Actions workflows

This repository reached its first stable release as [v1.0.0](https://github.com/heller-adrian/Bibliothekar/tree/v1.0.0) on 2026-11-05.

The original **54 workflow YAML files** are preserved in that immutable release source tree under [`.github/workflows` at v1.0.0](https://github.com/heller-adrian/Bibliothekar/tree/v1.0.0/.github/workflows).

After post-1.0 maintenance, the default-branch workflow directory has **four** current entry points. The one-off 1.0.0 qualification workflow was retired from the default branch when its self-hosted runner was decommissioned; it remains byte-identical in the immutable `v1.0.0` source tree. No test implementation under `qa/` or `tests/` is removed by this change.

## Workflows still present in the current development tree

| Workflow | Purpose |
| --- | --- |
| `qa-tests.yml` | Ordinary pull-request and main-branch backend regression, using GitHub-hosted runners for untrusted pull requests |
| `publish-container.yml` | Controlled stable publishing by explicit dispatch on `main`, or reusable patch publishing |
| `publish-patch-request.yml` | Explicit patch-image publication request from `patch/**` |
| `audit-public-history.yml` | Explicit-only source-history inventory on GitHub-hosted Ubuntu; upload finding paths only while the repository is private |

## What moved out of the active workflow directory

Historical `qa-pre*`, `qa-rc*`, `qa-f*`, security-wave, one-off patch QA and `publish-rc*` / `publish-pre` registrations are still accessible at the v1.0.0 tag. These files were release-candidate-specific execution entry points, **not** the underlying regression tests. Their source and the original source-tree paths remain inspectable with:

```sh
git show v1.0.0:.github/workflows/qa-pre5-operation-recovery.yml
git show v1.0.0:.github/workflows/publish-rc14.yml
git ls-tree -r --name-only v1.0.0 .github/workflows
```

Keep `qa/` and `tests/` unchanged until an independent code-level dependency check justifies any move. In particular, the historical 1.0.0 qualification used `qa/rc13/regression.py`; its original workflow is still available as `v1.0.0:.github/workflows/qa-100-stabilization.yml`.

## Safety and migration notes

- A workflow removed from the default branch may still exist and execute on an old development branch; cleaning branches and open pull requests is a **separate** reviewed step.
- Past Actions runs and artifacts are separate GitHub records and are not deleted by this cleanup.
- The v1.0.0 release tag, corresponding Git history and published container image must not be rewritten.
- The archived 1.0.0 qualification and current stable publisher contain **release-specific commit and run checks**. A later stable version needs a new, reviewed release gate, not just a version-number edit.
- Publication of the repository itself must wait for review of reachable history, Actions logs, artifacts, PR comments and private metadata.
- **Removing workflow YAML does not unregister an actual self-hosted runner.** Repository owners must remove the runner registration in GitHub Settings → Actions → Runners before making the repository public; older branches can contain historical workflows. The repository connector cannot perform runner deregistration.
