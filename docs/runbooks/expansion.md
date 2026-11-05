# P07–P12 local expansion

Run `make bootstrap` and `make dev`. The optional real engines need:

```sh
make local-model
make blender
```

Model setup downloads only pinned public Apache-2.0 weights and verifies their
SHA-256. It makes no remote inference call. CPU compilation requires GCC/G++ and
may take several minutes. Blender setup accepts `/usr/bin/blender` only at 4.3.2;
otherwise it verifies and extracts the official Linux x64 archive. If it installs
a private runtime, set `BLENDER_EXECUTABLE` to the path in `.local/blender.env`
before starting the supervisor. Optional weights/runtime are excluded from the
source archive; missing engines report BLOCKED_EXTERNAL.

## Generate and render

Create a text dataset, visit **Teacher Studio**, connect the licensed local model
with explicit intended-use permission and rights evidence, select the dataset,
write instructions, save the recipe/estimate and start generation. Real accepted
outputs are marked UNREVIEWED_MODEL. Use P06 curation for human review; schema
checks are not correctness judgments. The small model is for pipeline testing.

Create an image dataset and visit **Simulation Studio**. Choose cube/sphere,
scenes, frames, resolution and seed, save/estimate, then render. Inspect the run
and dataset: frames, mask-derived boxes, protected object masks, a checksum-verified
GLB viewer, calibration/pose/timestamp metadata, data card, and actual COCO/YOLO
bundles. GLB is lazy-loaded on inspection and needs browser WebGL2. Isaac options
report their hardware/runtime blocker and never launch fake episodes.

Generated samples are accepted once into an immutable source artifact/checkpoint;
Temporal retries reuse it. Cancellation/revocation is checked during native work
and before publication. Local internal cost is the configured per-sample rate
card, not a cloud price. Accepted tokens and runtime milliseconds are separate
usage metrics; external charges are zero. Failed/unaccepted native attempts are
not invoiced, and this is not a full hardware cost model.

## Connect an outbound agent

In **Compute**, register an `agent` pool with an approved capacity envelope,
enroll an identity, and save its one-time token privately. Inject
`FOUNDRY_AGENT_TOKEN` and optional `FOUNDRY_API_URL` into its process, then run
`uv run python -m foundry.agent`. Queue an immutable version for verification.
The fixed operator downloads the artifact, checks its SHA-256, and completes its
lease; the API independently verifies the result. No user code executes.

Agents heartbeat with capabilities. A dead connection causes lease expiry and a
fresh fenced retry, capped at three attempts. Stale results and revoked identities
are rejected. Pool capacity is enforced across concurrent leases. Local commands
use HTTP only on loopback; external deployment requires operator-approved TLS,
network access, installation and secrets. Kubernetes/Kueue and Slurm templates/
codecs in `foundry.external_adapters` have no connected cluster or live proof.

## Evaluate without contaminating training

**Evaluations** provides lexical PostgreSQL search, distributions and exact
version diffs. New publications are indexed atomically; historical versions can
be indexed with `POST /v1/versions/{id}/index`.

Protect a separate, independent published dataset as a holdout in **Governance**.
An active run/compute lease or exact overlap prevents conversion; legacy sources
without indexes are checked within a bounded operator action. More than 1,000
unindexed versions require an offline backfill first. Ordinary training users/
keys cannot read held-out solutions. Exact hashes do not establish semantic
independence or eliminate near-duplicate leakage.

Register the fixed benchmark and its origin, then import externally measured
counts with a model/run reference, denominators, optional slices, and limitations.
Mark synthetic fixture counts as such. The console calculates descriptive
accuracy/Wilson intervals and compares results only on the same benchmark.
Feedback stores target slices, sample/budget caps and a manual decision. It does
not run training or generation automatically. Scientific gains need independent
measurement beyond this local protocol fixture.

## Governance and SCIM

Save immutable organization policy revisions for native PII measure/block/redact,
license lists, human review and retention. Redaction precedes review/publication;
the raw upload remains a private source until approved artifact erasure. Policy
changes can invalidate in-flight runs or existing unfrozen curation approvals.

