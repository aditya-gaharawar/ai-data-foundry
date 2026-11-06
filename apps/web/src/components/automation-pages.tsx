"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CalendarClock, CheckCheck, Plus } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import type { components } from "../../../../packages/sdk-ts/src/schema";
import type { Dataset, Page, Recipe } from "@/lib/api";
import { shortId } from "@/lib/api";
import { useResource, useWorkspace } from "./context";
import {
  Button,
  Empty,
  ErrorNotice,
  Loading,
  Modal,
  PageHeader,
  Status,
  useAction,
} from "./ui";

type Schedule = components["schemas"]["ScheduleOut"];
type Occurrence = components["schemas"]["OccurrenceOut"];
type Notice = components["schemas"]["NotificationOut"];
type Summary = components["schemas"]["NotificationSummary"];
type Preview = components["schemas"]["SchedulePreviewOut"];
type Definition = components["schemas"]["ScheduleDefinition"];
const when = (value: string | null, zone = "Asia/Kolkata") =>
  value
    ? `${new Date(value).toLocaleString("en-IN", { timeZone: zone, dateStyle: "medium", timeStyle: "medium" })} · ${zone}`
    : "—";
const usd = (micro: number) => `$${(micro / 1e6).toFixed(6)}`;
const inputTime = (offset: number) =>
  new Date(Date.now() + offset + 330 * 60_000).toISOString().slice(0, 19);

function useInboxSummary() {
  const { call, organization, session } = useWorkspace();
  return useQuery({
    queryKey: [organization.id, "inbox-summary", session.user.id],
    queryFn: () => call<Summary>("/notifications/summary"),
    enabled: organization.scopes.includes("notifications:read"),
    refetchInterval: 10_000,
  });
}

