# Public source release checklist

**Status: preparation in progress – not a public-release approval.**
Stable **v1.0.0** was published on 2026-11-05. This checklist concerns **making the GitHub source repository public**, not rebuilding or retesting that already published version.

## Before making the repository public

- [ ] Review all files in the current default branch for access tokens, passwords, private keys, credentials, internal IP addresses, home directories and private NAS paths.
- [ ] Scan **all reachable Git history** across every retained branch and tag. Removing files in a new commit does not remove old reachable versions.
- [ ] Review old release assets, GitHub Actions logs, uploaded artifacts, issue and pull-request descriptions/comments, and any other attachments. The source-history scanner does not cover every GitHub surface.
- [ ] Rotate or revoke any credentials found, even if they appear only in an old commit.
- [ ] Review old branch and open pull-request retention. Only remove a branch after checking its contribution, current activity, open PRs and release/tag references.
- [ ] Check GitHub Actions workflows for fork/pull-request trust boundaries, self-hosted runners, token permissions, secrets and writable publishing paths.
- [ ] Verify that publication is intentionally gated and that documentation-only changes cannot publish or overwrite an existing stable image.
- [ ] Review the container package visibility in GHCR separately; public source access does not determine package visibility.
- [ ] Verify license text, dependencies/third-party licenses, third-party image/icon usage and a security-reporting contact.
- [ ] Review README and install instructions from a new user's perspective, including restrictions on privileged SD/USB mounting and the distinction between TrueNAS Custom Apps and the official Apps Catalog.
- [ ] Recheck the remaining repository contents, GitHub settings, and sensitive metadata after cleanup; explicitly approve the final public-visibility change.

## Current preservation rule

The existing `v1.0.0` release tag, published image digest and application code are not part of this housekeeping task. Historic candidate testing is already recorded; it should not be run again simply to reorganize documentation or CI entry points.

## Historical qualification documentation

The archived 0.50.0 gate report is [here](0500_RELEASE_GATE_REPORT.md). Its earlier **NO-GO** language and test counts concern *0.50.0*, not the published 1.0.0 release, and should not be read as a current release verdict.

The final 1.0.0 qualification is represented by its recorded release QA run and immutable `v1.0.0` source tag. The one-off full-qualification workflow is not yet a reusable future-version release gate. See [Releasing](RELEASING.md) and the [CI inventory](history/ci-workflows.md).

## Separate TrueNAS Catalog submission

Public repository visibility does **not** imply approval by the TrueNAS Apps Catalog. Device access, privileged helper operation, filesystem mounts and security review must be handled under a separate catalog-submission assessment.
