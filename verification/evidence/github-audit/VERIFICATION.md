# Security audit and GitHub publication preparation

6 November 2026. Defensive source review and regression testing; this is not a
certification that the application has no zero-day vulnerabilities.

## Confirmed fixes

1. Organization-bound API keys exposed the owner's other organization memberships
   through `/v1/organizations` and `/v1/auth/session`. Session responses also
   advertised full role scopes instead of the key's delegated scopes. Both new
   regression cases failed against the previous API and pass after the fix.
   Key responses now contain only the bound organization and effective scopes;
   browser sessions retain legitimate organization switching. No unauthorized
   dataset access or permission escalation was demonstrated.
2. An oversized completed S3 object returned an error while leaving the upload
   marked UPLOADING and its unread body open. It now persists REJECTED and closes
   the response body. A controlled storage-response regression verifies both.

## Executed checks

- Lint/format and TypeScript checks passed.
- 40 unit/contract cases passed, including the upload rejection regression.
- 18 security cases passed, including both real-service API-key identity tests.
- 2 browser lifecycles passed: create/run/export and multipart upload/publication.
- SDK, signed webhook, export and CLI smoke passed.
- No npm advisories; 68 installed Python packages checked against OSV.
- Known diskcache 5.6.3 advisory remains in optional local-model dependencies.
  No disk cache is configured and the inference wrapper refuses one. This is an
  existing production blocker, not a newly discovered or fixed vulnerability.
- 698 historical Git blobs checked against current private configuration values
  and recognizable GitHub/private-key patterns: zero matches; no oversized Git
  blobs. Ignored credentials, local data and raw traces are absent from tracked files.

CI is manual (`workflow_dispatch`) with read-only repository permissions. No
Actions run, external model call or deployment was requested by publication.
