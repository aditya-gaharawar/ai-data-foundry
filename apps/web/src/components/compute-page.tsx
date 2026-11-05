"use client";
import { useQueryClient } from "@tanstack/react-query";
import { Cpu, Plus, Server } from "lucide-react";
import { useState } from "react";
import type { Dataset, Page, Version } from "@/lib/api";
import { shortId } from "@/lib/api";
import { useResource, useWorkspace } from "./context";
import {
  Button,
  Code,
  Copy,
  Empty,
  ErrorNotice,
  Modal,
  PageHeader,
  Status,
  useAction,
} from "./ui";

type Pool = {
  id: string;
  name: string;
  scheduler: string;
  state: string;
  active_agents: number;
  reason: string;
  capabilities: { cpu_cores: number; memory_gib: number };
};
type Agent = {
  id: string;
  name: string;
  pool_id: string;
  revoked: boolean;
  seen_at: string | null;
  agent_token?: string;
};
type Job = {
  id: string;
  pool_id: string;
  version_id: string;
  status: string;
  attempt: number;
  result: Record<string, unknown>;
  error: string | null;
};

export function ComputePage() {
  const { call, organization, toast } = useWorkspace();
  const cache = useQueryClient();
  const action = useAction();
  const pools = useResource<Page<Pool>>(
    "/compute/registered-pools?limit=100",
    true,
  );
  const agents = useResource<Page<Agent>>("/compute/agents?limit=100", true);
  const jobs = useResource<Page<Job>>("/compute/jobs?limit=100", true);
  const datasets = useResource<Page<Dataset>>("/datasets?limit=100");
  const [poolId, setPoolId] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const versions = useResource<Page<Version>>(
    `/datasets/${datasetId || "none"}/versions`,
    false,
    !!datasetId,
  );
  const [versionId, setVersionId] = useState("");
  const [poolOpen, setPoolOpen] = useState(false);
  const [name, setName] = useState("");
  const [scheduler, setScheduler] = useState("agent");
  const [cores, setCores] = useState(2);
  const [memory, setMemory] = useState(2);
  const [agentName, setAgentName] = useState("");
  const [secret, setSecret] = useState("");
  const [placement, setPlacement] = useState<unknown>(null);
  const canManage = organization.scopes.includes("compute:manage");
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
        eyebrow="INFRASTRUCTURE / COMPUTE"
        title="Your compute, connected"
        description="Outbound worker identities, explicit capabilities, and fenced leases for immutable artifact verification."
      >
        {canManage && (
          <Button onClick={() => setPoolOpen(true)}>
            <Plus size={14} />
            Register pool
          </Button>
        )}
      </PageHeader>
      <ErrorNotice
        error={action.error || pools.error || agents.error || jobs.error}
      />
      <div className="notice">
        The built-in dataset worker runs generation and Blender locally.
        Enrolled agents execute the fixed artifact verification operator.
        Kubernetes/Kueue, Slurm, and RTX Isaac execution require an approved
        external environment.
      </div>
      <div className="capability-grid">
        {pools.data?.items.map((pool) => (
          <div className="panel capability-card" key={pool.id}>
            <div className="section-row">
              <Server size={17} />
              <Status value={pool.state} />
            </div>
            <h2>{pool.name}</h2>
            <p>
              {pool.capabilities.cpu_cores} CPU · {pool.capabilities.memory_gib}{" "}
              GiB · {pool.scheduler}
            </p>
            <p>{pool.active_agents} active agents</p>
            <small>{pool.reason}</small>
          </div>
        ))}
      </div>
      {!pools.data?.items.length && (
        <section className="panel">
          <Empty
            icon={Cpu}
            title="No enrolled compute pools"
            description="Register a local outbound-agent pool to verify real dataset artifacts."
          />
        </section>
      )}
      <div className="two-columns">
        <section className="panel">
          <div className="panel-heading">
            <h2>Verify an artifact</h2>
          </div>
          <form
            className="panel-body"
            onSubmit={async (event) => {
              event.preventDefault();
              const result = await mutate<Job>("/compute/jobs", {
                pool_id: poolId,
                version_id: versionId,
              });
              if (result) toast("Artifact verification queued.");
            }}
          >
            <label className="field">
              <span>Compute pool</span>
              <select
                aria-label="Compute pool"
                required
                value={poolId}
                onChange={(event) => {
                  setPoolId(event.target.value);
                  setPlacement(null);
                }}
              >
                <option value="">Select pool</option>
                {pools.data?.items.map((pool) => (
                  <option value={pool.id} key={pool.id}>
                    {pool.name} · {pool.state}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Dataset to verify</span>
              <select
                aria-label="Dataset to verify"
                required
                value={datasetId}
                onChange={(event) => {
                  setDatasetId(event.target.value);
                  setVersionId("");
                }}
              >
                <option value="">Select dataset</option>
                {datasets.data?.items
                  .filter((item) => item.protection !== "holdout")
                  .map((item) => (
                    <option value={item.id} key={item.id}>
                      {item.name}
                    </option>
                  ))}
              </select>
            </label>
            <label className="field">
              <span>Artifact version</span>
              <select
                aria-label="Artifact version"
                required
                value={versionId}
                onChange={(event) => setVersionId(event.target.value)}
              >
                <option value="">Select version</option>
                {versions.data?.items.map((item) => (
                  <option value={item.id} key={item.id}>
                    v{item.number} · {item.sample_count} samples
                  </option>
                ))}
              </select>
            </label>
            <ErrorNotice error={versions.error} />
            <div className="studio-actions">
              <Button
                type="button"
                variant="secondary"
                busy={action.busy}
                disabled={!poolId}
                onClick={async () => {
                  const result = await action.perform(() =>
                    call("/compute/placement", {
                      method: "POST",
                      body: {
                        pool_id: poolId,
                        engine: "artifact.verify@1",
                        cpu_cores: 1,
                        memory_gib: 0.5,
                      },
                    }),
                  );
                  if (result) setPlacement(result);
                }}
              >
                Check placement
              </Button>
              {organization.scopes.includes("runs:execute") && (
                <Button
                  type="submit"
                  busy={action.busy}
                  disabled={!poolId || !versionId}
                >
                  Queue verification
                </Button>
              )}
            </div>
            {placement !== null && <Code value={placement} />}
            <small>
              One CPU, 0.5 GiB, $0 external cost. No arbitrary code executes.
            </small>
          </form>
        </section>
        <section className="panel">
          <div className="panel-heading">
            <h2>Agent identities</h2>
          </div>
          <div className="panel-body">
            {canManage && (
              <form
                onSubmit={async (event) => {
                  event.preventDefault();
                  const result = await mutate<Agent>("/compute/agents", {
                    pool_id: poolId,
                    name: agentName,
                  });
                  if (result?.agent_token) {
                    setSecret(result.agent_token);
                    setAgentName("");
                    toast("Agent enrolled. Save its one-time credential.");
                  }
                }}
              >
                <label className="field">
                  <span>Agent name</span>
                  <input
                    aria-label="Agent name"
                    required
                    maxLength={160}
                    value={agentName}
                    onChange={(event) => setAgentName(event.target.value)}
                  />
                </label>
                <Button
                  type="submit"
                  variant="secondary"
                  disabled={!poolId}
                  busy={action.busy}
                >
                  Enroll in selected pool
                </Button>
              </form>
            )}
            <p className="muted">
              Inject the one-time token as FOUNDRY_AGENT_TOKEN, then run:
            </p>
            <Code value="uv run python -m foundry.agent" />
            {agents.data?.items.map((agent) => (
              <div className="record-row" key={agent.id}>
                <div>
                  <strong>{agent.name}</strong>
                  <small>
                    {agent.revoked
                      ? "Revoked"
                      : agent.seen_at
                        ? `Heartbeat: ${new Date(agent.seen_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST`
                        : "Awaiting first heartbeat"}
                  </small>
                </div>
                {canManage && !agent.revoked && (
                  <Button
                    variant="ghost"
                    busy={action.busy}
                    onClick={() => mutate(`/compute/agents/${agent.id}/revoke`)}
                  >
                    Revoke
                  </Button>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>Verification jobs</h2>
          <small>Most recent 100</small>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Job</th>
                <th>Status</th>
                <th>Attempt</th>
                <th>Result</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.data?.items.map((job) => (
                <tr key={job.id}>
                  <td className="mono">{shortId(job.id)}</td>
                  <td>
                    <Status value={job.status} />
                  </td>
                  <td>{job.attempt}</td>
                  <td>
                    {job.result?.verified_by_api
                      ? "Checksum verified by API"
                      : job.error || "Awaiting worker"}
                  </td>
                  <td>
                    {!["SUCCEEDED", "FAILED", "CANCELLED"].includes(
                      job.status,
                    ) &&
                      organization.scopes.includes("runs:execute") && (
                        <Button
                          variant="ghost"
                          busy={action.busy}
                          onClick={() =>
                            mutate(`/compute/jobs/${job.id}/cancel`)
                          }
                        >
                          Cancel
                        </Button>
                      )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!jobs.data?.items.length && (
            <p className="panel-body muted">Queued work will appear here.</p>
          )}
        </div>
      </section>
      <Modal
        open={poolOpen}
        setOpen={setPoolOpen}
        title="Register compute pool"
        description="Describe an approved capacity envelope. Registration alone does not start or provision resources."
      >
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            const result = await mutate<Pool>("/compute/registered-pools", {
              name,
              scheduler,
              capabilities: { cpu_cores: cores, memory_gib: memory },
            });
            if (result) {
              setPoolOpen(false);
              setPoolId(result.id);
              toast("Compute pool registered.");
            }
          }}
        >
          <label className="field">
            <span>Pool name</span>
            <input
              aria-label="Pool name"
              required
              maxLength={160}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Scheduler</span>
            <select
              aria-label="Scheduler"
              value={scheduler}
              onChange={(event) => setScheduler(event.target.value)}
            >
              <option value="agent">Outbound agent · available locally</option>
              <option value="kubernetes">
                Kubernetes / Kueue · blocked external
              </option>
              <option value="slurm">Slurm · blocked external</option>
            </select>
          </label>
          <div className="field-row">
            <label className="field">
              <span>CPU capacity</span>
              <input
                aria-label="CPU capacity"
                required
                type="number"
                min={1}
                max={1024}
                value={cores}
                onChange={(event) => setCores(Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>Memory capacity (GiB)</span>
              <input
                aria-label="Memory capacity (GiB)"
                required
                type="number"
                min={0.25}
                step={0.25}
                max={4096}
                value={memory}
                onChange={(event) => setMemory(Number(event.target.value))}
              />
            </label>
          </div>
          <ErrorNotice error={action.error} />
          <div className="modal-actions">
            <Button type="submit" busy={action.busy}>
              Register pool
            </Button>
          </div>
        </form>
      </Modal>
      <Modal
        open={!!secret}
        setOpen={(open) => {
          if (!open) setSecret("");
        }}
        title="Save agent credential"
        description="This token is shown once. Keep it in your worker secret manager."
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
