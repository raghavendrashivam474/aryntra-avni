
ADR 0002: Language and Runtime Selection for V0
Context
Avni requires a programming runtime for contracts, capability orchestration, adapter bindings, and tests.

Options Considered
Python (3.10+): Native ecosystem for TTS/AI research, standard data structures (dataclasses, typing), straightforward C/C++ FFI if needed, rapid integration.
Rust: High performance, but higher iteration cost during contract discovery phase.
TypeScript/Node: Good for web services, weaker for local TTS engine integrations and future ML pipelines.
Decision
Use Python 3.10+ standard library as the core contract foundation. Core contracts and orchestrators will rely solely on Python standard libraries (dataclasses, typing, abc) to keep the core dependency-free.

Status
Accepted