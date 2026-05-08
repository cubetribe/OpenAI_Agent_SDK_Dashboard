# Roadmap

## Phase 1: Foundation

- Trace event ingestion over Redis Pub/Sub.
- WebSocket broadcast with replay buffer.
- Static dashboard UI that shows live event flow.
- Docker Compose deployment.
- Security and governance baseline.

## Phase 2: Operational Dashboard

- Configurable workflow graph with active, success, and error states.
- Operator-friendly status summaries.
- Event feed with status and latency.
- Error highlighting without exposing sensitive diagnostics to viewer clients.

## Phase 3: Developer Diagnostics

- Developer-only span detail panel.
- Token, latency, and cost fields when provided by upstream events.
- Optional local debug tooling profile.
- Configurable customer deployments without source-code changes.
