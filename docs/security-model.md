# Security Model

## Trust Boundary

The dashboard is designed for a private operations surface. Public internet exposure should happen
only through a TLS reverse proxy with explicit access controls.

## Default Protections

- Read-only application behavior.
- Separate viewer and developer tokens.
- Developer diagnostics stripped from viewer payloads.
- Session identifiers pseudonymized for viewer payloads.
- Search API responses use the same viewer/developer redaction rules as live WebSocket events.
- Redis not exposed on the host network in the default Compose file.
- Dashboard bound to localhost in the default Compose file.
- Developer demo event injection disabled by default.
- Local context folders ignored by Git.

## Deployment Checklist

1. Generate high-entropy viewer and developer tokens.
2. Bind the service behind TLS.
3. Keep Redis private to the Docker network or private subnet.
4. Back up the `/data` volume if the local archive is operationally important.
5. Disable debug profiles in production.
6. Keep `DASHBOARD_ENABLE_DEV_TOOLS=false` outside local smoke tests.
7. Verify reverse proxy logs do not retain sensitive query strings.
8. Run the public-term scan before release.
9. Enable GitHub branch protection and required CI checks.

## Data Handling

Viewer payloads should contain operational status only. Developer payloads may contain trace details,
but the dashboard should still avoid long-term storage. If persistent storage is added later, it must
go through a privacy and retention review.
