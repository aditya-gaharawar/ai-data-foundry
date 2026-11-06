# ADR 012: Recover sessions and diagnose dependency failures explicitly

The user cancelled deployment and asked to improve the local codebase. P14
preserves the existing services, local authentication and persisted workflows.

Previously, any unsuccessful initial session check displayed the login form;
an unsuccessful background check could retain an older successful session in
the query cache. The console now treats only HTTP 401 as signed out. Other
failures show a retry screen. A confirmed expired session cancels and removes
workspace queries before another user signs in. Cancellation signals reach the
session fetch, and invalid error documents cannot crash the error display.

The Next.js proxy previously buffered the entire incoming request before the
API's 1 MiB control-body limit ran. It now checks declared and streamed lengths
before forwarding. This does not change dataset upload limits: multipart object
storage transfers already follow a separate path. Proxy failures carry request
IDs and Problem Details, and responses are not cached.

Readiness previously short-circuited after the first dependency failure and ran
a synchronous database query on the event loop. Independent concurrent probes
now check PostgreSQL, S3 and Temporal under four-second deadlines. Synchronous
clients run in threads with native connection/read/statement limits. The
database probe uses its own connection instead of moving a request session
between threads. Worker heartbeats remain a separate signal; adding them to API
readiness would create a startup dependency cycle with the worker.

No schema migration or public API response-shape change is needed. Failure
injection is limited to isolated tests and browser routes; real services remain
the basis for the successful login, dataset, workflow, and export checks.

Full browser verification exposed an existing evaluation-import race: the
success toast appeared before the refreshed evaluation list contained the new
record. A quick click on the next form hit native required-select validation
and never submitted feedback. The confirmed import response now populates the
tenant's query cache before selecting that record. A delayed list refresh in
the browser test proves feedback uses the actual newly persisted evaluation.
