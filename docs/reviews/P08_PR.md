# Add scoped outbound compute agents and fenced verification leases

An enrolled agent can claim a real immutable-artifact verification job, download its authorized bytes and report a checksum that the API independently verifies. Heartbeats, pool capacity, resource compatibility, one live lease per agent, expiry, fresh fencing tokens, attempt caps, cancellation and revocation are persisted. The console and SDKs expose pool/identity/job management.

Validation: see the executed commands, native artifacts, SDK tests, browser journeys, accessibility/screenshots, and failures/corrections in [the batch evidence](../../verification/evidence/p07-p12/VERIFICATION.md). The feature matrix records partial and blocked scope explicitly.

Kubernetes/Kueue templates and Slurm codecs have contract proof only. No cluster, GPU, queue account, billed compute or arbitrary user workload is configured. H100/H200/A100 cannot satisfy Isaac rendering.

Local review draft for `phases/p07-p12-completion`, based on P06 `0f1d469`. The user requested one combined build effort. No hosted PR is open: this checkout has no Git remote. No remote change or merge is claimed.
