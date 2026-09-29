# Security Policy

## Supported versions

Security fixes are provided for the latest published pre-release or stable release. Older pre-release builds are not maintained after a replacement is available.

## Reporting a vulnerability

Use GitHub private vulnerability reporting after it is enabled for the published repository. If that channel is unavailable, contact the maintainers through a private channel identified by the repository owner. Do not open a public issue containing exploit details, credentials, private project state, or review records.

A useful report includes the affected version, impact, minimal reproduction, and whether the issue can expose credentials, bypass dependency/evidence rules, corrupt state, or permit non-human final gate approval. Maintainers should acknowledge the report privately before coordinating remediation and disclosure.

## Sensitive data boundary

Never store passwords, API tokens, private keys, embedded-credential URLs, personal access tokens, or private logs in `.ipd/project_state.yaml`, policies, evidence fields, fixtures, prompts, or generated artifacts. Use repository-relative paths or approved external record identifiers. `scripts/release_check.py` provides a high-confidence pre-publication scan, but it does not replace secret revocation if a credential was ever committed.
