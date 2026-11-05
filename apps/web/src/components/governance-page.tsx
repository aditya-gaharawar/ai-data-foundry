"use client";
import { useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import type { Dataset, Page } from "@/lib/api";
import { shortId } from "@/lib/api";
import { useResource, useWorkspace } from "./context";
import {
  Button,
  Code,
  Copy,
  ErrorNotice,
  Modal,
  PageHeader,
  Status,
  useAction,
} from "./ui";

type Policy = {
  number: number;
  sha256: string;
  definition: {
    pii_mode: string;
    allowed_licenses: string[];
    require_human_review: boolean;
    erasure_delay_seconds: number;
    retention_days: number;
  };
};
type Approval = {
  id: string;
  dataset_id: string;
  requested_by: string;
  status: string;
  note: string;
};
type Erasure = {
  id: string;
  dataset_id: string;
  requested_by: string;
  status: string;
  ready_after: string;
  reason: string;
  result: {
    plan_sha256?: string;
    object_versions_planned?: number;
    shared_keys_preserved?: number;
  };
  confirm_dataset_name?: string;
};
type Token = {
  id: string;
  name: string;
  allowed_domain: string;
  revoked: boolean;
  provisioning_token?: string;
};

export function GovernancePage() {
  const { call, organization, session, toast } = useWorkspace();
  const cache = useQueryClient();
  const action = useAction();
  const policy = useResource<Policy>("/governance/policy");
  const datasets = useResource<Page<Dataset>>("/datasets?limit=100");
  const approvals = useResource<Page<Approval>>("/governance/approvals");
  const erasures = useResource<Page<Erasure>>("/governance/erasures", true);
  const canProvision = organization.scopes.includes("members:manage");
  const tokens = useResource<Page<Token>>(
    "/governance/scim-tokens",
    false,
    canProvision,
  );
  const [pii, setPii] = useState("allow");
  const [licenses, setLicenses] = useState("");
  const [review, setReview] = useState(false);
  const [days, setDays] = useState(30);
  const [delay, setDelay] = useState(86400);
  const [datasetId, setDatasetId] = useState("");
  const [note, setNote] = useState("");
  const [decisionNote, setDecisionNote] = useState("");
  const [eraseDataset, setEraseDataset] = useState("");
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<Erasure | null>(null);
  const [confirmName, setConfirmName] = useState("");
  const [tokenName, setTokenName] = useState("");
  const [domain, setDomain] = useState("foundry.local");
  const [secret, setSecret] = useState("");
  const [retention, setRetention] = useState<unknown>(null);
  const selected = datasets.data?.items.find((item) => item.id === datasetId);
  async function mutate<T>(path: string, body: unknown = {}) {
    const result = await action.perform(() =>
      call<T>(path, { method: "POST", body }),
    );
    if (result) cache.invalidateQueries();
    return result;
  }
  return (
    <>
      <PageHeader
        eyebrow="ORGANIZATION / GOVERNANCE"
        title="Decisions with a record"
        description="Immutable policy revisions, protected benchmarks, independent approvals, and controlled artifact erasure."
      />
      <ErrorNotice
        error={
          action.error ||
          policy.error ||
          datasets.error ||
          approvals.error ||
          erasures.error ||
          tokens.error
        }
      />
      <div className="notice">
        <ShieldCheck size={16} />
        Local SCIM supports scoped user provisioning. SSO is blocked without a
        configured identity provider. These controls do not constitute a
        compliance certification.
      </div>
      <div className="two-columns">
        <section className="panel">
          <div className="panel-heading">
            <h2>Organization policy</h2>
            <small>Current revision {policy.data?.number ?? "…"}</small>
          </div>
          <div className="panel-body">
            {policy.data && (
              <details className="evidence-details">
                <summary>Current enforced policy</summary>
                <Code value={policy.data} />
              </details>
            )}
            <Button
              variant="ghost"
              disabled={!policy.data}
              onClick={() => {
                if (policy.data) {
                  const current = policy.data.definition;
                  setPii(current.pii_mode);
                  setLicenses(current.allowed_licenses.join(", "));
                  setReview(current.require_human_review);
                  setDays(current.retention_days);
                  setDelay(current.erasure_delay_seconds);
                }
              }}
            >
              Load current values
            </Button>
            <form
              onSubmit={async (event) => {
                event.preventDefault();
                if (
                  await mutate("/governance/policies", {
                    definition: {
                      pii_mode: pii,
                      allowed_licenses: licenses
                        .split(",")
                        .map((value) => value.trim())
                        .filter(Boolean),
                      require_human_review: review,
                      erasure_delay_seconds: delay,
                      retention_days: days,
                    },
                  })
                )
                  toast("New policy revision enforced.");
              }}
            >
              <label className="field">
                <span>PII handling</span>
                <select
                  aria-label="PII handling"
                  value={pii}
                  onChange={(event) => setPii(event.target.value)}
                >
                  <option value="allow">Measure and allow</option>
                  <option value="block">Block matching data</option>
                  <option value="redact">
                    Redact before review/publication
                  </option>
                </select>
                <small>
                  Native patterns cover email, US SSN, and formatted phone
                  numbers. Review other privacy risks separately.
                </small>
              </label>
              <label className="field">
                <span>Allowed licenses (comma separated)</span>
                <input
                  aria-label="Allowed licenses (comma separated)"
                  value={licenses}
                  onChange={(event) => setLicenses(event.target.value)}
                />
                <small>
                  Empty permits user-declared licenses, subject to dataset
                  rights.
                </small>
              </label>
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={review}
                  onChange={(event) => setReview(event.target.checked)}
                />
                <span>
                  Require frozen human review before training publication
                </span>
              </label>
              <div className="field-row">
                <label className="field">
                  <span>Retention period (days)</span>
                  <input
                    aria-label="Retention period (days)"
                    required
                    type="number"
                    min={1}
                    max={3650}
                    value={days}
                    onChange={(event) => setDays(Number(event.target.value))}
                  />
                </label>
                <label className="field">
                  <span>Erasure delay (seconds)</span>
                  <input
                    aria-label="Erasure delay (seconds)"
                    required
                    type="number"
                    min={0}
                    max={31536000}
                    value={delay}
                    onChange={(event) => setDelay(Number(event.target.value))}
                  />
                </label>
              </div>
              <Button type="submit" busy={action.busy}>
                Save policy revision
              </Button>
            </form>
          </div>
        </section>
        <section className="panel">
          <div className="panel-heading">
            <h2>Dataset protection</h2>
          </div>
          <div className="panel-body">
            <label className="field">
              <span>Dataset to protect</span>
              <select
                aria-label="Dataset to protect"
                value={datasetId}
                onChange={(event) => setDatasetId(event.target.value)}
              >
                <option value="">Select dataset</option>
                {datasets.data?.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            {selected && (
              <p>
                <Status
                  value={
                    selected.protection === "holdout"
                      ? "HOLDOUT_PROTECTED"
                      : "STANDARD"
                  }
                />{" "}
                {selected.legal_hold ? "Legal hold active" : "No legal hold"} ·
                revision {selected.governance_revision}
              </p>
            )}
            <label className="field">
              <span>Protection decision note</span>
              <textarea
                aria-label="Protection decision note"
                maxLength={2000}
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </label>
            <div className="studio-actions">
              {[
                {
                  action: "protect_holdout",
                  label: "Protect as holdout",
                  disabled: selected?.protection === "holdout",
                },
                {
                  action: "place_legal_hold",
                  label: "Place legal hold",
                  disabled: selected?.legal_hold,
                },
                {
                  action: "request_hold_release",
                  label: "Request hold release",
                  disabled: !selected?.legal_hold,
                },
              ].map((item) => (
                <Button
                  key={item.action}
                  variant="secondary"
                  busy={action.busy}
                  disabled={!selected || !note.trim() || item.disabled}
                  onClick={async () => {
                    if (
                      selected &&
                      (await mutate(`/governance/datasets/${selected.id}`, {
                        expected_revision: selected.governance_revision,
                        action: item.action,
                        note,
                      }))
                    )
                      toast("Protection decision saved.");
                  }}
                >
                  {item.label}
                </Button>
              ))}
            </div>
            <p className="muted">
              Holdouts deny training access and exact-hash overlap with new
              publications. This detector does not prove semantic independence.
              Legal hold release requires another administrator.
            </p>
            <Button
              variant="ghost"
              busy={action.busy}
              onClick={async () => {
                const result = await action.perform(() =>
                  call("/governance/retention-plan"),
                );
                if (result) setRetention(result);
              }}
            >
              Inspect retention candidates
            </Button>
            {retention !== null && <Code value={retention} />}
          </div>
        </section>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>Independent approval queue</h2>
        </div>
        <div className="panel-body">
          <label className="field">
            <span>Approval decision note</span>
            <input
              aria-label="Approval decision note"
              value={decisionNote}
              maxLength={2000}
              onChange={(event) => setDecisionNote(event.target.value)}
            />
          </label>
          {approvals.data?.items.map((item) => (
            <div className="record-row" key={item.id}>
              <div>
                <strong>Release legal hold · {shortId(item.dataset_id)}</strong>
                <p>{item.note}</p>
                <Status value={item.status} />
              </div>
              {item.status === "PENDING" &&
                ["approve", "reject"].map((decision) => (
                  <Button
                    key={decision}
                    variant="secondary"
                    busy={action.busy}
                    disabled={
                      !decisionNote.trim() ||
                      item.requested_by === session.user.id
                    }
                    onClick={async () => {
                      if (
                        await mutate(
                          `/governance/approvals/${item.id}/decision`,
                          { decision, note: decisionNote },
                        )
                      )
                        toast("Independent decision recorded.");
                    }}
                  >
                    {decision === "approve"
                      ? "Approve release"
                      : "Reject release"}
                  </Button>
                ))}
            </div>
          ))}
          {!approvals.data?.items.length && (
            <p className="muted">No pending legal hold decisions.</p>
          )}
        </div>
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h2>Artifact erasure</h2>
          <small>
            Independent approval → delay → sealed plan → durable deletion
          </small>
        </div>
        <form
          className="panel-body"
          onSubmit={async (event) => {
            event.preventDefault();
            if (
              await mutate("/governance/erasures", {
                dataset_id: eraseDataset,
                reason,
                trigger: "user_request",
              })
            )
              toast("Erasure request saved for independent approval.");
          }}
        >
          <label className="field">
            <span>Dataset for erasure request</span>
            <select
              aria-label="Dataset for erasure request"
              value={eraseDataset}
              required
              onChange={(event) => setEraseDataset(event.target.value)}
            >
              <option value="">Select dataset</option>
              {datasets.data?.items
                .filter((item) => !item.legal_hold)
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="field">
            <span>Erasure reason</span>
            <textarea
              aria-label="Erasure reason"
              required
              minLength={8}
              maxLength={2000}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <Button type="submit" variant="secondary" busy={action.busy}>
            Request artifact erasure
          </Button>
          <p className="muted">
            A tombstone blocks access before physical deletion. Shared blobs are
            preserved. Immutable audit, manifests, and review metadata remain.
          </p>
        </form>
        <div className="panel-body">
          {erasures.data?.items.map((item) => (
            <div key={item.id} className="record-row">
              <div>
                <strong>
                  {shortId(item.id)} · {shortId(item.dataset_id)}
                </strong>
                <p>{item.reason}</p>
                <Status value={item.status} />
                <small>
                  Ready after{" "}
                  {new Date(item.ready_after).toLocaleString("en-IN", {
                    timeZone: "Asia/Kolkata",
                  })}{" "}
                  IST
                </small>
              </div>
              <div className="studio-actions">
                {item.status === "PENDING_APPROVAL" &&
                  ["approve", "reject"].map((decision) => (
                    <Button
                      variant="secondary"
                      key={decision}
                      disabled={
                        !decisionNote.trim() ||
                        item.requested_by === session.user.id
                      }
                      busy={action.busy}
                      onClick={() =>
                        mutate(`/governance/erasures/${item.id}/decision`, {
                          decision,
                          note: decisionNote,
                        })
                      }
                    >
                      {decision === "approve"
                        ? "Approve erasure"
                        : "Reject erasure"}
                    </Button>
                  ))}
                {item.status === "APPROVED" && (
                  <Button
                    variant="secondary"
                    busy={action.busy}
                    onClick={async () => {
                      const result = await mutate<Erasure>(
                        `/governance/erasures/${item.id}/preview`,
                      );
                      if (result) {
                        setPreview(result);
                        setConfirmName("");
                      }
                    }}
                  >
                    Preview erasure plan
                  </Button>
                )}
                {item.status === "ERASURE_FAILED" && (
                  <Button
                    variant="secondary"
                    busy={action.busy}
                    onClick={() =>
                      mutate(`/governance/erasures/${item.id}/retry`)
                    }
                  >
                    Retry physical erasure
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>
      {canProvision && (
        <section className="panel">
          <div className="panel-heading">
            <h2>SCIM provisioning tokens</h2>
            <small>Core Users subset · domain restricted</small>
          </div>
          <form
            className="panel-body"
            onSubmit={async (event) => {
              event.preventDefault();
              const result = await mutate<Token>("/governance/scim-tokens", {
                name: tokenName,
                allowed_domain: domain,
              });
              if (result?.provisioning_token) {
                setSecret(result.provisioning_token);
                toast("Provisioning token created.");
              }
            }}
          >
            <div className="field-row">
              <label className="field">
                <span>Provisioning token name</span>
                <input
                  aria-label="Provisioning token name"
                  required
                  maxLength={160}
                  value={tokenName}
                  onChange={(event) => setTokenName(event.target.value)}
                />
              </label>
              <label className="field">
                <span>Allowed email domain</span>
                <input
                  aria-label="Allowed email domain"
                  required
                  maxLength={254}
                  value={domain}
                  onChange={(event) => setDomain(event.target.value)}
                />
              </label>
            </div>
            <Button type="submit" variant="secondary" busy={action.busy}>
              Create provisioning token
            </Button>
            <small>
              SCIM endpoint: /v1/scim/v2/Users · Engineer, Labeler, Viewer roles
              only. Updates require If-Match ETags.
            </small>
          </form>
          <div className="panel-body">
            {tokens.data?.items.map((item) => (
              <div className="record-row" key={item.id}>
                <div>
                  <strong>{item.name}</strong>
                  <small>
                    {item.allowed_domain} ·{" "}
                    {item.revoked ? "Revoked" : "Active"}
                  </small>
                </div>
                {!item.revoked && (
                  <Button
                    variant="ghost"
                    busy={action.busy}
                    onClick={() =>
                      mutate(`/governance/scim-tokens/${item.id}/revoke`)
                    }
                  >
                    Revoke
                  </Button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
      <Modal
        open={!!preview}
        setOpen={(open) => {
          if (!open) setPreview(null);
        }}
        title="Review artifact erasure"
        description="Review the sealed plan and type the exact dataset name. Deletion starts only after independent approval and the policy delay."
      >
        {preview && (
          <>
            <dl className="key-values">
              <dt>Dataset name</dt>
              <dd>{preview.confirm_dataset_name}</dd>
              <dt>Object versions to delete</dt>
              <dd>{preview.result.object_versions_planned}</dd>
              <dt>Shared keys preserved</dt>
              <dd>{preview.result.shared_keys_preserved}</dd>
              <dt>Plan SHA-256</dt>
              <dd className="mono">{preview.result.plan_sha256}</dd>
            </dl>
            <label className="field">
              <span>Confirm exact dataset name</span>
              <input
                aria-label="Confirm exact dataset name"
                value={confirmName}
                onChange={(event) => setConfirmName(event.target.value)}
              />
            </label>
            <ErrorNotice error={action.error} />
            <Button
              variant="danger"
              disabled={
                confirmName !== preview.confirm_dataset_name ||
                Date.parse(preview.ready_after) > Date.now()
              }
              busy={action.busy}
              onClick={async () => {
                if (
                  await mutate(`/governance/erasures/${preview.id}/execute`, {
                    confirm_dataset_name: confirmName,
                    plan_sha256: preview.result.plan_sha256,
                  })
                ) {
                  setPreview(null);
                  toast("Artifact erasure queued; dataset access is blocked.");
                }
              }}
            >
              Start artifact erasure
            </Button>
          </>
        )}
      </Modal>
      <Modal
        open={!!secret}
        setOpen={(open) => {
          if (!open) setSecret("");
        }}
        title="Save provisioning credential"
        description="This token is shown once. Store it privately with your provisioning client."
      >
        <div className="secret-box">
          <code>{secret}</code>
          <Copy value={secret} />
        </div>
        <Button onClick={() => setSecret("")}>I saved the credential</Button>
      </Modal>
    </>
  );
}
