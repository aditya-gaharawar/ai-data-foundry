# Codex phased implementation

Use the detailed P00-P12 files in this directory. Every phase contains: outcome, required implementation, API/UI proof and abort criteria. Build P00-P05 in order for an actual usable core; P06-P12 add honest, verified integrations. Codex must never declare a phase complete based solely on scaffold/UI.

| Phase | Dependency | Proof |
|---|---|---|
| P00 Foundation | None | Fresh clone boot; API+DB+MinIO+web+worker health |
| P01 UX system | P00 | Functional sidebar, five starter routes, screenshot/a11y evidence |
| P02 Identity and data model | P00 | Auth and two-tenant isolation |
| P03 Registry/upload | P02 | SHA-verified upload, persisted dataset CRUD |
| P04 Recipes and jobs | P03 | Real job -> quality -> version -> export |
| P05 API/SDK/webhooks | P04 | OpenAPI, SDK, CLI, signed delivery, core E2E |
| P06 Curation/annotation | P05 | Human-reviewed labels and quality gate |
| P07 Model generation | P05 | Authorized provider, costs, rights and validation |
| P08 Compute/HPC | P04 | Correct scheduling, leases, agent security |
| P09 Simulations | P08 | Blender and then Isaac real artifacts/blocked capability |
| P10 Evaluation/feedback | P05 | Comparison and benchmark feedback workflow |
| P11 Enterprise and billing | P05 | Enterprise controls and reconciled charges |
| P12 Release hardening | All launched subsystems | Restore, security, load, launch approval |
