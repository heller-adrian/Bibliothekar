<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/bibliothekar-logo-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/bibliothekar-logo-light.svg">
  <img src="docs/bibliothekar-logo-light.svg" width="560" alt="Bibliothekar — camera library management">
</picture>

### From camera card to camera archive. Carefully.

**Self-hosted photo ingestion, event organization and verified archiving for TrueNAS.**

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-3b657f)](LICENSE)
[![Container: GHCR](https://img.shields.io/badge/Container-GHCR-15222c)](https://github.com/heller-adrian/Bibliothekar/pkgs/container/bibliothekar)
[![Platform: TrueNAS](https://img.shields.io/badge/Platform-TrueNAS-3b657f)](https://www.truenas.com/)

[Overview](#overview) · [Workflow](#how-it-works) · [Features](#what-bibliothekar-does) · [Installation](#install-on-truenas) · [Safety](#data-safety) · [Deutsch](#kurz-auf-deutsch)

</div>

---

## Overview

**Bibliothekar** is a self-hosted web application for photographers who want to manage camera files deliberately, rather than hand their original photo archive to an opaque automation.

It bridges the gap between an SD card and a durable, organized camera library. You can import and check media, group related files, organize images into events, work with your own folder structure and verify the final archive. The archive remains under **your control**.

Bibliothekar runs locally as a container. It is designed primarily for **TrueNAS SCALE** and can be installed as a **Custom App**. It is **not yet an officially listed TrueNAS Apps Catalog / Discover app**.

> **The central idea:** Backup and working files may be managed by the application. Changes to the long-term camera archive are explicit, reviewable and verified — not silent background reorganizations.

## How it works

```text
Camera / SD card / existing folders
                │
                ▼
       Back up and inspect
       Metadata · duplicates · file families
                │
                ▼
          Shared photo stock
       Dates · unassigned captures
                │
                ▼
           Plan events
       Named events or "No Event"
                │
                ▼
          Working library
       Custom folders · manual selection
                │
                ▼
          Prepare archive
       Compare source and destination
                │
                ▼
         Verify and finish
       Read-only archive · open tasks
```

Bibliothekar **does not decide which photographs are good**. You remain free to select, edit, export and rearrange your photos using your preferred tools.

## What Bibliothekar does

| Area | Capabilities |
| --- | --- |
| **Import** | Read camera backups and configured folder/NAS sources; optional read-only removable-media support |
| **Media integrity** | Inspect capture metadata and duplicates; keep RAW/JPEG pairs and related sidecars associated |
| **Events** | Organize captures into dated events, subevents and configurable *No Event* collections |
| **Workspaces** | Plan and preview folder operations; use configurable, event-specific directory layouts |
| **Metadata** | Correct capture dates safely, including batch correction using a reference photograph and a constant time offset |
| **Multiple libraries** | Keep independent library databases, working areas and archive destinations while coordinating shared incoming media |
| **Archive** | Check files and structures, prepare explicit archive actions and verify the result; track remaining tasks |
| **Change handling** | Detect external file/folder changes and support controlled editing, rollback and recovery workflows |
| **Everyday use** | Browser interface and installable web app (PWA), with English and German UI |

### One file, one history

A RAW file and its matching JPEG should not lose their relationship just because they are moved into an event. A photograph should not silently be assigned twice. A failed or interrupted operation should not be mistaken for a successful one. Bibliothekar is built around **file identity, visible states, verification and recoverable operations**.

### Your archive stays yours

An event can change long after its photographs have been archived. Bibliothekar can prepare the necessary changes and verify their result, but its recommended archive mount is **read-only**. The actual archive file operations remain deliberate administrator actions.

## Install on TrueNAS

The repository provides a [Compose example](compose.example.yaml) for a TrueNAS **Custom App**. This is not the same as an official one-click Catalog/Discover installation.

**Before you start:** Create and configure separate persistent storage locations for application data, the shared workspace and the primary camera archive. Set appropriate TrueNAS ACLs and permissions. Never point a test instance at an existing production database or workspace.

1. Open [`compose.example.yaml`](compose.example.yaml) and configure the required host paths `BIBLIOTHEKAR_APPDATA_DIR`, `BIBLIOTHEKAR_WORKSPACE_DIR` and `BIBLIOTHEKAR_MAIN_LIBRARY_DIR`.
2. Set `BIBLIOTHEKAR_ADMIN_PASSWORD` to a strong password (**at least 16 characters**). The example uses port `30044`.
3. Mount **app data** and **workspace** read/write; mount the **archive read-only**. Verify the paths and filesystem permissions before starting.
4. Deploy the Custom App and finish the web-based setup. Back up app data and your database before upgrading.

```text
Image: ghcr.io/heller-adrian/bibliothekar:1.0.0
Web UI: http://<your-truenas-host>:30044
```

**Release note:** The `1.0.0` image is the intended stable release tag. Verify that the [GitHub Release](https://github.com/heller-adrian/Bibliothekar/releases) and the corresponding GHCR image have actually been published before installing it. For reproducible deployments, pin a numbered image tag or digest rather than relying on `latest`.

| Container path | Use | Mount |
| --- | --- | --- |
| `/appdata` | Configuration, SQLite databases and recovery state | Persistent RW |
| `/workspace` | Shared incoming stock and working data | Persistent RW |
| `/main-library` | Primary camera archive | **RO** |
| `/tmp` | Temporary runtime files | tmpfs |

The [Compose example](compose.example.yaml) is authoritative for the actual container configuration. Optional NAS sources and additional library roots require explicit configuration.

### SD cards and USB drives

The default deployment uses folder-based sources **without privileged container mode**. Direct detection and mounting of physical SD/USB devices is a separate optional capability and requires additional host/device permissions. Do **not** enable elevated privileges just for convenience; consult the deployment/security documentation and assess the impact on your TrueNAS host. Automatic removable-device operation is not yet qualified for an official TrueNAS catalog listing.

## Data safety

- **Read-only archive boundary:** The recommended container setup cannot write directly into the camera archive.
- **Explicit operations:** Preview and confirm significant changes; review open tasks before declaring the workflow complete.
- **Verification:** File sizes, hashes and live file inventories are used where appropriate to detect incomplete or inconsistent states.
- **Recovery state:** SQLite databases and persistent operation journals must be retained and backed up. Do not delete journals or reservations to bypass a blocked operation.
- **Least privilege:** Mount only the directories the application actually needs. Do not expose the web UI directly to the public internet; use appropriate access controls and HTTPS for remote use.
- **One active writer:** Never run multiple instances against the same application database/workspace.

Like any file-management software, Bibliothekar is **not a replacement for an independent backup** of your original photos and application state.

## Scope

The **1.0.0 milestone** focuses on the stable camera-file workflow. Bibliothekar is **not** a photo gallery, an Immich replacement or an AI-based photo selector. Possible future integrations (including Immich and optional AI-assisted preselection) are separate work, not promised features of 1.0.0.

## Project and development

[Source code](app/) · [Automated tests](tests/) · [QA](qa/) · [Technical documentation](docs/) · [Changelog](CHANGELOG.md) · [Security policy](.github/SECURITY.md) · [Releases](https://github.com/heller-adrian/Bibliothekar/releases)

Development combines backend regression tests, integration tests and hands-on UI and TrueNAS checks. A green workflow alone is not a promise that every possible storage configuration is supported.

### Reporting problems

For suspected vulnerabilities, follow our [private disclosure policy](.github/SECURITY.md), not a public issue. For ordinary bugs, please include the exact version or container digest, relevant TrueNAS information, expected versus actual behavior and reproducible steps. **Remove personal photographs, database contents, passwords, tokens, device identifiers and internal network details** before posting logs or screenshots.

## Kurz auf Deutsch

**Bibliothekar** ist eine selbst gehostete Web-App zur sicheren Organisation von Kameraaufnahmen auf TrueNAS. Sie begleitet den Weg von der SD-Karte über Sicherung, Metadatenprüfung, Ereigniszuordnung und Arbeitsbereich bis zur langfristigen Kamerabibliothek.

Im Mittelpunkt stehen **nachvollziehbare Dateioperationen, zusammengehörige RAW-/JPEG-Dateien, kontrollierte Änderungen und eine möglichst schreibgeschützte Archivbibliothek**. Du behältst die Entscheidung darüber, wie deine Fotos sortiert und archiviert werden. Die Oberfläche ist auf Deutsch und Englisch verfügbar.

Die Installation erfolgt zunächst als **TrueNAS Custom App**. Eine Aufnahme in den offiziellen TrueNAS-Katalog ist angestrebt, aber noch nicht erfolgt.

## License

Bibliothekar is free and open-source software licensed under the **GNU Affero General Public License v3.0**. See [LICENSE](LICENSE).
