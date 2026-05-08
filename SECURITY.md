# Security Policy

## Supported Versions

Security fixes target the latest released version and `main`.

## Reporting a Vulnerability

Please report security issues privately through GitHub Security Advisories when available. If that is
not available, contact the repository owner directly and avoid posting exploit details in public
issues.

Include:

- affected version or commit
- reproduction steps
- expected impact
- any known workaround

## Security Baseline

- The dashboard is read-only by design.
- Viewer and developer access use separate bearer tokens.
- Redis is internal-only in the default Compose setup.
- Production deployments should terminate TLS at a reverse proxy.
- Public examples must not include tenant-specific prompts, contact data, trace dumps, or local
  context material.
