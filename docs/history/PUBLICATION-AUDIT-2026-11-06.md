# Branch and historical privacy review — 2026-11-06

**Status:** Repository publication NOT approved. Read-only branch classification and preliminary private-path review. The published `v1.0.0` tag and GHCR image are not changed.

## Branch snapshot

The snapshot was taken while the default branch was `main` at **`3f9c4a52d0c2063403cf425164a45d5ba6ef5cc7`**, **before** creating this audit branch. Inventory: **236 branches** (including `main`), with exact tip SHA and classification in [branch-inventory-2026-11-06.csv](branch-inventory-2026-11-06.csv).

All **3,644 commits reachable from `main`** were enumerated via GitHub's paginated commit history and checked against every branch tip SHA:

| Class | Count | Treatment |
| --- | ---: | --- |
| `CANDIDATE_ANCESTRY_ONLY` | 183 | Tip is in `main`; no known open-PR base/head or protected release evidence reference. Review before deleting |
| `KEEP_DEFAULT` | 1 | `main` |
| `KEEP_OPEN_PR_HEAD` | 2 | PR #28 and PR #31 |
| `KEEP_OPEN_PR_BASE` | 2 | `patch/0.54.4` and `release/1.0.0-public-preparation` |
| `KEEP_QUALIFICATION_EVIDENCE` | 1 | Exact v1.0.0 release QA branch, run 42002573062 |
| `KEEP_RELEASE_TAG_ALIAS` | 1 | Branch tip also points to `v1.0.0` |
| `REVIEW_SQUASH_MERGED` | 5 | Post-release maintenance PRs #32–#36; branch tips were not retained as ancestors after squash |
| `KEEP_TAG_REACHABLE_DIVERGED` | 1 | `patch/0.34.0` is not in `main`, but a `v0.34.0` tag points to the same SHA |
| `REVIEW_NOT_IN_MAIN` | 40 | Distinct branch tip not an ancestor of `main`; no automatic deletion |

**Key distinctions:** "tip reachable from `main`" proves Git commit reachability, **not** equivalence of all external Actions history, artifacts, references, secrets, or live deployments. A squash-merged PR may already have its changes incorporated without its tip becoming an ancestor. A non-ancestor branch may still be preserved by a tag or contain valuable development history.

**No branch or tag has been deleted.** The available GitHub connection does not provide branch-deletion operations. The CSV is a review snapshot, not an executable deletion list. Before any deletion, fetch fresh refs, check branch protection and open PRs, and preserve release and qualification provenance. Do not delete an open PR's base or head.

## Historic Git object scan already performed

Existing [read-only scanner](../../tools/public_release_audit.py) ran as GitHub Actions [41738548229](https://github.com/heller-adrian/Bibliothekar/actions/runs/41738548229) on **2026-11-03**. Its private artifact reported:

- **8,609 unique text blobs examined.**
- **100 blobs** matched the `explicit-private-path` rule.
- **Zero matches** for the scanner's five high-confidence credential pattern families (private-key PEM, GitHub tokens, AWS keys, OpenAI keys, Google API keys).
- No local-network address or email-address matches reported by that run.
- The report explicitly requires manual review of infrastructure metadata and does not cover all GitHub-hosted surfaces.

These are **pattern-scanner results, not proof that no secrets exist**. The old run predates later repository changes and may not cover all new refs. New scans, GitHub Action logs, artifacts, releases, attachments, pull-request comments and user/profile metadata remain unreviewed in full.

The historical path findings are associated primarily with older TrueNAS setup notes and QA scripts. Manual spot checks confirm that host-specific `/mnt/...` paths are present in the **unchanged `v1.0.0` tag**, including `qa/archive_e2e/start_isolated_archive_qa.sh` and `qa/CLEAN_SLATE.md`. Raw host-specific values are intentionally **not reproduced** in this report.

**Consequences:** Moving or deleting such files in `main`, or pruning a branch, cannot remove them from an immutable `v1.0.0` tree. The owner must decide whether publishing those legacy paths is acceptable. If not, do not make this repository public without a separately approved history and release-preservation strategy; rewriting `v1.0.0` is explicitly out of scope.

## Additional publication blockers

1. Human review of the historic `/mnt/...` path findings, including whether any identify private locations, users, datasets or host names.
2. Independently check commit history since 2026-11-03 and all GitHub surfaces outside the scanner: Actions logs/artifacts, issue/PR bodies and comments, releases, packages, attachments, email addresses and secrets.
3. Verify licensing and redistribution rights for all non-code assets and dependencies.
4. Define a private security-contact fallback before public visibility. Enable and verify GitHub Private Vulnerability Reporting promptly after changing the repository to public, **before announcing**.
5. Configure suitable branch / publication protections. GitHub currently reports `main` as **unprotected**; verify capabilities and enforcement when public.
6. Resolve or retain the two historical draft PRs #28 and #31 intentionally before pruning their respective branch bases/heads.
7. Re-review the publication checklist immediately before changing visibility. Changing visibility is a separate deliberate action.

## Preservation statement

The application source `app/`, test code `tests/` and `qa/`, Dockerfile, released `v1.0.0` tag, release qualification and GHCR image are **not modified** by this audit. The repository remains private.
