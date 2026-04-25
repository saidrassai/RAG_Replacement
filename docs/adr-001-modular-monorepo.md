# ADR 001: Modular Monorepo Over Day-One Microservices

## Status

Accepted

## Decision

Use a Python-first modular monorepo with installable workspace members instead of splitting the system into separate deployable services immediately.

## Why

- The first milestone is a thin vertical slice, so package boundaries matter more than deployment boundaries.
- Shared contracts, storage models, and orchestration logic would be duplicated or over-networked in an early microservice split.
- Celery already gives us async boundaries for Phase B and governance jobs without forcing an API boundary between every component.
- A workspace keeps one lockfile, one toolchain, and one local developer workflow while still preserving future extraction paths.

## Consequences

- Service boundaries are expressed as packages and app entrypoints.
- Future extraction to separate repos or deployables should happen only after the APIs and operational needs stabilize.
- Some package dependencies are intentionally pragmatic in the first slice, especially around bootstrapping and wiring.
