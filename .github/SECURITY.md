# Security Policy

Thank you for helping keep Bibliothekar and its users safe.

Bibliothekar manages camera originals, metadata, workspaces, SQLite application state and long-term archive workflows. Reports that could compromise files, access control, privacy or recovery integrity are taken seriously.

## Supported versions

Security fixes are intended for the **most recent stable release** in the currently maintained series. At initial publication, this is the **1.0.x series**, once `v1.0.0` has been released. Earlier prereleases, release candidates, development branches and outdated stable versions are not guaranteed security updates.

If no stable version has been published yet, please identify the exact prerelease version and commit in your report.

## Reporting a vulnerability

**Please do not report security vulnerabilities in public GitHub issues, discussions or pull requests.**

Once the repository is public and **GitHub Private Vulnerability Reporting** is enabled, use the **Report a vulnerability** option on the repository's [Security page](https://github.com/heller-adrian/Bibliothekar/security). This provides a private channel for the maintainers to coordinate a fix.

If private vulnerability reporting is not available or not yet enabled, **do not post exploitation details publicly**. Wait for the maintainer to publish a verified private reporting channel. Ordinary issues are for non-security bugs only.

When reporting privately, please include, if safely available:

- The Bibliothekar version, image digest or exact commit.
- The affected component and expected versus observed security boundary.
- Minimal, reproducible steps using **synthetic data**.
- The potential impact and any relevant, redacted logs.
- Whether the issue requires authentication, particular mounts or elevated container privileges.

Do not include real photographs, private databases, passwords, tokens, recovery secrets, internal network addresses or personally identifiable information.

## Areas of particular concern

- Authentication, authorization, session handling and cross-library isolation.
- Unauthorized reads or writes through file paths, archive mounts, import sources or device helpers.
- Symlink, hardlink, path traversal and time-of-check/time-of-use attacks.
- Camera-original integrity, SHA/metadata verification and unintended file deletion or overwrite.
- SQLite state, operation journals, archive-change tasks, rollback and crash recovery.
- Container privileges, secrets handling and the optional removable-device helper.
- Exposure of private content through logs, UI, HTTP responses or published artifacts.

## Coordinated disclosure

Please allow the maintainers an opportunity to investigate and reproduce a privately reported vulnerability before public disclosure. Confirmed findings may be addressed through a security fix, a GitHub Security Advisory and release notes as appropriate.

Response and remediation times depend on severity, reproducibility and maintainer availability; **no fixed response or resolution deadline is promised**. Please do not test against other people's installations or attempt to access their personal media.

## Security guidance for installations

- Keep Bibliothekar and its dependencies updated and maintain independent, tested backups.
- Use the recommended **read-only archive mount**.
- Grant only necessary filesystem and device permissions; the optional SD/USB helper has elevated privilege requirements.
- Keep the web interface behind trusted network access controls and use HTTPS for remote access.
- Do not run multiple writers against the same application database.
- Never clear persistent journals or recovery reservations merely to bypass a safety block.

See the [README](../README.md) and the [TrueNAS deployment example](../compose.example.yaml).

---

## Sicherheitshinweis (Deutsch)

Bitte melde vermutete Sicherheitslücken **nicht öffentlich** über GitHub-Issues. Sobald die vertrauliche Schwachstellenmeldung aktiviert ist, verwende auf der [Security-Seite](https://github.com/heller-adrian/Bibliothekar/security) die Funktion **Report a vulnerability**. Verwende für Nachweise künstliche Testdaten und entferne private Fotos, Kennwörter, interne Adressen und andere vertrauliche Informationen.

Die jeweils aktuelle stabile Version wird vorrangig unterstützt. Sicherheitsupdates für ältere Vorabversionen sind nicht zugesichert.
