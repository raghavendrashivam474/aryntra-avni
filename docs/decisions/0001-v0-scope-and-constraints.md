# ADR 0001: V0 Scope, Non-Goals, and Architectural Guardrails

## Context

Aryntra Avni is starting its implementation phase. NAV requires speech synthesis capability. There is a risk of premature expansion into voice cloning, composite identity research, and microservice infrastructure before the baseline is functional.

## Decision
```text
V0 is scoped strictly to establishing the voice capability foundation.
Composite identity, multi-speaker interpolation, and deep voice conversion research are deferred to V1+.
All synthesis engines must reside behind standard contracts.
No network or microservice boundary will be added unless required by NAV integration constraints.
```
## Consequences
```text
Positive: Fast path to working voice for NAV, zero wasted research overhead, clear upgrade path.
Trade-off: V0 voice identity is static configuration rather than dynamically synthesized composition.
```
## Status
Accepted