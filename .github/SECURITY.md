# Security Policy

Thank you for helping keep Bibliothekar and its users safe.

Bibliothekar manages camera originals, metadata, workspaces, SQLite application state and long-term archive workflows. Reports that could compromise files, access control, privacy or recovery integrity are taken seriously.

## Supported versions

The supported stable series is **1.0.x**, starting with the published release `v1.0.0`. Earlier prereleases, release candidates, development branches and superseded stable versions are not guaranteed security updates.

## Reporting a vulnerability

**Please do not report security vulnerabilities in public GitHub issues, discussions or pull requests.**

When **GitHub Private Vulnerability Reporting** is enabled, use **Report a vulnerability** on the repository's [Security page](https://github.com/heller-adrian/Bibliothekar/security) to report privately. **GitHub enables this feature for public repositories.** It must therefore be activated and verified immediately **after** making the repository public and **before** announcing the public launch. Until a working private reporting channel is available, publication should not be actively promoted.

If private reporting is unavailable, do not include security details in a public issue, discussion or pull request. Ask the maintainers to make a private channel available without revealing the vulnerability in public. Ordinary issues are for non-security bugs only.

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

Bitte melde vermutete Sicherheitslücken **nicht öffentlich** über GitHub-Issues. Wenn die vertrauliche Schwachstellenmeldung aktiviert wurde, verwende auf der [Security-Seite](https://github.com/heller-adrian/Bibliothekar/security) die Funktion **Report a vulnerability**. Steht sie noch nicht bereit, bitte die Projektverantwortlichen ohne technische Details um einen privaten Kontaktweg. Verwende für Nachweise künstliche Testdaten und entferne private Fotos, Kennwörter, interne Adressen und andere vertrauliche Informationen.

Die jeweils aktuelle stabile Version wird vorrangig unterstützt. Sicherheitsupdates für ältere Vorabversionen sind nicht zugesichert.
