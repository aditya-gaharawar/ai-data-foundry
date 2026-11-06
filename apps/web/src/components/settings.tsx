"use client";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowRight,
  BookOpen,
  Code2,
  Info,
  KeyRound,
  Plus,
  RefreshCw,
  ShieldCheck,
  Users,
  Webhook,
} from "lucide-react";
import { useState } from "react";
import type { Delivery, Hook, Key, Member, Page, Usage } from "@/lib/api";
import { date, money, shortId } from "@/lib/api";
import { useResource, useWorkspace } from "./context";
import {
  Button,
  Code,
  Copy,
  Empty,
  ErrorNotice,
  Loading,
  Modal,
  PageHeader,
  Status,
  useAction,
} from "./ui";

const scopes = [
  "datasets:read",
  "datasets:write",
  "runs:execute",
  "keys:manage",
  "members:manage",
  "webhooks:manage",
  "audit:read",
  "budgets:manage",
  "annotations:manage",
  "annotations:review",
  "annotations:adjudicate",
  "schedules:manage",
  "notifications:read",
];
export function KeysPage() {
  const query = useResource<Page<Key>>("/api-keys");
  const { call, organization, toast } = useWorkspace();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState([
    "datasets:read",
    "datasets:write",
    "runs:execute",
  ]);
  const [secret, setSecret] = useState("");
  const [revoke, setRevoke] = useState<Key | null>(null);
  const action = useAction();
  return (
    <>
      <PageHeader
        title="API keys"
        description="Connect your tools with scoped, revocable credentials."
      >
        <Button
          onClick={() => {
            setSecret("");
            setOpen(true);
          }}
        >
          <Plus size={14} />
          Create API key
        </Button>
      </PageHeader>
      <div className="notice">
        <ShieldCheck size={15} />
        <span>
          Key secrets are revealed once. Store them securely and grant only the
          permissions your integration needs.
        </span>
      </div>
      <ErrorNotice error={query.error || (!open && action.error)} />
      {query.isPending ? (
        <Loading />
      ) : !query.data?.items.length ? (
        <div className="panel">
          <Empty
            icon={KeyRound}
            title="Your workflow, from anywhere"
            description="Create an API key to work with datasets and runs through the SDK or CLI."
            action={
              <Button variant="secondary" onClick={() => setOpen(true)}>
                <Plus size={13} />
                Create your first key
              </Button>
            }
          />
        </div>
      ) : (
        <div
          className="table-wrap"
          role="region"
          aria-label="API keys table"
          tabIndex={0}
        >
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Key prefix</th>
                <th>Permissions</th>
                <th>Status</th>
                <th>Created</th>
                <th>
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((key) => (
                <tr key={key.id}>
                  <td>
                    <div className="cell-title">
                      <KeyRound size={14} />
                      {key.name}
                    </div>
                  </td>
                  <td className="mono muted">{key.prefix}…</td>
                  <td>
                    <span className="muted" style={{ fontSize: 11 }}>
                      {key.scopes.length} scopes
                    </span>
                  </td>
                  <td>
                    <Status value={key.revoked ? "REVOKED" : "READY"} />
                  </td>
                  <td className="muted">{date(key.created_at)}</td>
                  <td>
                    {!key.revoked && (
                      <Button variant="ghost" onClick={() => setRevoke(key)}>
                        Revoke
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <section className="panel" style={{ marginTop: 26 }}>
        <div className="panel-heading">
          <h2>Make your first API request</h2>
          <Code2 size={14} className="muted" />
        </div>
        <Code
          value={
            'from datafoundry import DataFoundry\n\nclient = DataFoundry(\n    base_url="http://localhost:8000",\n    api_key="YOUR_API_KEY",\n)\n\nfor dataset in client.datasets.list():\n    print(dataset.name)'
          }
        />
      </section>
      <Modal
        open={open}
        setOpen={(value) => {
          setOpen(value);
          if (!value) setSecret("");
        }}
        title={secret ? "Save your API key" : "Create API key"}
        description={
          secret
            ? "This secret will not be shown again."
            : "Use a descriptive name and select the required permissions."
        }
      >
        {secret ? (
          <>
            <div className="secret">
              <p>Copy this key to your secure credential store.</p>
              <Copy value={secret} label="Copy new API key" />
              <code>{secret}</code>
            </div>
            <div className="modal-actions">
              <Button
                onClick={() => {
                  setOpen(false);
                  setSecret("");
                }}
              >
                I saved my key
              </Button>
            </div>
          </>
        ) : (
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              const key = await action.perform(() =>
                call<Key>("/api-keys", {
                  method: "POST",
                  body: { name, scopes: selected },
                }),
              );
              if (key) {
                setSecret(key.secret || "");
                setName("");
                client.invalidateQueries();
                toast("API key created.");
              }
            }}
          >
            <label className="field">
              <span>Key name</span>
              <input
                required
                value={name}
                maxLength={160}
                placeholder="e.g. Training pipeline"
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <p style={{ fontSize: 12, marginBottom: 10 }}>Permissions</p>
            <div className="scope-grid">
              {scopes
                .filter((scope) => organization.scopes.includes(scope))
                .map((scope) => (
                  <label key={scope}>
                    <input
                      type="checkbox"
                      checked={selected.includes(scope)}
                      onChange={(event) =>
                        setSelected(
                          event.target.checked
                            ? [...selected, scope]
                            : selected.filter((value) => value !== scope),
                        )
                      }
                    />
                    <span className="mono" style={{ fontSize: 10 }}>
                      {scope}
                    </span>
                  </label>
                ))}
            </div>
            <ErrorNotice error={action.error} />
            <div className="modal-actions">
              <Button
                variant="secondary"
                type="button"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button busy={action.busy} disabled={!selected.length}>
                Create key
              </Button>
            </div>
          </form>
        )}
      </Modal>
      <Modal
        open={!!revoke}
        setOpen={() => setRevoke(null)}
        title="Revoke API key?"
        description={`Requests using ${revoke?.name || "this key"} will stop working immediately.`}
      >
        <ErrorNotice error={action.error} />
        <div className="modal-actions">
          <Button variant="secondary" onClick={() => setRevoke(null)}>
            Keep key
          </Button>
          <Button
            variant="danger"
            busy={action.busy}
            onClick={() =>
              action.perform(async () => {
                await call(`/api-keys/${revoke?.id}`, { method: "DELETE" });
                setRevoke(null);
                client.invalidateQueries();
                toast("API key revoked.");
              })
            }
          >
            Revoke key
          </Button>
        </div>
      </Modal>
    </>
  );
}

export function WebhooksPage() {
  const query = useResource<Page<Hook>>("/webhooks");
  const deliveries = useResource<Page<Delivery>>(
    "/webhook-deliveries?limit=25",
    true,
  );
  const { call, toast } = useWorkspace();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("http://localhost:9100/events");
  const [secret, setSecret] = useState("");
  const action = useAction();
  return (
    <>
      <PageHeader
        title="Webhooks"
        description="Bring dataset and run events into your own workflow."
      >
        <Button
          onClick={() => {
            setSecret("");
            setOpen(true);
          }}
        >
          <Plus size={14} />
          Add endpoint
        </Button>
      </PageHeader>
      <div className="notice">
        <Info size={15} />
        <span>
          Local mode delivers to configured local receivers. Events are signed,
          retried, and delivered at least once.
        </span>
      </div>
      <ErrorNotice
        error={query.error || deliveries.error || (!open && action.error)}
      />
      <div className="panel">
        {!query.data?.items.length ? (
          <Empty
            icon={Webhook}
            title="Keep your tools in the loop"
            description="Subscribe to publication and run events with a signed webhook endpoint."
          />
        ) : (
          query.data.items.map((hook) => (
            <div className="sample-row" key={hook.id}>
              <div className="section-row">
                <div>
                  <h3 className="mono" style={{ overflowWrap: "anywhere" }}>
                    {hook.url}
                  </h3>
                  <small>{hook.events.join(", ")}</small>
                </div>
                <Status value={hook.active ? "READY" : "DISABLED"} />
              </div>
              {hook.active && (
                <div style={{ display: "flex", gap: 8 }}>
                  <Button
                    variant="secondary"
                    busy={action.busy}
                    onClick={() =>
                      action.perform(async () => {
                        const result = await call<{ signing_secret: string }>(
                          `/webhooks/${hook.id}/rotate`,
                          { method: "POST" },
                        );
                        setSecret(result.signing_secret);
                        setOpen(true);
                        toast("Signing secret rotated.");
                      })
                    }
                  >
                    <RefreshCw size={12} />
                    Rotate secret
                  </Button>
                  <Button
                    variant="ghost"
                    busy={action.busy}
                    onClick={() =>
                      action.perform(async () => {
                        await call(`/webhooks/${hook.id}`, {
                          method: "DELETE",
                        });
                        client.invalidateQueries();
                        toast("Webhook disabled.");
                      })
                    }
                  >
                    Disable endpoint
                  </Button>
                </div>
              )}
            </div>
          ))
        )}
      </div>
      <section style={{ marginTop: 28 }}>
        <div className="section-row">
          <h2>Delivery history</h2>
          <span className="muted" style={{ fontSize: 11 }}>
            Retries are automatic
          </span>
        </div>
        {!deliveries.data?.items.length ? (
          <div className="panel">
            <Empty
              icon={Webhook}
              title="No deliveries yet"
              description="Subscribed events appear here after a run or export."
            />
          </div>
        ) : (
          <div
            className="table-wrap"
            role="region"
            aria-label="Webhook deliveries"
            tabIndex={0}
          >
            <table>
              <thead>
                <tr>
                  <th>Delivery</th>
                  <th>Status</th>
                  <th>Attempts</th>
                  <th>HTTP</th>
                  <th>
                    <span className="sr-only">Replay</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {deliveries.data.items.map((delivery) => (
                  <tr key={delivery.id}>
                    <td className="mono">
                      {shortId(delivery.id)}
                      {delivery.error && (
                        <div className="cell-subtitle">{delivery.error}</div>
                      )}
                    </td>
                    <td>
                      <Status value={delivery.status} />
                    </td>
                    <td className="mono">{delivery.attempts}</td>
                    <td className="mono">{delivery.last_status || "—"}</td>
                    <td>
                      <Button
                        variant="ghost"
                        busy={action.busy}
                        onClick={() =>
                          action.perform(async () => {
                            await call(
                              `/webhook-deliveries/${delivery.id}/replay`,
                              { method: "POST" },
                            );
                            client.invalidateQueries();
                            toast("Delivery scheduled for replay.");
                          })
                        }
                      >
                        <RefreshCw size={12} />
                        Replay
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <Modal
        open={open}
        setOpen={(value) => {
          setOpen(value);
          if (!value) setSecret("");
        }}
        title={secret ? "Save your signing secret" : "Add a webhook endpoint"}
        description={
          secret
            ? "Verify signatures over the exact raw request bytes."
            : "Subscribe to successful runs, published versions, and exports."
        }
      >
        {secret ? (
          <>
            <div className="secret">
              <p>Only available now. Save it securely.</p>
              <Copy value={secret} label="Copy webhook signing secret" />
              <code>{secret}</code>
            </div>
            <div className="modal-actions">
              <Button
                onClick={() => {
                  setOpen(false);
                  setSecret("");
                }}
              >
                I saved my secret
              </Button>
            </div>
          </>
        ) : (
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              const hook = await action.perform(() =>
                call<Hook>("/webhooks", {
                  method: "POST",
                  body: {
                    url,
                    events: [
                      "run.succeeded",
                      "dataset.version.published",
                      "export.ready",
                    ],
                  },
                }),
              );
              if (hook) {
                setSecret(hook.signing_secret || "");
                client.invalidateQueries();
                toast("Webhook endpoint created.");
              }
            }}
          >
            <label className="field">
              <span>Endpoint URL</span>
              <input
                type="url"
                required
                value={url}
                onChange={(event) => setUrl(event.target.value)}
              />
            </label>
            <div className="notice">
              <ShieldCheck size={14} />
              Subscribed events: run succeeded, version published, export ready.
            </div>
            <ErrorNotice error={action.error} />
            <div className="modal-actions">
              <Button
                variant="secondary"
                type="button"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button busy={action.busy}>Add endpoint</Button>
            </div>
          </form>
        )}
      </Modal>
    </>
  );
}

export function MembersPage() {
  const query = useResource<Page<Member>>("/members");
  const { call, session, toast } = useWorkspace();
  const client = useQueryClient();
  const action = useAction();
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("Engineer");
  const [remove, setRemove] = useState<Member | null>(null);
  return (
    <>
      <PageHeader
        title="Members"
        description="The right people. The right permissions."
      >
        <Button onClick={() => setOpen(true)}>
          <Plus size={14} />
          Add member
        </Button>
      </PageHeader>
      <ErrorNotice error={query.error || (!open && action.error)} />
      {query.isPending ? (
        <Loading />
      ) : (
        <div
          className="table-wrap"
          role="region"
          aria-label="Organization members"
          tabIndex={0}
        >
          <table>
            <thead>
              <tr>
                <th>Member</th>
                <th>Role</th>
                <th>
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {query.data?.items.map((member) => (
                <tr key={member.id}>
                  <td>
                    <div className="cell-title">
                      <span className="avatar">
                        {member.name.slice(0, 2).toUpperCase()}
                      </span>
                      <div>
                        {member.name}
                        {member.id === session.user.id && (
                          <span
                            className="muted"
                            style={{ fontSize: 10, marginLeft: 8 }}
                          >
                            You
                          </span>
                        )}
                        <div className="cell-subtitle">{member.email}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    {member.role === "Owner" ||
                    member.id === session.user.id ? (
                      <span className="status">{member.role}</span>
                    ) : (
                      <select
                        className="form-input"
                        aria-label={`Role for ${member.name}`}
                        value={member.role}
                        onChange={(event) =>
                          action.perform(async () => {
                            await call(`/members/${member.id}`, {
                              method: "PATCH",
                              body: { role: event.target.value },
                            });
                            client.invalidateQueries();
                            toast("Member role updated.");
                          })
                        }
                      >
                        {["Admin", "Engineer", "Labeler", "Viewer"].map(
                          (value) => (
                            <option key={value}>{value}</option>
                          ),
                        )}
                      </select>
                    )}
                  </td>
                  <td>
                    {member.role !== "Owner" &&
                      member.id !== session.user.id && (
                        <Button
                          variant="ghost"
                          onClick={() => setRemove(member)}
                        >
                          Remove
                        </Button>
                      )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="notice" style={{ marginTop: 24 }}>
        <Info size={15} />
        <span>
          Local accounts are managed within this organization. Production
          identity integration is a later milestone.
        </span>
      </div>
      <Modal
        open={open}
        setOpen={setOpen}
        title="Add a workspace member"
        description="Provision a local account and assign its organization role."
      >
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            const result = await action.perform(() =>
              call("/members", {
                method: "POST",
                body: { email, name, password, role },
              }),
            );
            if (result) {
              setOpen(false);
              setEmail("");
              setName("");
              setPassword("");
              client.invalidateQueries();
              toast("Member account created.");
            }
          }}
        >
          <label className="field">
            <span>Full name</span>
            <input
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Email address</span>
            <input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Initial password</span>
            <input
              type="password"
              autoComplete="new-password"
              minLength={12}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <small>
              At least 12 characters. Share it through your secure channel.
            </small>
          </label>
          <label className="field">
            <span>Role</span>
            <select
              value={role}
              onChange={(event) => setRole(event.target.value)}
            >
              {["Engineer", "Labeler", "Viewer", "Admin"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <ErrorNotice error={action.error} />
          <div className="modal-actions">
            <Button
              variant="secondary"
              type="button"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button busy={action.busy}>Add member</Button>
          </div>
        </form>
      </Modal>
      <Modal
        open={!!remove}
        setOpen={() => setRemove(null)}
        title="Remove member?"
        description={`Remove ${remove?.name || "this member"}'s access to this organization.`}
      >
        <ErrorNotice error={action.error} />
        <div className="modal-actions">
          <Button variant="secondary" onClick={() => setRemove(null)}>
            Keep member
          </Button>
          <Button
            variant="danger"
            busy={action.busy}
            onClick={() =>
              action.perform(async () => {
                await call(`/members/${remove?.id}`, { method: "DELETE" });
                setRemove(null);
                client.invalidateQueries();
                toast("Member access removed.");
              })
            }
          >
            Remove member
          </Button>
        </div>
      </Modal>
    </>
  );
}

export function UsagePage() {
  const query = useResource<Usage>("/usage", true);
  const { call, organization, toast } = useWorkspace();
  const client = useQueryClient();
  const action = useAction();
  const [open, setOpen] = useState(false);
  const [maximum, setMaximum] = useState(100);
  const data = query.data;
  if (query.isPending) return <Loading />;
  if (!data) return <ErrorNotice error={query.error} />;
  return (
    <>
      <PageHeader
        title="Usage & budgets"
        description="Every sample accounted for. Every run within its limits."
      >
        {organization.scopes.includes("budgets:manage") && (
          <Button
            variant="secondary"
            onClick={() => {
              setMaximum(data.budget_usd);
              setOpen(true);
            }}
          >
            Edit budget
          </Button>
        )}
      </PageHeader>
      <div className="notice">
        <Info size={15} />
        <span>
          This workspace is unbilled. Internal estimates use your local rate
          card; actual external charges are $0.
        </span>
      </div>
      <div className="stats">
        {[
          { label: "Internal usage", value: money(data.internal_spent_usd) },
          { label: "Reserved", value: money(data.reserved_usd) },
          { label: "External charges", value: money(data.external_cost_usd) },
          { label: "Organization cap", value: money(data.budget_usd) },
        ].map((value) => (
          <div className="stat" key={value.label}>
            <div className="stat-title">{value.label}</div>
            <div className="stat-number">{value.value}</div>
            <div className="stat-note">Nonbillable local workspace</div>
          </div>
        ))}
      </div>
      <div className="panel">
        <div className="panel-heading">
          <h2>Budget utilization</h2>
          <span className="mono muted">
            {money(data.internal_spent_usd + data.reserved_usd)} /{" "}
            {money(data.budget_usd)}
          </span>
        </div>
        <div className="panel-body">
          <div className="progress-track">
            <div
              className="budget-fill"
              style={{
                width: `${data.budget_usd ? Math.min(100, ((data.internal_spent_usd + data.reserved_usd) / data.budget_usd) * 100) : 0}%`,
              }}
            />
          </div>
          <small>
            Spend is reserved before scheduling and reconciled at durable
            checkpoints.
          </small>
        </div>
      </div>
      <div className="section-row" style={{ marginTop: 28 }}>
        <h2>Measured activity</h2>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Meter</th>
              <th>Quantity</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(data.meters).map(([key, value]) => (
              <tr key={key}>
                <td>{key.replaceAll("_", " ")}</td>
                <td className="mono">{value.toLocaleString()}</td>
              </tr>
            ))}
            {!Object.keys(data.meters).length && (
              <tr>
                <td colSpan={2} className="muted">
                  No activity recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <Modal
        open={open}
        setOpen={setOpen}
        title="Organization budget"
        description="Set a hard cap for internal local usage estimates."
      >
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            const result = await action.perform(() =>
              call("/budgets", {
                method: "PATCH",
                body: { maximum_usd: maximum },
              }),
            );
            if (result) {
              setOpen(false);
              client.invalidateQueries();
              toast("Organization budget saved.");
            }
          }}
        >
          <label className="field">
            <span>Maximum internal usage (USD)</span>
            <input
              type="number"
              min={0}
              step="0.001"
              required
              value={maximum}
              onChange={(event) => setMaximum(Number(event.target.value))}
            />
          </label>
          <ErrorNotice error={action.error} />
          <div className="modal-actions">
            <Button
              variant="secondary"
              type="button"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button busy={action.busy}>Save budget</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

export function AuditPage() {
  const [cursor, setCursor] = useState<string | null>(null);
  const query = useResource<
    Page<{
      id: string;
      action: string;
      actor_id: string;
      resource_id: string;
      request_id: string;
      created_at: string;
    }>
  >(
    `/audit-events?limit=25${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
  );
  return (
    <>
      <PageHeader
        title="Audit log"
        description="An append-only record of changes in your organization."
      />
      <ErrorNotice error={query.error} />
      {query.isPending ? (
        <Loading />
      ) : (
        <>
          <div
            className="table-wrap"
            role="region"
            aria-label="Audit events"
            tabIndex={0}
          >
            <table>
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Actor</th>
                  <th>Resource</th>
                  <th>Date</th>
                  <th>
                    <span className="sr-only">Copy request ID</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {query.data?.items.map((event) => (
                  <tr key={event.id}>
                    <td>{event.action.replaceAll(".", " · ")}</td>
                    <td className="mono muted">{shortId(event.actor_id)}</td>
                    <td className="mono muted">{shortId(event.resource_id)}</td>
                    <td className="muted">{date(event.created_at)}</td>
                    <td>
                      <Copy
                        value={event.request_id}
                        label="Copy audit request ID"
                      />
                    </td>
                  </tr>
                ))}
                {!query.data?.items.length && (
                  <tr>
                    <td colSpan={5}>No audit events yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="table-end">
            <span>{query.data?.items.length || 0} events on this page</span>
            <div>
              {cursor && (
                <Button variant="ghost" onClick={() => setCursor(null)}>
                  First page
                </Button>
              )}
              {query.data?.next_cursor && (
                <Button
                  variant="secondary"
                  onClick={() => setCursor(query.data?.next_cursor || null)}
                >
                  Next page <ArrowRight size={12} />
                </Button>
              )}
            </div>
          </div>
        </>
      )}
    </>
  );
}

type OpenAPI = {
  info: { title: string; version: string };
  paths: Record<
    string,
    Record<string, { summary?: string; operationId?: string }>
  >;
};
export function ApiDocsPage() {
  const query = useResource<OpenAPI>("/openapi.json");
  const [language, setLanguage] = useState("Python");
  const snippets: Record<string, string> = {
    Python:
      'from datafoundry import DataFoundry\n\nwith DataFoundry(base_url="http://localhost:8000", api_key="YOUR_API_KEY") as client:\n    for dataset in client.datasets.list():\n        print(dataset.id, dataset.name)',
    TypeScript:
      'import { DataFoundry } from "@datafoundry/sdk";\n\nconst client = new DataFoundry({\n  baseUrl: "http://localhost:8000",\n  apiKey: "YOUR_API_KEY",\n});\nconst datasets = await client.datasets.list();\nconsole.log(datasets.items);',
    CLI: 'export FOUNDRY_API_KEY="YOUR_API_KEY"\ndatafoundry doctor\ndatafoundry datasets list\ndatafoundry runs watch RUN_ID',
  };
  return (
    <>
      <PageHeader
        title="Developer reference"
        description="The same platform, from your terminal or application."
      >
        <Button
          variant="secondary"
          disabled={!query.data}
          onClick={() => {
            const url = URL.createObjectURL(
              new Blob([JSON.stringify(query.data, null, 2)], {
                type: "application/json",
              }),
            );
            const a = document.createElement("a");
            a.href = url;
            a.download = "datafoundry-openapi.json";
            a.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          }}
        >
          <ArrowDownToLine size={13} />
          OpenAPI 3.1
        </Button>
      </PageHeader>
      <div className="panel">
        <div className="panel-heading">
          <h2>Start building</h2>
          <BookOpen size={14} className="muted" />
        </div>
        <div className="panel-body">
          <p className="muted" style={{ fontSize: 12, marginBottom: 16 }}>
            Use a scoped API key from your workspace. Clients are
            workspace-local packages in this milestone.
          </p>
          <div className="tabs" role="tablist" aria-label="SDK language">
            {["Python", "TypeScript", "CLI"].map((value) => (
              <button
                key={value}
                role="tab"
                aria-selected={language === value}
                className={`tab ${language === value ? "active" : ""}`}
                onClick={() => setLanguage(value)}
              >
                {value}
              </button>
            ))}
          </div>
          <Code value={snippets[language]} />
        </div>
      </div>
      <section style={{ marginTop: 30 }}>
        <div className="section-row">
          <h2>API endpoints</h2>
          <span className="mono muted">/v1 · {query.data?.info.version}</span>
        </div>
        <ErrorNotice error={query.error} />
        <div className="panel">
          {Object.entries(query.data?.paths || {}).map(([path, operations]) =>
            Object.entries(operations)
              .filter(([method]) =>
                ["get", "post", "patch", "delete"].includes(method),
              )
              .map(([method, operation]) => (
                <div className="api-route" key={method + path}>
                  <span>{method.toUpperCase()}</span>
                  <code>{path}</code>
                  <small>{operation.summary}</small>
                </div>
              )),
          )}
        </div>
      </section>
    </>
  );
}
