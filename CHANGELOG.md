# Changelog

All notable changes to this project are documented in this file.

The format follows Keep a Changelog and the project uses SemVer.

## [Unreleased]

### Added

- Redis publisher and OpenAI Agents SDK trace processor adapter for upstream integrations.
- Neutral registration example and integration documentation.
- Gated local dev-event injection and demo publisher for live browser smoke tests.
- SQLite event archive with searchable/filterable API and persisted Docker volume.
- GitHub Container Registry publishing workflow with SBOM and provenance attestations.
- Neutral runtime dashboard config for live workflow smoke tests.
- Runtime graph mode that derives workflow nodes and edges from live trace/span events.
- n8n-style runtime canvas with readable node cards, ports, arrow edges, and declared tool/handoff
  branches from safe agent metadata.
- Runtime canvas zoom controls and removed the event-panel live replay button.
- Safer OpenAI Agents SDK span extraction for slotted `SpanData.export()` payloads.

## [0.1.0] - 2026-05-08

### Added

- Initial FastAPI/WebSocket dashboard skeleton.
- Static browser UI with configurable graph metadata.
- Redis Pub/Sub ingestion boundary.
- Replay buffer and viewer/developer token roles.
- Docker, CI, test, security, and governance baseline.
