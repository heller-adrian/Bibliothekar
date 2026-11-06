# Bibliothekar documentation

This is the documentation entry point for the current development tree. The shipped application and immutable release **v1.0.0** are not modified by documentation housekeeping.

## Start here

- [Project overview, features and TrueNAS Custom App setup](../README.md)
- [Example TrueNAS Compose deployment](../compose.example.yaml)
- [Release and image publishing policy](RELEASING.md)
- [Checklist before making this private repository public](PUBLICATION_CHECKLIST.md)
- [QA infrastructure and test scope](../qa/README.md)
- [Stable version 1.0.0 release](https://github.com/heller-adrian/Bibliothekar/releases/tag/v1.0.0)

## Historical development material

The `pre*`, `rc*`, `practice/`, numbered reports (`0500_*` through `0531_*`) and `BA*` notes document earlier development, regression analysis and TrueNAS experiments. **They are not current installation instructions or independent certification of the stable release.**

Some historic qualification tools **still import or inspect these files by their original repository paths**, for example `qa/pre6/reuse_backend.py` importing `docs/pre5/release/core.py` and `qa/release/verify_rc7_source.py` examining `docs/rc7/compose.truenas.yaml`. Those paths are deliberately left in place until the tools themselves can be migrated safely.

- [Original version-bound CI definitions at the immutable v1.0.0 tag](https://github.com/heller-adrian/Bibliothekar/tree/v1.0.0/.github/workflows)
- [Post-1.0 workflow inventory](history/ci-workflows.md)
- [Pre-release notes](pre/) and [Pre.5 release evidence](pre5/)
- [RC14 release candidate reports](rc14/)
- [Older QA practices](practice/)

**History is not the active configuration.** Current installation guidance belongs in the root README and current Compose examples.

## Public release caution

The `v1.0.0` tag preserves the entire historic source tree, including old documentation and GitHub Actions YAML. Moving or deleting files from `main` does **not** remove them from reachable Git history. Do not switch repository visibility until current and historic content, release artifacts, logs, comments and workflow permissions are reviewed.
