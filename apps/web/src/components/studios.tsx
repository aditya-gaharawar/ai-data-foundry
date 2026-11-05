"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Box, Cpu, Plus, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Dataset, Page, Recipe, RecipeDefinition, Run } from "@/lib/api";
import { useResource, useWorkspace } from "./context";
import {
  Button,
  Code,
  Empty,
  ErrorNotice,
  Loading,
  Modal,
  PageHeader,
  Status,
  useAction,
} from "./ui";

export type Provider = {
  id: string;
  name: string;
  kind: string;
  model_ref: string;
  state: string;
  reason: string;
  revoked: boolean;
  rights: Record<string, unknown>;
};
type Catalog = {
  kind: string;
  model_ref?: string;
  state: string;
  reason: string;
  license?: string;
};

export function TeacherStudio() {
  const { call, organization, toast } = useWorkspace();
  const providers = useResource<Page<Provider>>("/providers?limit=100");
  const catalog = useResource<{ items: Catalog[] }>("/providers/catalog");
  const cache = useQueryClient();
  const action = useAction();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("local.gguf");
  const [model, setModel] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [secret, setSecret] = useState("");
  const [terms, setTerms] = useState("Apache-2.0");
  const [rights, setRights] = useState("");
  const [consent, setConsent] = useState(false);
  const canManage = organization.scopes.includes("providers:manage");
  const localEntry = catalog.data?.items.find(
    (item) => item.kind === "local.gguf",
  );
  return (
    <>
      <PageHeader
        eyebrow="BUILD / TEACHER STUDIO"
        title="Generate with provenance"
        description="Permitted synthetic text, measured token usage, and a record of every accepted output."
      >
        {canManage && (
          <Button onClick={() => setOpen(true)}>
            <Plus size={14} />
            Connect provider
          </Button>
        )}
      </PageHeader>
      <ErrorNotice error={providers.error || catalog.error || action.error} />
      <div className="capability-grid">
        {catalog.data?.items.map((item) => (
          <div className="panel capability-card" key={item.kind}>
            <div className="section-row">
              <Sparkles size={17} />
              <Status value={item.state} />
            </div>
            <h2>
              {item.kind === "local.gguf"
                ? "Local text model"
                : item.kind === "http.image"
                  ? "Image provider"
                  : "External text provider"}
            </h2>
            <p>{item.reason}</p>
            {item.license && (
              <small>{item.license} · CPU · no external charges</small>
            )}
          </div>
        ))}
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>Provider connections</h2>
          <span className="muted">Rights and credentials are immutable</span>
        </div>
        {providers.isPending ? (
          <Loading />
        ) : !providers.data?.items.length ? (
          <Empty
            icon={Sparkles}
            title="Connect a permitted source"
            description="The local model runs privately on CPU. External accounts remain blocked until approved and configured."
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Connection</th>
                  <th>Model</th>
                  <th>Availability</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {providers.data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.name}</strong>
                      <small>{item.kind}</small>
                    </td>
                    <td className="mono">{item.model_ref}</td>
                    <td>
                      <Status value={item.state} />
                      <small>{item.reason}</small>
                    </td>
                    <td>
                      {canManage && !item.revoked && (
                        <Button
                          variant="ghost"
                          busy={action.busy}
                          onClick={async () => {
                            const result = await action.perform(() =>
                              call(`/providers/${item.id}/revoke`, {
                                method: "POST",
                                body: {},
                              }),
                            );
                            if (result) {
                              cache.invalidateQueries();
                              toast("Provider revoked.");
                            }
                          }}
                        >
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
      </section>
      <GenerationForm mode="teacher" providers={providers.data?.items || []} />
      <Modal
        open={open}
        setOpen={setOpen}
        title="Connect provider"
        description="Record permission for the intended training purpose. External accounts are never called by this local build."
      >
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            const readyModel = localEntry?.model_ref;
            if (
              kind === "local.gguf" &&
              (!readyModel || localEntry?.state !== "READY")
            )
              return;
            const result = await action.perform(() =>
              call<Provider>("/providers", {
                method: "POST",
                body: {
                  name,
                  kind,
                  model_ref: kind === "local.gguf" ? readyModel : model,
                  ...(kind !== "local.gguf"
                    ? { endpoint, ...(secret ? { api_secret: secret } : {}) }
                    : {}),
                  permitted_training_use: true,
                  consent_to_processing: true,
                  terms_version: terms,
                  rights_evidence: rights,
                },
              }),
            );
            if (result) {
              const providerKey = [organization.id, "/providers?limit=100"];
              await cache.cancelQueries({ queryKey: providerKey });
              cache.setQueryData<Page<Provider>>(providerKey, (current) => ({
                items: [
                  result,
                  ...(current?.items || []).filter(
                    (item) => item.id !== result.id,
                  ),
                ],
                next_cursor: current?.next_cursor || null,
              }));
              setOpen(false);
              setSecret("");
              setConsent(false);
              await cache.invalidateQueries();
              toast("Provider connection saved.");
            }
          }}
        >
          {kind === "local.gguf" && (
            <p className="muted" role="status">
              {catalog.isPending
                ? "Loading verified local model metadata…"
                : localEntry?.reason ||
                  "Local model metadata is unavailable. Check the provider catalog."}
            </p>
          )}
          <label className="field">
            <span>Connection name</span>
            <input
              aria-label="Connection name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              maxLength={160}
            />
          </label>
          <label className="field">
            <span>Provider kind</span>
            <select
              aria-label="Provider kind"
              value={kind}
              onChange={(event) => {
                setKind(event.target.value);
                setModel("");
              }}
            >
              <option value="local.gguf">Local licensed CPU model</option>
              <option value="http.structured">
                External structured text · blocked
              </option>
              <option value="http.image">External image · blocked</option>
            </select>
          </label>
          {kind !== "local.gguf" && (
            <>
              <label className="field">
                <span>Model reference</span>
                <input
                  aria-label="Model reference"
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  required
                  maxLength={200}
                />
              </label>
              <label className="field">
                <span>HTTPS endpoint</span>
                <input
                  aria-label="HTTPS endpoint"
                  value={endpoint}
                  onChange={(event) => setEndpoint(event.target.value)}
                  type="url"
                  required
                />
              </label>
              <label className="field">
                <span>API secret (optional)</span>
                <input
                  aria-label="API secret (optional)"
                  value={secret}
                  onChange={(event) => setSecret(event.target.value)}
                  type="password"
                  autoComplete="off"
                />
              </label>
            </>
          )}
          <label className="field">
            <span>Terms version</span>
            <input
              aria-label="Terms version"
              value={terms}
              onChange={(event) => setTerms(event.target.value)}
              required
              maxLength={200}
            />
          </label>
          <label className="field">
            <span>Rights evidence</span>
            <textarea
              aria-label="Rights evidence"
              value={rights}
              onChange={(event) => setRights(event.target.value)}
              minLength={8}
              maxLength={4000}
              required
              placeholder="License, source, intended use, and permission evidence"
            />
          </label>
          <label className="check-field">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
              required
            />
            <span>
              I have permission to process these inputs and use outputs for this
              training purpose.
            </span>
          </label>
          <ErrorNotice error={action.error} />
          <div className="modal-actions">
            <Button
              type="submit"
              busy={action.busy}
              disabled={
                !consent ||
                (kind === "local.gguf" &&
                  (!localEntry?.model_ref || localEntry.state !== "READY"))
              }
            >
              Save connection
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

export function SimulationStudio() {
  const capabilities = useResource<{
    items: {
      engine: string;
      state: string;
      reason: string;
      version?: string;
    }[];
  }>("/simulations/capabilities");
  return (
    <>
      <PageHeader
        eyebrow="BUILD / SIMULATION STUDIO"
        title="From scene to sample"
        description="Original procedural scenes, rendered frames, aligned masks, and inspectable 3D artifacts."
      />
      <ErrorNotice error={capabilities.error} />
      <div className="capability-grid">
        {capabilities.data?.items.map((item) => (
          <div className="panel capability-card" key={item.engine}>
            <div className="section-row">
              <Box size={18} />
              <Status value={item.state} />
            </div>
            <h2>{item.engine}</h2>
            <p>{item.reason}</p>
            {item.version && <small>{item.version}</small>}
          </div>
        ))}
      </div>
      <div className="notice">
        Blender uses scripted camera/object motion and primitive assets. These
        episodes do not represent robot dynamics or sim-to-real validation.
      </div>
      <GenerationForm mode="simulate" providers={[]} />
    </>
  );
}

function GenerationForm({
  mode,
  providers,
}: {
  mode: "teacher" | "simulate";
  providers: Provider[];
}) {
  const { call, organization } = useWorkspace();
  const router = useRouter();
  const cache = useQueryClient();
  const action = useAction();
  const datasets = useResource<Page<Dataset>>("/datasets?limit=100");
  const [datasetId, setDatasetId] = useState("");
  const [providerId, setProviderId] = useState("");
  const [instructions, setInstructions] = useState("");
  const [count, setCount] = useState(1);
  const [seed, setSeed] = useState(42);
  const [frames, setFrames] = useState(1);
  const [shape, setShape] = useState("cube");
  const [resolution, setResolution] = useState(128);
  const [estimate, setEstimate] = useState<Record<string, unknown> | null>(
    null,
  );
  const [saved, setSaved] = useState<{
    recipe: Recipe;
    datasetId: string;
    fingerprint: string;
  } | null>(null);
  const [budget, setBudget] = useState(0.1);
  const target = datasets.data?.items.find((item) => item.id === datasetId);
  const eligible =
    datasets.data?.items.filter(
      (item) =>
        !item.archived &&
        item.modality === (mode === "teacher" ? "text" : "image") &&
        item.protection !== "holdout",
    ) || [];
  const canWrite =
    organization.scopes.includes("datasets:write") &&
    organization.scopes.includes("runs:execute");
  const config: Record<string, string | number> =
    mode === "teacher"
      ? {
          connection_id: providerId,
          instructions,
          count,
          seed,
          max_output_tokens: 256,
        }
      : {
          engine: "blender.procedural@1",
          object_type: shape,
          count,
          frames_per_scene: frames,
          resolution,
          fps: 10,
          seed,
          render_samples: 4,
        };
  const fingerprint = JSON.stringify({ config, datasetId, budget });
  const ready =
    mode === "simulate" ||
    providers.some((item) => item.id === providerId && item.state === "READY");
  async function prepare() {
    if (!target) throw new Error("Select a target dataset.");
    const samples = count * (mode === "simulate" ? frames : 1);
    const definition: RecipeDefinition = {
      name: `${mode === "teacher" ? "Teacher" : "Blender"} · ${target.name}`,
      schema_version: "1.0",
      nodes: [
        {
          id: "source",
          type: mode,
          config,
        },
        {
          id: "validate",
          type: "validate",
          config: {
            minimum_samples: samples,
            max_duplicate_ratio: 0,
            max_invalid_ratio: 0,
          },
        },
        { id: "publish", type: "publish", config: {} },
      ],
      edges: [
        { from: "source", to: "validate" },
        { from: "validate", to: "publish" },
      ],
      budget: { currency: "USD", maximum: budget },
    };
    const recipe = await call<Recipe>("/recipes", {
      method: "POST",
      body: { project_id: target.project_id, definition },
    });
    setSaved({ recipe, datasetId, fingerprint });
    setEstimate(
      await call<Record<string, unknown>>(`/recipes/${recipe.id}/estimate`, {
        method: "POST",
      }),
    );
    cache.invalidateQueries({ queryKey: [organization.id, "/recipes"] });
  }
  return (
    <section className="panel studio-form">
      <div className="panel-heading">
        <h2>
          {mode === "teacher"
            ? "Create synthetic text"
            : "Render a Blender episode"}
        </h2>
        <span className="muted">Durable worker · immutable output</span>
      </div>
      <form
        className="panel-body"
        onSubmit={(event) => {
          event.preventDefault();
          action.perform(prepare);
        }}
      >
        <fieldset disabled={!canWrite || action.busy}>
          <div className="field-row">
            <label className="field">
              <span>Target dataset</span>
              <select
                aria-label="Target dataset"
                required
                value={datasetId}
                onChange={(event) => setDatasetId(event.target.value)}
              >
                <option value="">
                  Select a {mode === "teacher" ? "text" : "image"} dataset
                </option>
                {eligible.map((item) => (
                  <option value={item.id} key={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
              <small>
                Showing up to 100 datasets.{" "}
                <Link href="/datasets">Create a dataset</Link>
              </small>
            </label>
            {mode === "teacher" ? (
              <label className="field">
                <span>Provider connection</span>
                <select
                  aria-label="Provider connection"
                  required
                  value={providerId}
                  onChange={(event) => setProviderId(event.target.value)}
                >
                  <option value="">Select a ready provider</option>
                  {providers.map((item) => (
                    <option
                      value={item.id}
                      disabled={item.state !== "READY"}
                      key={item.id}
                    >
                      {item.name} · {item.state}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <label className="field">
                <span>Primitive</span>
                <select
                  aria-label="Primitive"
                  value={shape}
                  onChange={(event) => setShape(event.target.value)}
                >
                  <option value="cube">Cube</option>
                  <option value="sphere">Sphere</option>
                </select>
              </label>
            )}
          </div>
          {mode === "teacher" && (
            <label className="field">
              <span>Generation instructions</span>
              <textarea
                aria-label="Generation instructions"
                required
                minLength={1}
                maxLength={4000}
                value={instructions}
                onChange={(event) => setInstructions(event.target.value)}
                placeholder="Describe the synthetic instruction and answer pairs you need."
              />
              <small>
                Outputs are schema-checked and marked unreviewed. The tiny local
                model cannot establish factual quality.
              </small>
            </label>
          )}
          <div className="field-row">
            <label className="field">
              <span>{mode === "teacher" ? "Samples" : "Scenes"}</span>
              <input
                type="number"
                min={1}
                max={mode === "teacher" ? 10 : 5}
                value={count}
                onChange={(event) => setCount(Number(event.target.value))}
                required
              />
            </label>
            <label className="field">
              <span>Seed</span>
              <input
                aria-label="Seed"
                type="number"
                min={0}
                max={2147483647}
                value={seed}
                onChange={(event) => setSeed(Number(event.target.value))}
                required
              />
            </label>
          </div>
          {mode === "simulate" && (
            <div className="field-row">
              <label className="field">
                <span>Frames per scene</span>
                <input
                  aria-label="Frames per scene"
                  type="number"
                  min={1}
                  max={3}
                  value={frames}
                  onChange={(event) => setFrames(Number(event.target.value))}
                />
              </label>
              <label className="field">
                <span>Resolution</span>
                <select
                  aria-label="Resolution"
                  value={resolution}
                  onChange={(event) =>
                    setResolution(Number(event.target.value))
                  }
                >
                  {[64, 128, 256].map((value) => (
                    <option key={value} value={value}>
                      {value} × {value}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
          <label className="field">
            <span>Maximum internal budget (USD)</span>
            <input
              aria-label="Maximum internal budget (USD)"
              type="number"
              min={0}
              max={100}
              step={0.001}
              value={budget}
              onChange={(event) => setBudget(Number(event.target.value))}
              required
            />
            <small>Local rate card only. External cost is $0.</small>
          </label>
        </fieldset>
        <ErrorNotice error={action.error || datasets.error} />
        <div className="studio-actions">
          <Button
            type="submit"
            variant="secondary"
            busy={action.busy}
            disabled={!canWrite || !ready}
          >
            Save recipe & estimate
          </Button>
          <Button
            type="button"
            busy={action.busy}
            disabled={
              !canWrite ||
              !saved ||
              !estimate ||
              saved.fingerprint !== fingerprint
            }
            onClick={async () => {
              if (!saved?.recipe.revision) return;
              const result = await action.perform(() =>
                call<Run>("/runs", {
                  method: "POST",
                  body: {
                    dataset_id: saved.datasetId,
                    recipe_revision_id: saved.recipe.revision!.id,
                    max_budget_usd: budget,
                  },
                }),
              );
              if (result) {
                cache.invalidateQueries();
                router.push(`/runs/${result.id}`);
              }
            }}
          >
            <Cpu size={14} />
            Start {mode === "teacher" ? "generation" : "render"}
          </Button>
        </div>
        {saved && saved.fingerprint !== fingerprint && (
          <p className="muted">
            Settings changed. Save a fresh recipe and estimate before starting.
          </p>
        )}
        {estimate && (
          <details className="evidence-details">
            <summary>Estimate and saved recipe</summary>
            <Code value={estimate} />
            {saved && (
              <Link
                href={`/workflows/${saved.recipe.id}?dataset=${encodeURIComponent(saved.datasetId)}`}
              >
                Inspect workflow
              </Link>
            )}
          </details>
        )}
        {!canWrite && (
          <p className="muted">
            Creating runs requires dataset write and run execution access.
          </p>
        )}
      </form>
    </section>
  );
}
