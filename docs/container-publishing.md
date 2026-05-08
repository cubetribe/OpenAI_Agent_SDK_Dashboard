# Container Publishing

## Image

The project publishes an OCI/Docker image to GitHub Container Registry:

```text
ghcr.io/cubetribe/openai-agent-sdk-dashboard
```

After the container workflow has run on `main`, pull the latest image:

```bash
docker pull ghcr.io/cubetribe/openai-agent-sdk-dashboard:latest
```

## Tags

The container workflow generates tags from:

- branch names
- pull request refs
- semantic version tags like `v0.2.0`
- commit SHA tags with `sha-` prefix
- `latest` on the default branch

## Supply Chain

The workflow follows GitHub and Docker's current publishing guidance:

- GitHub Actions authenticates to GHCR with `GITHUB_TOKEN`
- official Docker actions build and push the image
- Docker metadata action generates labels and tags
- BuildKit cache speeds up repeated builds
- SBOM generation is enabled
- max-level provenance attestations are enabled

## Runtime Data

The image declares `/data` as a volume. The SQLite event archive lives at:

```text
/data/dashboard.db
```

With Compose, the `dashboard_data` named volume persists this archive outside the container
writable layer.