Place legal holds; ask a different administrator to approve a hold release or
erasure request. Review the preview's object count/shared references/plan digest,
observe the configured delay and type the exact dataset name. Execution commits
a tombstone, then Temporal deletes the sealed S3 versions. A failed worker leaves
the dataset inaccessible and supports an explicit retry. Immutable audit,
manifests, review metadata and other live datasets' shared blobs remain.

SCIM tokens are one-time, hashed and domain restricted. Use a dedicated bearer
client at `/v1/scim/v2`: Users CRUD, `userName eq "address@example.com"`,
1-based pagination, and `If-Match` from ETag/meta.version. Only core User schema,
Engineer/Labeler/Viewer and the documented PATCH paths are supported. Deactivation
removes only this tenant's membership and keys, preserving global password and
other tenants. Provisioning tokens cannot edit privileged memberships. Deleted
bindings remain tombstoned; no implicit reprovision/reset is offered. SSO/Groups/
Bulk/Password and a live licensed IdP are blocked, not simulated.

## Operations and recovery

Use **Operations** to reconcile usage balances, scan actual failed runs/stale
agents, acknowledge signals and retain signed readiness reports. An incident
acknowledgement records ownership; it does not repair a failed run.

Run checks serially, after finishing/cancelling all dataset and compute work:

```sh
make test-recovery
make test-load
make scan-security
```

The recovery drill blocks API writes through `.local/maintenance.json`. It
performs a real PostgreSQL/S3 recovery and a restored API/configuration rehearsal,
then removes only its generated temporary DB/bucket. Do not run browser mutations
or other operator checks during it. Private backups and version maps are in
`.local/backups` with restrictive permissions, include credential-bearing
metadata, and must never be published. The app secret is a separate recovery
prerequisite. Temporal service history and external KMS/SSO are outside this drill.
If the process is killed forcibly, inspect its marker and generated recovery
resources before resuming writes; do not delete live volumes.

Load proof is 60 local read requests at concurrency 4, with observed p50/p95,
error count and throughput. It does not test a production SLA or GPU fleet.
Security proof includes actual dependency advisories and a source scan for local
private values. The remaining optional diskcache advisory and lack of independent
pentest remain documented production blockers.

Proof imports require the operator's HMAC, current source SHA-256 and a measured
local report. API keys alone cannot forge them. Readiness requires recent evidence
against the current source, and keeps production release blocked independently.
No staging/public URL, production IdP, external provider/cluster or Git remote is
configured. Hosted CI, PR review, staging demonstration/traffic rollback and
production cutover remain unavailable.

## SDK and CLI

Python exposes `providers`, `compute`, `simulations`, `evaluations`, `governance`,
`operations`, and a separate-token `scim` namespace. Generated request models live
in `datafoundry.models`; helpers also accept JSON dictionaries. TypeScript exposes
the same domains with generated request types. Existing recipe/run helpers launch
teacher and simulation DSL sources. Both SDKs expose generic requests for the
remaining public protocol endpoints and support SCIM `If-Match` updates.

```python
from datafoundry import DataFoundry
from datafoundry.models import ProviderCreate
import os

with DataFoundry(api_key=os.environ["FOUNDRY_API_KEY"]) as api:
    print(api.providers.catalog())
    print(api.simulations.capabilities())
    print(api.operations.reconcile())

# Use a separate enrolled provisioning token, never a browser public key.
with DataFoundry(api_key=os.environ["FOUNDRY_SCIM_TOKEN"]) as provisioning:
    print(provisioning.scim.configuration())
```

`datafoundry api GET /v1/operations/status` and
`datafoundry api POST /v1/compute/registered-pools --body pool.json` use the same
real HTTP API, scopes and idempotency. One-time credentials returned by creation
commands must be treated as private output. Never paste them into issue bodies,
screenshots or source files.

## Local build and recipe examples

After `pnpm build`, `FOUNDRY_WEB_MODE=production make dev` serves the optimized
web output locally. This changes the frontend start command; it does not deploy
anything or enable production authentication.

API recipe definitions are in `examples/teacher-recipe.json` and
`examples/blender-recipe.json`. Replace the teacher connection placeholder with
an approved local connection ID and use a text target; Blender needs an image
target. Validate with `datafoundry recipes validate PATH` before creation,
estimation and run submission.

Recovery restores committed object versions. Unfinished multipart sessions need
re-upload; the saved development-server workflow history, external KMS and SSO
need separate production recovery procedures.