export function NotificationBell() {
  const { organization } = useWorkspace();
  const summary = useInboxSummary();
  if (!organization.scopes.includes("notifications:read")) return null;
  const count = summary.data?.unread_count;
  return (
    <Link
      className="icon-button notification-bell"
      href="/notifications"
      aria-label={`Notifications${count === undefined ? "" : `, ${count} unread`}`}
    >
      <Bell size={16} />
      {count !== undefined && count > 0 && (
        <span className="notification-count" aria-hidden="true">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </Link>
  );
}

export function NotificationsPage() {
  const { call, toast } = useWorkspace();
  const cache = useQueryClient();
  const action = useAction();
  const [unread, setUnread] = useState(false);
  const [cursor, setCursor] = useState<string | null>(null);
  const summary = useInboxSummary();
  const inbox = useResource<Page<Notice>>(
    `/notifications?unread=${unread}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    true,
  );
  async function mark(path: string, body?: unknown) {
    const result = await action.perform(() =>
      call(path, { method: "POST", body: body || {} }),
    );
    if (result) {
      await cache.invalidateQueries();
      toast("Inbox updated.");
    }
  }
  async function markAll() {
    const result = await action.perform(async () => {
      const snapshot = await call<Summary>("/notifications/summary");
      return call("/notifications/read-all", {
        method: "POST",
        body: { before: snapshot.as_of },
      });
    });
    if (result) {
      await cache.invalidateQueries();
      toast("Inbox updated.");
    }
  }
  return (
    <>
      <PageHeader
        eyebrow="WORKSPACE / INBOX"
        title="Notifications"
        description="Your run outcomes and schedule notices, private to this workspace account."
      >
        <Button
          variant="secondary"
          busy={action.busy}
          disabled={
            !summary.data?.unread_count &&
            !inbox.data?.items.some((item) => !item.read_at)
          }
          onClick={markAll}
        >
          <CheckCheck size={15} /> Mark all as read
        </Button>
      </PageHeader>
      <ErrorNotice error={action.error || inbox.error || summary.error} />
      <div className="inbox-toolbar">
        <span className="muted">
          {summary.data?.unread_count ?? "…"} unread
        </span>
        <label className="check-label">
          <input
            type="checkbox"
            checked={unread}
            onChange={(event) => {
              setUnread(event.target.checked);
              setCursor(null);
            }}
          />{" "}
          Unread only
        </label>
        {cursor && (
          <Button variant="ghost" onClick={() => setCursor(null)}>
            Newest notices
          </Button>
        )}
      </div>
      {inbox.isLoading ? (
        <Loading />
      ) : inbox.data?.items.length === 0 ? (
        <Empty
          icon={Bell}
          headingLevel="h2"
          title="You're all caught up"
          description="New run outcomes and scheduling notices will appear here."
        />
      ) : (
        <section className="panel" aria-label="Inbox notices">
          {inbox.data?.items.map((item) => (
            <article
              className={`notice-item ${item.read_at ? "" : "is-unread"}`}
              key={item.id}
            >
              <div className="notice-dot" aria-hidden="true" />
              <div className="notice-copy">
                <strong>{item.title}</strong>
                <p>{item.body}</p>
                <small>{when(item.created_at)}</small>
                <div className="inline-actions">
                  {item.target && (
                    <Link className="text-link" href={item.target}>
                      Open {item.kind.startsWith("run.") ? "run" : "schedule"} →
                    </Link>
                  )}
                  {!item.read_at && (
                    <Button
                      variant="ghost"
                      busy={action.busy}
                      aria-label={`Mark ${item.title} as read`}
                      onClick={() => mark(`/notifications/${item.id}/read`)}
                    >
                      Mark as read
                    </Button>
                  )}
                </div>
              </div>
              {item.read_at && <span className="muted">Read</span>}
            </article>
          ))}
        </section>
      )}
      {inbox.data?.next_cursor && (
        <Button
          variant="secondary"
          onClick={() => setCursor(inbox.data!.next_cursor!)}
        >
          Older notices
        </Button>
      )}
      <p className="muted automation-note">
        Notices use generic summaries. A link appears only while you retain
        access to its resource. Mark all uses a fresh server cutoff; later
        notices remain unread.
      </p>
    </>
  );
}

export function SchedulesPage() {
  const { organization } = useWorkspace();
  const params = useSearchParams();
  const [selected, setSelected] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [create, setCreate] = useState(false);
  const list = useResource<Page<Schedule>>(
    `/schedules?limit=25${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    true,
  );
  const health = useResource<components["schemas"]["SchedulerHealth"]>(
    "/schedules/health",
    true,
  );
  const selectedId = selected || params.get("selected") || "";
  const canCreate = ["datasets:read", "runs:execute", "schedules:manage"].every(
    (scope) => organization.scopes.includes(scope),
  );
  return (
    <>
      <PageHeader
        eyebrow="WORKFLOW ENGINE / AUTOMATION"
        title="Schedules"
        description="Pin a workflow revision. Set a finite window and budget. Let the worker handle each launch."
      >
        <Button onClick={() => setCreate(true)} disabled={!canCreate}>
          <Plus size={15} /> Create schedule
        </Button>
      </PageHeader>
      <ErrorNotice error={list.error || health.error} />
      <div className="automation-summary panel">
        <CalendarClock size={22} />
        <div>
          <strong>Bounded by design</strong>
          <p>
            Up to 100 launches over 30 days. Each launch rechecks current
            access, source rights, policy, and available budget.
          </p>
        </div>
        <div>
          <small>Schedule worker</small>
          {health.data && <Status value={health.data.status} />}
        </div>
      </div>
      {health.data?.status === "UNAVAILABLE" && (
        <div className="notice">
          The scheduler is unavailable. Saved schedules remain durable;
          occurrences more than 120 seconds late will be skipped when it
          recovers.
        </div>
      )}
      {list.isLoading ? (
        <Loading />
      ) : list.data?.items.length === 0 ? (
        <Empty
          icon={CalendarClock}
          headingLevel="h2"
          title="Make your next run automatic"
          description="Create an interval or daily schedule with explicit launch and cost limits."
        />
      ) : (
        <section className="panel table-wrap schedule-list">
          <table>
            <thead>
              <tr>
                <th>Schedule / cadence</th>
                <th>State</th>
                <th>Launches</th>
                <th>Admitted / cap</th>
                <th>Next launch (IST)</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {list.data?.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <button
                      className="text-link"
                      onClick={() => setSelected(item.id)}
                    >
                      {item.name}
                    </button>
                    <small>
                      {item.definition.mode === "interval"
                        ? `Every ${item.definition.interval_seconds}s`
                        : `Daily ${item.definition.daily_time} · ${item.definition.timezone}`}
                    </small>
                  </td>
                  <td>
                    <Status value={item.state} />
                  </td>
                  <td>
                    {item.launched_runs} / {item.max_runs}
                    <small>{item.skipped_runs} skipped</small>
                  </td>
                  <td className="mono">
                    {usd(item.admitted_micro)}
                    <small>of {usd(item.total_budget_micro)}</small>
                  </td>
                  <td>{when(item.next_run_at)}</td>
                  <td>
                    <Button
                      variant="ghost"
                      aria-label={`View ${item.name}`}
                      onClick={() => setSelected(item.id)}
                    >
                      View →
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      <div className="inline-actions">
        {cursor && (
          <Button variant="ghost" onClick={() => setCursor(null)}>
            Newest schedules
          </Button>
        )}
        {list.data?.next_cursor && (
          <Button
            variant="secondary"
            onClick={() => setCursor(list.data!.next_cursor!)}
          >
            Older schedules
          </Button>
        )}
      </div>
      {selectedId && <ScheduleDetail key={selectedId} id={selectedId} />}
      <p className="muted automation-note">
        Missed and overlapping launches are skipped. Resuming starts at the next
        future occurrence. Admitted estimates count toward the total cap even if
        a run later fails or is cancelled. Schedule definitions stay fixed;
        create a replacement to change them.
      </p>
      <Modal
        open={create}
        setOpen={setCreate}
        title="Create a bounded schedule"
        description="Preview and approve a finite series of launches. The schedule never calls paid services."
        className="schedule-modal"
      >
        {create && (
          <ScheduleForm
            onCreated={(id) => {
              setSelected(id);
              setCursor(null);
              setCreate(false);
            }}
          />
        )}
      </Modal>
    </>
  );
}

function ScheduleDetail({ id }: { id: string }) {
  const { call, toast, organization, session } = useWorkspace();
  const cache = useQueryClient();
  const action = useAction();
  const [consent, setConsent] = useState(false);
  const [cursor, setCursor] = useState<string | null>(null);
  const detail = useResource<Schedule>(`/schedules/${id}`, true);
  const occurrences = useResource<Page<Occurrence>>(
    `/schedules/${id}/occurrences?limit=10${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    true,
  );
  const row = detail.data;
  const canControl =
    row &&
    (["Owner", "Admin"].includes(organization.role) ||
      [row.created_by, row.authorized_by].includes(session.user.id));
  async function control(kind: "pause" | "resume" | "cancel") {
    const result = await action.perform(() =>
      call(`/schedules/${id}/control`, {
        method: "POST",
        body: {
          action: kind,
          expected_revision: row!.revision,
          approved_for_scheduled_execution: kind === "resume" && consent,
        },
      }),
    );
    if (result) {
      setConsent(false);
      await cache.invalidateQueries();
      toast(
        `Schedule ${kind === "pause" ? "paused" : kind === "resume" ? "resumed" : "cancelled"}.`,
      );
    }
  }
  return (
    <section className="panel schedule-detail" aria-label="Schedule details">
      <div className="panel-heading">
        <h2>{row?.name || "Schedule details"}</h2>
        {row && <Status value={row.state} />}
      </div>
      <div className="panel-body">
        <ErrorNotice
          error={action.error || detail.error || occurrences.error}
        />
        {row && (
          <>
            <dl className="automation-facts">
              <div>
                <dt>Pinned revision</dt>
                <dd>
                  <span className="mono">
                    {shortId(row.recipe_revision_id)}
                  </span>
                </dd>
              </div>
              <div>
                <dt>Dataset</dt>
                <dd>
                  <Link href={`/datasets/${row.dataset_id}`}>
                    {shortId(row.dataset_id)}
                  </Link>
                </dd>
              </div>
              <div>
                <dt>Window ends</dt>
                <dd>{when(row.definition.ends_at)}</dd>
              </div>
              <div>
                <dt>Per-run cap</dt>
                <dd>{usd(row.run_budget_micro)}</dd>
              </div>
            </dl>
            {row.last_error && (
              <div className="notice">
                <strong>{row.last_error_code}</strong> · {row.last_error}
              </div>
            )}
            {canControl &&
              !["COMPLETED", "EXPIRED", "CANCELLED"].includes(row.state) && (
                <div className="schedule-controls">
                  {row.state === "ACTIVE" ? (
                    <Button
                      variant="secondary"
                      busy={action.busy}
                      onClick={() => control("pause")}
                    >
                      Pause schedule
                    </Button>
                  ) : (
                    <>
                      <label className="check-label">
                        <input
                          type="checkbox"
                          checked={consent}
                          onChange={(event) => setConsent(event.target.checked)}
                        />{" "}
                        I authorize future launches under my current permissions
                        and the remaining caps.
                      </label>
                      <Button
                        busy={action.busy}
                        disabled={!consent}
                        onClick={() => control("resume")}
                      >
                        Resume schedule
                      </Button>
                    </>
                  )}
                  <Button
                    variant="danger"
                    busy={action.busy}
                    onClick={() => control("cancel")}
                  >
                    Cancel schedule
                  </Button>
                </div>
              )}
            <p className="muted">
              Pausing or cancelling prevents future launches. A run already
              admitted continues and can be cancelled from its run page.
            </p>
          </>
        )}
        <h3>Occurrence history</h3>
        {occurrences.data?.items.length === 0 && (
          <p className="muted">No occurrence has been processed yet.</p>
        )}
        {occurrences.data?.items.map((item) => (
          <div className="record-row" key={item.id}>
            <div>
              <strong>{when(item.scheduled_at)}</strong>
              <small>{item.message}</small>
              <small className="mono">
                {item.code}
                {item.estimate_micro ? ` · ${usd(item.estimate_micro)}` : ""}
              </small>
            </div>
            <div className="inline-actions">
              <Status value={item.status} />
              {item.run_id && (
                <Link className="text-link" href={`/runs/${item.run_id}`}>
                  Open run →
                </Link>
              )}
            </div>
          </div>
        ))}
        <div className="inline-actions">
          {cursor && (
            <Button variant="ghost" onClick={() => setCursor(null)}>
              Latest occurrences
            </Button>
          )}
          {occurrences.data?.next_cursor && (
            <Button
              variant="ghost"
              onClick={() => setCursor(occurrences.data!.next_cursor!)}
            >
              Older occurrences
            </Button>
          )}
        </div>
      </div>
    </section>
  );
}

function ScheduleForm({ onCreated }: { onCreated: (id: string) => void }) {
  const { call, toast } = useWorkspace();
  const cache = useQueryClient();
  const action = useAction();
  const datasets = useResource<Page<Dataset>>("/datasets?limit=100");
  const recipes = useResource<Page<Recipe>>("/recipes?limit=100");
  const [form, setForm] = useState(() => ({
    name: "",
    dataset: "",
    recipe: "",
    revision: "",
    mode: "interval" as "interval" | "daily",
    interval: "3600",
    daily: "09:00",
    timezone: "Asia/Kolkata",
    start: inputTime(120_000),
    end: inputTime(86400_000),
    launches: "2",
    runBudget: "1",
    totalBudget: "2",
  }));
  const [report, setReport] = useState<Preview | null>(null);
  const [consent, setConsent] = useState(false);
  const recipe = useResource<Recipe>(
    `/recipes/${form.recipe}`,
    false,
    !!form.recipe,
  );
  const update = (key: keyof typeof form, value: string) => {
    setForm((old) => ({
      ...old,
      [key]: value,
      ...(key === "recipe" ? { revision: "" } : {}),
    }));
    setReport(null);
    setConsent(false);
  };
  function payload() {
    const definition: Definition = {
      mode: form.mode,
      starts_at: new Date(`${form.start}+05:30`).toISOString(),
      ends_at: new Date(`${form.end}+05:30`).toISOString(),
      timezone: form.timezone,
      ...(form.mode === "interval"
        ? { interval_seconds: Number(form.interval) }
        : { daily_time: form.daily }),
    };
    return {
      name: form.name,
      dataset_id: form.dataset,
      recipe_revision_id: form.revision,
      definition,
      max_runs: Number(form.launches),
      run_budget_usd: form.runBudget,
      total_budget_usd: form.totalBudget,
    };
  }
  async function preview(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = await action.perform(() =>
      call<Preview>("/schedules/preview", { method: "POST", body: payload() }),
    );
    if (value) setReport(value);
  }
  async function create() {
    const value = await action.perform(() =>
      call<Schedule>("/schedules", {
        method: "POST",
        body: { ...payload(), approved_for_scheduled_execution: consent },
      }),
    );
    if (value) {
      await cache.invalidateQueries();
      toast("Schedule saved and activated.");
      onCreated(value.id);
    }
  }
  return (
    <form onSubmit={preview}>
      <ErrorNotice
        error={action.error || datasets.error || recipes.error || recipe.error}
      />
      <label className="field">
        <span>Schedule name</span>
        <input
          aria-label="Schedule name"
          required
          maxLength={160}
          value={form.name}
          onChange={(e) => update("name", e.target.value)}
        />
      </label>
      <div className="field-row">
        <label className="field">
          <span>Dataset</span>
          <select
            aria-label="Schedule dataset"
            required
            value={form.dataset}
            onChange={(e) => update("dataset", e.target.value)}
          >
            <option value="">Choose a dataset</option>
            {datasets.data?.items
              .filter((item) => !item.archived && item.protection !== "holdout")
              .map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
          </select>
        </label>
        <label className="field">
          <span>Workflow</span>
          <select
            aria-label="Schedule workflow"
            required
            value={form.recipe}
            onChange={(e) => update("recipe", e.target.value)}
          >
            <option value="">Choose a workflow</option>
            {recipes.data?.items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {item.id.slice(-6)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="field">
        <span>Pinned revision</span>
        <select
          aria-label="Pinned revision"
          required
          value={form.revision}
          onChange={(e) => update("revision", e.target.value)}
        >
          <option value="">Choose an immutable revision</option>
          {recipe.data?.revisions?.map((item) => (
            <option key={item.id} value={item.id}>
              {shortId(item.id)} · {item.digest.slice(0, 12)}
            </option>
          ))}
        </select>
        <small>
          Pickers show the 100 most recent datasets and workflows. Later
          workflow edits do not change this schedule.
        </small>
      </label>
      <div className="field-row">
        <label className="field">
          <span>Cadence</span>
          <select
            value={form.mode}
            onChange={(e) => update("mode", e.target.value)}
          >
            <option value="interval">Interval</option>
            <option value="daily">Daily at a local time</option>
          </select>
        </label>
        {form.mode === "interval" ? (
          <label className="field">
            <span>Interval (seconds)</span>
            <input
              required
              type="number"
              min={10}
              max={2592000}
              value={form.interval}
              onChange={(e) => update("interval", e.target.value)}
            />
          </label>
        ) : (
          <label className="field">
            <span>Daily launch time</span>
            <input
              required
              type="time"
              value={form.daily}
              onChange={(e) => update("daily", e.target.value)}
            />
          </label>
        )}
      </div>
      <label className="field">
        <span>Cadence timezone (IANA)</span>
        <input
          required
          value={form.timezone}
          onChange={(e) => update("timezone", e.target.value)}
          list="schedule-timezones"
        />
        <datalist id="schedule-timezones">
          <option value="Asia/Kolkata" />
          <option value="UTC" />
          <option value="America/New_York" />
          <option value="Europe/London" />
        </datalist>
      </label>
      <div className="field-row">
        <label className="field">
          <span>Start (IST)</span>
          <input
            aria-label="Schedule start (IST)"
            required
            type="datetime-local"
            step="1"
            value={form.start}
            onChange={(e) => update("start", e.target.value)}
          />
        </label>
        <label className="field">
          <span>End (IST, within 30 days)</span>
          <input
            aria-label="Schedule end (IST)"
            required
            type="datetime-local"
            step="1"
            value={form.end}
            onChange={(e) => update("end", e.target.value)}
          />
        </label>
      </div>
      <div className="field-row">
        <label className="field">
          <span>Maximum launches</span>
          <input
            required
            type="number"
            min={1}
            max={100}
            value={form.launches}
            onChange={(e) => update("launches", e.target.value)}
          />
        </label>
        <label className="field">
          <span>Per-run cap (USD)</span>
          <input
            required
            type="number"
            min={0}
            step="0.000001"
            value={form.runBudget}
            onChange={(e) => update("runBudget", e.target.value)}
          />
        </label>
        <label className="field">
          <span>Total cap (USD)</span>
          <input
            required
            type="number"
            min={0}
            step="0.000001"
            value={form.totalBudget}
            onChange={(e) => update("totalBudget", e.target.value)}
          />
        </label>
      </div>
      <Button type="submit" variant="secondary" busy={action.busy}>
        Preview launches and cost
      </Button>
      {report && (
        <div className="schedule-preview" aria-label="Schedule preview">
          <strong>
            {report.sample_count} samples · {usd(report.estimate_micro)}{" "}
            estimated per launch
          </strong>
          <p>
            Budget covers up to {report.affordable_runs} launches. Times below
            use {form.timezone}.
          </p>
          <ol>
            {report.next_occurrences.map((stamp) => (
              <li key={stamp}>{when(stamp, form.timezone)}</li>
            ))}
          </ol>
          <p>{report.semantics}</p>
          <label className="check-label">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />{" "}
            I approve these scheduled launches within the displayed window,
            launch limit, and budget caps.
          </label>
          <Button
            type="button"
            busy={action.busy}
            disabled={!consent}
            onClick={create}
          >
            Activate schedule
          </Button>
        </div>
      )}
    </form>
  );
}
