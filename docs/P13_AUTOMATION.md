# Bounded schedules and private notifications

Use **Schedules** in the console to choose a dataset and immutable workflow
revision. Set an interval or daily time, a future start, an end within 30 days,
up to 100 launches, and per-run/total USD caps. Window inputs display IST; daily
cadence may use another valid IANA timezone. Preview the times and current cost,
then explicitly approve activation. Pickers show the 100 newest resources; the
API accepts any accessible identifier.

The worker checks current access, source rights, governance and budget on each
launch. An unavailable worker leaves schedules durable. Ticks over 120 seconds
late and overlapping runs are skipped. There is no backlog burst. Pausing or
cancelling stops future launches; cancel an already admitted run from its run
page. Resume explicitly reauthorizes the remaining launches under your current
account/key. Definitions are fixed: create a replacement to change them.

The total cap counts admitted estimates even after a failure/cancellation. The
local rate is nonbillable; this phase does not enable paid external calls.
`COMPLETED` means no further launch is scheduled, while each run retains its own
execution result. A schedule stops at 1,000 processed occurrences and must then
be replaced. Daily DST gaps are skipped; repeated times use their first occurrence.

The **Notifications** bell links to your personal workspace inbox. Only your
new run outcomes and schedule failures/skips appear. Mark-all applies through
a fresh server summary requested when you click it; later notices remain unread.
Generic notices remain
visible if a source later becomes protected, but navigation disappears when
your current access no longer permits the target. No messages leave the app.

Create a scoped API key with `datasets:read`, `runs:execute`, `schedules:manage`
and `notifications:read` for automation plus inbox access. Existing keys do not
gain these scopes automatically. Revoking a schedule's originating key blocks
future launches. Workspace Owner/Admin may explicitly resume it under their own
authority; Engineers control only schedules they created or authorized.

```python
from datetime import datetime, timedelta, timezone
from datafoundry import DataFoundry
import os

start = datetime.now(timezone.utc) + timedelta(minutes=5)
body = {
    "name": "Daily bounded refresh",
    "dataset_id": os.environ["FOUNDRY_DATASET_ID"],
    "recipe_revision_id": os.environ["FOUNDRY_REVISION_ID"],
    "definition": {
        "mode": "daily", "daily_time": "09:00", "timezone": "Asia/Kolkata",
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(days=3)).isoformat(),
    },
    "max_runs": 3, "run_budget_usd": "1", "total_budget_usd": "3",
}
with DataFoundry(api_key=os.environ["FOUNDRY_API_KEY"]) as api:
    print(api.schedules.preview(body))
    schedule = api.schedules.create({**body, "approved_for_scheduled_execution": True})
    print(api.schedules.occurrences(schedule["id"]))
    print(api.notifications.list(unread=True))
```

TypeScript has `client.schedules.{health,preview,create,list,retrieve,control,occurrences}`
and `client.notifications.{summary,list,read,readAll}`, with generated request and
response types. Python uses the equivalent namespaces (`read_all` for mark-all).

```bash
datafoundry schedules preview schedule-preview.json
datafoundry schedules create approved-schedule.json
datafoundry schedules list
datafoundry schedules control SCHEDULE_ID pause REVISION
datafoundry schedules control SCHEDULE_ID resume REVISION --approve
datafoundry schedules occurrences SCHEDULE_ID
datafoundry notifications list --unread
datafoundry notifications summary
datafoundry notifications read NOTIFICATION_ID
datafoundry notifications read-all SERVER_AS_OF_TIMESTAMP
```

The create body requires `approved_for_scheduled_execution: true`. Use a fresh
`revision` from the schedule for control requests and a stable Idempotency-Key
when retrying a mutation. Console, SDK and CLI all call the same `/v1/schedules`
and `/v1/notifications` routes. Full contracts are at `/v1/openapi.json` and the
authenticated API reference. Local recovery drills require paused/cancelled
schedules and no active dataset/compute jobs.
