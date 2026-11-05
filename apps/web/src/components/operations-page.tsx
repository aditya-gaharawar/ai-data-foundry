"use client";
import { useQueryClient } from "@tanstack/react-query";
import { useWorkspace, useResource } from "./context";
import type { Page } from "@/lib/api";
import { shortId } from "@/lib/api";
import { Button, Code, ErrorNotice, PageHeader, Status, useAction } from "./ui";

type Gate = { gate: string; state: string; reason?: string; proof_id?: string };
type Readiness = {
  status: string;
  source_sha256: string;
  checks: Gate[];
  release_gates: Gate[];
  scope: string;
};
type Report = {
  id: string;
  created_at: string;
  report: Record<string, unknown>;
};
type Incident = {
  id: string;
  source_ref: string;
  summary: string;
  status: string;
};
type Proof = {
  id: string;
  kind: string;
  source_sha256: string;
  report: { status: string; recorded_at: string; limits?: string };
};

export function OperationsPage() {
  const { call, toast } = useWorkspace();
  const action = useAction();
  const cache = useQueryClient();
  const status = useResource<{
    environment: string;
    source_sha256: string;
    readiness: Readiness;
  }>("/operations/status");
  const incidents = useResource<Page<Incident>>("/operations/incidents");
  const ledgers = useResource<Page<Report>>("/operations/reconciliations");
  const proofs = useResource<Page<Proof>>("/operations/proofs");
  const readiness = useResource<Page<Report>>("/operations/readiness");
  async function mutate(path: string, message: string) {
    const result = await action.perform(() =>
      call(path, { method: "POST", body: {} }),
    );
    if (result) {
      cache.invalidateQueries();
      toast(message);
    }
  }
  return (
    <>
      <PageHeader
        eyebrow="OPERATE / LOCAL READINESS"
        title="Know what is proven"
        description="Persisted ledger checks, actual failure signals, and signed evidence tied to the current source."
      />
      <ErrorNotice
        error={
          action.error ||
          status.error ||
          incidents.error ||
          ledgers.error ||
          proofs.error ||
          readiness.error
        }
      />
      <div className="notice">
        This environment uses local authentication and synthetic fixtures.
        Production release remains blocked by staging, identity, infrastructure,
        review, and independent security gates.
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>Readiness gates</h2>
          {status.data && <Status value={status.data.readiness.status} />}
        </div>
        <div className="panel-body">
          <small className="mono">
            Source SHA-256: {status.data?.source_sha256 || "Loading…"}
          </small>
          {status.data?.readiness.checks.map((gate) => (
            <div className="record-row" key={gate.gate}>
              <strong>{gate.gate.replaceAll("_", " ")}</strong>
              <Status value={gate.state} />
            </div>
          ))}
          {status.data?.readiness.release_gates.map((gate) => (
            <div className="record-row" key={gate.gate}>
              <div>
                <strong>{gate.gate.replaceAll("_", " ")}</strong>
                <small>{gate.reason}</small>
              </div>
              <Status value={gate.state} />
            </div>
          ))}
          <Button
            busy={action.busy}
            onClick={() =>
              mutate(
                "/operations/readiness",
                "Signed local readiness report saved.",
              )
            }
          >
            Sign current readiness report
          </Button>
        </div>
      </section>
      <div className="two-columns">
        <section className="panel">
          <div className="panel-heading">
            <h2>Ledger reconciliation</h2>
            <Button
              variant="secondary"
              busy={action.busy}
              onClick={() =>
                mutate(
                  "/operations/reconciliations",
                  "Ledger reconciliation recorded.",
                )
              }
            >
              Reconcile ledger
            </Button>
          </div>
          <div className="panel-body">
            <p className="muted">
              Compares immutable usage events with per-run and organization
              balances. Discrepancies are recorded without editing money. All
              local usage is nonbillable.
            </p>
            {ledgers.data?.items.slice(0, 10).map((item) => (
              <details className="evidence-details" key={item.id}>
                <summary>
                  <Status value={String(item.report.status)} />{" "}
                  {new Date(item.created_at).toLocaleString("en-IN", {
                    timeZone: "Asia/Kolkata",
                  })}{" "}
                  IST
                </summary>
                <Code value={item.report} />
              </details>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panel-heading">
            <h2>Incident signals</h2>
            <Button
              variant="secondary"
              busy={action.busy}
              onClick={() =>
                mutate(
                  "/operations/incidents/scan",
                  "Actual failure signals scanned.",
                )
              }
            >
              Scan incidents
            </Button>
          </div>
          <div className="panel-body">
            {incidents.data?.items.map((item) => (
              <div className="record-row" key={item.id}>
                <div>
                  <strong>{shortId(item.source_ref)}</strong>
                  <p>{item.summary}</p>
                  <Status value={item.status} />
                </div>
                {item.status === "OPEN" && (
                  <Button
                    variant="ghost"
                    busy={action.busy}
                    onClick={() =>
                      mutate(
                        `/operations/incidents/${item.id}/acknowledge`,
                        "Incident acknowledged.",
                      )
                    }
                  >
                    Acknowledge
                  </Button>
                )}
              </div>
            ))}
            {!incidents.data?.items.length && (
              <p className="muted">
                Scan failed runs and disconnected agents to create deduplicated
                incident records.
              </p>
            )}
          </div>
        </section>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>Operator evidence</h2>
          <small>
            Local HMAC attestation · expires for readiness after 24 hours or
            source change
          </small>
        </div>
        <div className="panel-body">
          <p>
            Run recovery and bounded load checks from the local operator
            environment. Signed reports are imported automatically; private
            backups remain outside the source bundle.
          </p>
          <Code
            value={
              "uv run python scripts/operational_checks.py restore\nuv run python scripts/operational_checks.py load"
            }
          />
          {proofs.data?.items.map((item) => (
            <details className="evidence-details" key={item.id}>
              <summary>
                <Status value={item.report.status} /> {item.kind} ·{" "}
                {shortId(item.source_sha256)}
                {item.source_sha256 !== status.data?.source_sha256
                  ? " · prior source"
                  : " · current source"}
              </summary>
              <Code value={item.report} />
            </details>
          ))}
        </div>
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h2>Saved readiness reports</h2>
        </div>
        <div className="panel-body">
          {readiness.data?.items.slice(0, 10).map((item) => (
            <details className="evidence-details" key={item.id}>
              <summary>
                {new Date(item.created_at).toLocaleString("en-IN", {
                  timeZone: "Asia/Kolkata",
                })}{" "}
                IST · {String(item.report.status)}
              </summary>
              <Code value={item.report} />
            </details>
          ))}
          {!readiness.data?.items.length && (
            <p className="muted">
              Sign a current report to retain its release gates and operator
              attestation.
            </p>
          )}
        </div>
      </section>
    </>
  );
}
