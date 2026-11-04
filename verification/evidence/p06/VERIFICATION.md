# P06 local verification

Verified checkpoint: **2026-11-05 02:30 IST**. This is a local text-category and image-box
curation milestone. It is not a production release or an assertion of label accuracy.

The complete story is: authenticated source upload/version → immutable quality
profile and cleaning report → assigned, revision-checked independent reviews →
consensus/adjudication → authored data card and blocking quality gate → frozen
approval → budgeted Temporal worker → immutable version → matching signed exports.

## Executed commands

| Command | Exit | Actual result |
| --- | --- | --- |
| `make bootstrap` | 0 | Frozen dependencies including Pillow, infrastructure, migrations and seed |
| `make lint` | 0 | Ruff checks/format; web and TypeScript SDK type checks |
| `make test` | 0 | 20 unit/contract tests passed |
| `make test-integration` | 0 | 14 integration tests passed, including original core and both new SDK flows |
| `uv run pytest -q tests/test_curation.py -k test_rejected_sources_are_removed_before_publication` | 0 | 1 subsequently added rejection/publication test passed |
| `make test-security` | 0 | 8 security tests passed, including wrong image MIME, tenant, scope and replay negatives |
| `make test-e2e` | 0 | All 8 browser tests passed; original six plus image and multi-reviewer journeys |
| `make smoke` | 0 | 1 repeated core SDK/webhook scenario passed; not counted again |
| `pnpm build` | 0 | Optimized production build and TypeScript passed |
| `uv run python scripts/verify_fresh_database.py` | 0 | Clean migrations/seed/drift, API restart persistence and tenant denial |
| `uv run python scripts/verify_curation_checkpoint.py` | 0 | Real P06 API restart, unchanged labels/history/card/manifest, matching image bundles |
| `uv run python scripts/contracts.py --check` | 0 | OpenAPI 3.1: 60 paths; 46 generated Python models, no drift |
| `uv run alembic check` | 0 | No new upgrade operations detected |
| `uv run datafoundry curations --help` and `annotations --help` | 0 | Actual installed CLI commands available |
| Additional Playwright/Axe setup/profile capture | 0 | Six extra light/dark desktop/mobile checks, zero violations/overflow |

**51 unique automated tests passed**: 20 unit + 15 integration + 8 security +
8 browser. The integration count includes the targeted rejection test added after
the full 14-test integration run. Smoke, manual checkpoint and screenshot checks
are additional verification, not extra unique test cases. Adjacent logs retain
actual command output and selection counts.

## Persisted evidence

- Curation: `cur_ebf7eeb12db34e768f0625b992b3316d`; task: `ant_085728dc811b452182dba3a34d653dcf`.
- Run: `run_76e399369a19440db771b08f410cdaf6`; version: `ver_76e399369a19440db771b08f410cdaf6`.
- Manifest SHA-256: `0d0abecee6611182d4824b3617d5f01b5fca69d0bc4d72e3c0b6efe0f8349d74`.
- `api-proof.json` records the matching worker/source hash, frozen snapshot hash,
  data card, explicit approval, real quality denominators, export checksums and
  actual second-tenant HTTP 404 results, including copied signed downloads.
- The API process changed from PID 202051 to
  210523; source labels, complete review history,
  frozen card/session and manifest hash remained identical.
- `sample-coco.zip`, `sample-yolo.zip` and `sample-reviewed.jsonl` are actual
  downloaded artifacts. The approved pixel box `[8, 6, 32, 24]` matches the UI,
  API, JSONL and COCO. YOLO is `0 0.375 0.375 0.5 0.5`. Both ZIPs include the
  exact decoded image bytes displayed by the authenticated preview.
- `browser-consensus-proof.json` records two independent accounts, a persisted
  reviewer correction, disagreement, independent adjudication, four history
  decisions, keyboard interaction and inert uploaded HTML.
- `screenshots/` contains **18 P06 screenshots**: 360/390/768/1024/1440 image editor
  widths in both themes, approved curation, text adjudication and setup/profile
  screens. The original priority-route screenshots were also refreshed by the
  complete browser suite. Private traces remain in ignored `.local/`.

## Security and failure proof

Tenant queries and composite tenant foreign keys protect profiles, sessions,
tasks, source/version media and exports. Mutations require current role/key
scopes, session CSRF/Origin where applicable, idempotency and expected revisions.
Concurrent first edits yield one success and one stale conflict. Repeating one
user's correction never counts as a second independent reviewer. A voter cannot
adjudicate their own round; a Labeler cannot manage profiles or approve publication.

Image validation rejects corrupt/MIME-mismatched files and invalid coordinates
or categories. An invalid accepted payload or incomplete review blocks the gate
and publishes nothing. Consensus rejection and adjudicated rejection remove bad
sources before the published snapshot. Database mutation tests reject profile,
review and frozen-task tampering. Existing crash/retry, budget and webhook tests
remain green. No credentials, cookies, signing secrets or signed grants are
included in public evidence or the source archive.

## Genuine failures and corrections

1. The previous task's foreground supervisor had exited. The first live-service
   attempt reported 7 passing validation tests and 4 connection errors. The local
   runner was restored as a detached supervisor; the complete targeted set passed.
2. Initial browser selectors used exact label text around native selects, which
   includes option text in that selector API. Tests now use the controls' semantic
   combobox role and accessible name. No fake success replaced a failed request.
3. Axe found duplicate unlabeled complementary landmarks. Workspace and curation
   sidebars now have distinct accessible labels; the complete browser and extra
   setup/profile checks pass.
4. The additional screenshot harness initially used Playwright's implicit owned
   context, which Axe cannot extend. It now creates an explicit BrowserContext;
   the six checks and captures succeeded.

## Scope and remaining gates

Supported local scope: up to 500 curation rows / 20 MiB, text categories, normalized
PNG/JPEG and finite pixel boxes, exact plus lexical/perceptual near matching,
independent reviews/adjudication, cards and reviewed JSONL/COCO/YOLO publication.
Machine suggestions, semantic dedupe, PII/contamination checks, measured annotation
accuracy, advanced label types, distributed curation and production identity/ops
remain unimplemented. P07–P12 remain later phases. No paid provider calls, external
model transmission, chargeable infrastructure or deployment occurred.

Feature matrix: **51 TESTED, 13 INTEGRATED with scoped limits, 44 NOT_STARTED**
across 108 product features. No feature is RELEASED. Full application-container
execution and remote CI remain unverified; the tested runner uses persistent
Compose services plus supervised host application processes.

The phase is reviewable on local branch `phase/p06-curation-annotation` with the
proposed PR body in `docs/reviews/P06_PR.md`. There is no configured Git remote,
so no hosted PR was opened or merged. P06's hosted-PR requirement remains blocked
by that missing repository connection.
