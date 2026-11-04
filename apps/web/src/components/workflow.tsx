"use client";
import { Background, ReactFlow } from "@xyflow/react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  Code2,
  FileJson2,
  GitBranch,
  Info,
  Play,
  Plus,
  Save,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type {
  Dataset,
  Page,
  Recipe,
  RecipeDefinition,
  Run,
  Upload,
  Usage,
} from "@/lib/api";
import { date, money, shortId } from "@/lib/api";
import { useResource, useWorkspace } from "./context";
import {
  Button,
  Copy,
  Empty,
  ErrorNotice,
  Loading,
  Modal,
  PageHeader,
  Status,
  useAction,
} from "./ui";

const initial: RecipeDefinition = {
  name: "Verified text pipeline",
  schema_version: "1.0",
  nodes: [
    {
      id: "source",
      type: "generate",
      config: { engine: "deterministic.text@1", count: 100, seed: 42 },
    },
    {
      id: "validate",
      type: "validate",
      config: {
        minimum_samples: 100,
        max_duplicate_ratio: 0,
        max_invalid_ratio: 0,
      },
    },
    { id: "publish", type: "publish", config: {} },
    { id: "export", type: "export", config: { format: "jsonl" } },
  ],
  edges: [
    { from: "source", to: "validate" },
    { from: "validate", to: "publish" },
    { from: "publish", to: "export" },
  ],
  budget: { currency: "USD", maximum: 1 },
};

export function WorkflowsPage() {
  const query = useResource<Page<Recipe>>("/recipes?limit=100");
  const { organization } = useWorkspace();
  return (
    <>
      <PageHeader
        title="Workflows"
        description="Make good data a repeatable process."
      >
        {organization.scopes.includes("datasets:write") && (
          <Link href="/workflows/new" className="button primary">
            <Plus size={14} />
            New workflow
          </Link>
        )}
      </PageHeader>
      <ErrorNotice error={query.error} />
      {query.isPending ? (
        <Loading />
      ) : !query.data?.items.length ? (
        <div className="panel">
          <Empty
            icon={GitBranch}
            title="Your process, made reproducible"
            description="Connect a source, quality checks, and a publisher. Every execution freezes its recipe revision."
            action={
              organization.scopes.includes("datasets:write") ? (
                <Link href="/workflows/new" className="button secondary">
                  Build your first workflow <ArrowUpRight size={13} />
                </Link>
              ) : undefined
            }
          />
        </div>
      ) : (
        <div
          className="table-wrap"
          role="region"
          aria-label="Workflows table"
          tabIndex={0}
        >
          <table>
            <thead>
              <tr>
                <th>Workflow</th>
                <th>Revision</th>
                <th>Steps</th>
                <th>Created</th>
                <th>
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((recipe) => (
                <tr key={recipe.id}>
                  <td>
                    <div className="cell-title">
                      <span className="resource-icon">
                        <GitBranch size={16} />
                      </span>
                      <Link href={`/workflows/${recipe.id}`}>
                        {recipe.name}
                      </Link>
                    </div>
                  </td>
                  <td className="mono muted">
                    {recipe.revisions.length} saved
                  </td>
                  <td className="mono muted">
                    {recipe.revisions[0]?.definition.nodes.length || 0}
                  </td>
                  <td className="muted">{date(recipe.created_at)}</td>
                  <td>
                    <Link
                      href={`/workflows/${recipe.id}`}
                      aria-label={`Open ${recipe.name}`}
                      className="icon-button"
                    >
                      <ArrowUpRight size={15} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

export function WorkflowEditor({ id }: { id: string }) {
  const { call, project, projects, organization, toast } = useWorkspace();
  const router = useRouter();
  const queryClient = useQueryClient();
  const search = useSearchParams();
  const existing = useResource<Recipe>(
    id === "new" ? "/recipes?limit=1" : `/recipes/${id}`,
  );
  const datasets = useResource<Page<Dataset>>("/datasets?limit=100");
  const usage = useResource<Usage>("/usage");
  const [datasetId, setDatasetId] = useState(search.get("dataset") || "");
  const [targetInitialized, setTargetInitialized] = useState(
    Boolean(search.get("dataset")),
  );
  const uploads = useResource<Page<Upload>>(
    `/uploads?dataset_id=${datasetId || "none"}`,
    false,
    Boolean(datasetId),
  );
  const [json, setJson] = useState(JSON.stringify(initial, null, 2));
  const [loaded, setLoaded] = useState(false);
  const [selectedNode, setSelectedNode] = useState("source");
  const [launch, setLaunch] = useState(false);
  const [quote, setQuote] = useState<{
    sample_count: number;
    internal_estimate_usd: number;
    external_cost_usd: number;
  } | null>(null);
  const [budget, setBudget] = useState(1);
  const action = useAction();
  const [validated, setValidated] = useState(false);
  useEffect(() => {
    if (id !== "new" && existing.data?.revisions?.[0] && !loaded) {
      setJson(JSON.stringify(existing.data.revisions[0].definition, null, 2));
      setLoaded(true);
    }
  }, [existing.data, loaded, id]);
  const parsed = useMemo(() => {
    try {
      const value = JSON.parse(json) as RecipeDefinition;
      return value &&
        Array.isArray(value.nodes) &&
        Array.isArray(value.edges) &&
        value.budget
        ? value
        : null;
    } catch {
      return null;
    }
  }, [json]);
  const source = parsed?.nodes.find((node) =>
    ["ingest", "generate", "curate"].includes(node.type),
  );
  const sourceUpload = useResource<Upload>(
    `/uploads/${encodeURIComponent(String(source?.config.upload_id || "none"))}`,
    false,
    source?.type === "ingest" && Boolean(source.config.upload_id),
  );
  const sourceCuration = useResource<{ dataset_id: string; name: string }>(
    `/curations/${encodeURIComponent(String(source?.config.curation_id || "none"))}`,
    false,
    source?.type === "curate" && Boolean(source.config.curation_id),
  );
  const targetDataset = useResource<Dataset>(
    `/datasets/${datasetId || "none"}`,
    false,
    Boolean(datasetId),
  );
  useEffect(() => {
    if (
      targetDataset.data?.modality === "image" &&
      source?.type === "generate" &&
      id === "new"
    ) {
      const copy = structuredClone(parsed!);
      const node = copy.nodes.find((item) => item.id === source.id)!;
      node.type = "ingest";
      node.config = { upload_id: "" };
      setJson(JSON.stringify(copy, null, 2));
      setValidated(false);
    }
  }, [targetDataset.data?.modality, source, parsed, id]);
  useEffect(() => {
    if (targetInitialized || (id !== "new" && !loaded)) return;
    if (source?.type === "curate") {
      if (sourceCuration.data) {
        setDatasetId(sourceCuration.data.dataset_id);
        setTargetInitialized(true);
      }
      return;
    }
    if (source?.type === "ingest" && source.config.upload_id) {
      if (sourceUpload.data) {
        setDatasetId(sourceUpload.data.dataset_id);
        setTargetInitialized(true);
      }
      return;
    }
    const target = datasets.data?.items.find(
      (item) => id === "new" || item.project_id === existing.data?.project_id,
    );
    if (target) {
      setDatasetId(target.id);
      setTargetInitialized(true);
    }
  }, [
    targetInitialized,
    id,
    loaded,
    source,
    sourceUpload.data,
    sourceCuration.data,
    datasets.data,
    existing.data?.project_id,
  ]);
  const gate = parsed?.nodes.find((node) => node.type === "validate");
  const chosen = parsed?.nodes.find((node) => node.id === selectedNode);
  function update(fn: (value: RecipeDefinition) => void) {
    if (!parsed) return;
    const copy = structuredClone(parsed);
    fn(copy);
    setJson(JSON.stringify(copy, null, 2));
    setValidated(false);
  }
  const graph = useMemo(
    () => ({
      nodes: (parsed?.nodes || []).map((node, index) => ({
        id: node.id,
        position: { x: index * 205, y: 70 },
        data: {
          label: `${String(index + 1).padStart(2, "0")}  ${node.type === "generate" ? "Generate text" : node.type === "ingest" ? "Ingest upload" : node.type === "curate" ? "Reviewed source" : node.type === "validate" ? "Quality gates" : node.type === "publish" ? "Publish version" : "Export JSONL"}`,
        },
        selected: selectedNode === node.id,
      })),
      edges: (parsed?.edges || []).map((edge, index) => ({
        id: `edge-${index}`,
        source: edge.from,
        target: edge.to,
        style: { stroke: "var(--faint)" },
      })),
    }),
    [parsed, selectedNode],
  );
  const savedRevision =
    id !== "new" ? existing.data?.revisions?.[0] : undefined;
  const dirty =
    savedRevision &&
    JSON.stringify(parsed) !== JSON.stringify(savedRevision.definition);
  async function save() {
    const result = await action.perform(async () => {
      if (!parsed) throw new Error("Fix the recipe JSON before saving.");
      await call("/recipes/validate", { method: "POST", body: parsed });
      if (id === "new")
        return await call<Recipe>("/recipes", {
          method: "POST",
          body: {
            project_id:
              datasets.data?.items.find((item) => item.id === datasetId)
                ?.project_id || project,
            definition: parsed,
          },
        });
      await call(`/recipes/${id}/revisions`, { method: "POST", body: parsed });
      return { id } as Recipe;
    });
    if (result) {
      await queryClient.invalidateQueries();
      toast("Immutable recipe revision saved.");
      router.push(
        `/workflows/${result.id}?dataset=${encodeURIComponent(datasetId)}`,
      );
    }
  }
  if (id !== "new" && existing.isPending) return <Loading />;
  if (id !== "new" && existing.error)
    return <ErrorNotice error={existing.error} />;
  const canWrite = organization.scopes.includes("datasets:write");
  return (
    <>
      <PageHeader
        eyebrow="WORKFLOWS"
        title={
          id === "new" ? "Build a workflow" : existing.data?.name || "Workflow"
        }
        description="A clear path from source data to a verified, immutable version."
      >
        {canWrite && (
          <Button variant="secondary" busy={action.busy} onClick={save}>
            <Save size={13} />
            {id === "new" ? "Save workflow" : "Save revision"}
          </Button>
        )}
        {savedRevision && organization.scopes.includes("runs:execute") && (
          <Button
            busy={action.busy}
            disabled={!!dirty || !datasetId}
            onClick={() =>
              action.perform(async () => {
                const result = await call<{
                  sample_count: number;
                  internal_estimate_usd: number;
                  external_cost_usd: number;
                }>(`/recipes/${id}/estimate`, { method: "POST" });
                setQuote(result);
                setBudget(parsed?.budget.maximum || 1);
                setLaunch(true);
              })
            }
          >
            <Play size={13} />
            Launch run
          </Button>
        )}
      </PageHeader>
      <ErrorNotice
        error={
          action.error ||
          datasets.error ||
          sourceUpload.error ||
          sourceCuration.error ||
          targetDataset.error
        }
      />
      {dirty && (
        <div className="notice">
          <Info size={15} />
          Save a revision to run your latest changes.
        </div>
      )}
      <div className="flow-layout">
        <div className="stack">
          <div className="panel">
            <div className="panel-heading">
              <h2>Pipeline</h2>
              <span className="muted" style={{ fontSize: 10 }}>
                Select a step to inspect its configuration
              </span>
            </div>
            <div
              className="flow-canvas"
              role="region"
              aria-label="Recipe graph"
            >
              <ReactFlow
                nodes={graph.nodes}
                edges={graph.edges}
                nodesDraggable={false}
                nodesConnectable={false}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                minZoom={0.25}
                maxZoom={1.2}
                onNodeClick={(_, node) => setSelectedNode(node.id)}
              >
                <Background color="var(--strong-border)" gap={18} size={0.8} />
              </ReactFlow>
            </div>
            {chosen && (
              <div className="panel-body node-detail">
                <span className="mono">{chosen.id}</span> · {chosen.type}
                <pre style={{ padding: "8px 0 0" }}>
                  {JSON.stringify(chosen.config, null, 2)}
                </pre>
              </div>
            )}
          </div>
          <div className="panel">
            <div className="panel-heading">
              <h2>
                <Code2
                  size={13}
                  style={{ display: "inline", marginRight: 7 }}
                />
                Recipe JSON
              </h2>
              <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <Copy value={json} label="Copy recipe JSON" />
                <Button
                  variant="ghost"
                  busy={action.busy}
                  disabled={!parsed}
                  onClick={() =>
                    action.perform(async () => {
                      await call("/recipes/validate", {
                        method: "POST",
                        body: parsed,
                      });
                      setValidated(true);
                      toast("Recipe is valid.");
                    })
                  }
                >
                  {validated ? <Check size={13} /> : <ShieldCheck size={13} />}
                  {validated ? "Valid" : "Validate"}
                </Button>
              </div>
            </div>
            <textarea
              aria-label="Recipe JSON"
              className="recipe-json"
              spellCheck={false}
              readOnly={!canWrite}
              value={json}
              onChange={(event) => {
                setJson(event.target.value);
                setValidated(false);
              }}
            />
            {!parsed && (
              <div className="error-notice">
                Enter valid recipe JSON with nodes, edges, and a budget.
              </div>
            )}
          </div>
        </div>
        <aside className="stack">
          <div className="panel">
            <div className="panel-heading">
              <h2>Workflow settings</h2>
              <GitBranch size={14} className="muted" />
            </div>
            <div className="panel-body">
              <label className="field">
                <span>Name</span>
                <input
                  value={parsed?.name || ""}
                  disabled={!canWrite || !parsed}
                  maxLength={160}
                  onChange={(event) =>
                    update((value) => {
                      value.name = event.target.value;
                    })
                  }
                />
              </label>
              <label className="field">
                <span>Target dataset</span>
                <select
                  value={datasetId}
                  disabled={source?.type === "curate"}
                  onChange={(event) => {
                    setDatasetId(event.target.value);
                    setTargetInitialized(true);
                    if (source?.type === "ingest")
                      update((value) => {
                        value.nodes.find(
                          (node) => node.id === source.id,
                        )!.config.upload_id = "";
                      });
                  }}
                >
                  <option value="">Select a dataset</option>
                  {targetDataset.data &&
                    !datasets.data?.items.some(
                      (item) => item.id === datasetId,
                    ) && (
                      <option value={datasetId}>
                        {targetDataset.data.name}
                      </option>
                    )}
                  {datasets.data?.items.map((dataset) => (
                    <option key={dataset.id} value={dataset.id}>
                      {dataset.name}
                    </option>
                  ))}
                </select>
                {!datasets.data?.items.length && (
                  <small>
                    <Link href="/datasets">
                      Create a dataset first{" "}
                      <ArrowUpRight size={10} style={{ display: "inline" }} />
                    </Link>
                  </small>
                )}
              </label>
              <label className="field">
                <span>Source</span>
                <select
                  value={source?.type || "generate"}
                  disabled={!canWrite || !source || source.type === "curate"}
                  onChange={(event) =>
                    update((value) => {
                      const node = value.nodes.find(
                        (item) => item.id === source?.id,
                      );
                      if (node) {
                        node.type = event.target.value;
                        node.config =
                          node.type === "generate"
                            ? {
                                engine: "deterministic.text@1",
                                count: 100,
                                seed: 42,
                              }
                            : { upload_id: "" };
                      }
                    })
                  }
                >
                  <option
                    value="generate"
                    disabled={targetDataset.data?.modality === "image"}
                  >
                    Deterministic text generator
                  </option>
                  <option value="ingest">Verified upload</option>
                  {source?.type === "curate" && (
                    <option value="curate">Frozen human-reviewed source</option>
                  )}
                </select>
              </label>
              {source?.type === "generate" ? (
                <div className="field-row">
                  <label className="field">
                    <span>Samples</span>
                    <input
                      type="number"
                      min={1}
                      max={10000}
                      disabled={!canWrite}
                      value={source.config.count ?? 100}
                      onChange={(event) =>
                        update((value) => {
                          const node = value.nodes.find(
                            (item) => item.id === source.id,
                          )!;
                          node.config.count = Number(event.target.value);
                        })
                      }
                    />
                  </label>
                  <label className="field">
                    <span>Seed</span>
                    <input
                      type="number"
                      min={0}
                      disabled={!canWrite}
                      value={source.config.seed ?? 42}
                      onChange={(event) =>
                        update((value) => {
                          value.nodes.find(
                            (item) => item.id === source.id,
                          )!.config.seed = Number(event.target.value);
                        })
                      }
                    />
                  </label>
                </div>
              ) : source?.type === "curate" ? (
                <div className="notice">
                  <ShieldCheck size={14} />
                  <Link href={`/curation/${source.config.curation_id}`}>
                    {sourceCuration.data?.name || "Inspect approved curation"}
                  </Link>
                </div>
              ) : (
                <label className="field">
                  <span>Verified upload</span>
                  <select
                    disabled={!canWrite}
                    value={source?.config.upload_id || ""}
                    onChange={(event) =>
                      update((value) => {
                        value.nodes.find(
                          (item) => item.id === source?.id,
                        )!.config.upload_id = event.target.value;
                      })
                    }
                  >
                    <option value="">Select an upload</option>
                    {uploads.data?.items
                      .filter((item) => item.status === "COMPLETED")
                      .map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.filename} · {item.sample_count} samples
                        </option>
                      ))}
                  </select>
                </label>
              )}
              <label className="field">
                <span>Minimum accepted samples</span>
                <input
                  type="number"
                  min={1}
                  disabled={!canWrite || !gate}
                  value={gate?.config.minimum_samples ?? 1}
                  onChange={(event) =>
                    update((value) => {
                      value.nodes.find(
                        (item) => item.id === gate?.id,
                      )!.config.minimum_samples = Number(event.target.value);
                    })
                  }
                />
              </label>
              <label className="field">
                <span>Budget ceiling (USD)</span>
                <input
                  type="number"
                  step="0.001"
                  min={0}
                  disabled={!canWrite || !parsed}
                  value={parsed?.budget.maximum || 0}
                  onChange={(event) =>
                    update((value) => {
                      value.budget.maximum = Number(event.target.value);
                    })
                  }
                />
                <small>Nonbillable local estimates. External cost is $0.</small>
              </label>
            </div>
          </div>
          <div className="notice">
            <Info size={15} />
            <span>
              The local generator creates reproducible arithmetic examples. It
              does not call an AI model.
            </span>
          </div>
          {savedRevision && (
            <div className="panel">
              <div className="panel-heading">
                <h2>Frozen revision</h2>
                <ShieldCheck size={13} />
              </div>
              <div className="panel-body">
                <div
                  className="mono muted"
                  style={{ overflowWrap: "anywhere" }}
                >
                  sha256:{savedRevision.digest}
                </div>
                <small style={{ display: "block", marginTop: 10 }}>
                  Changes create a new revision. Existing runs keep their
                  original definition.
                </small>
              </div>
            </div>
          )}
        </aside>
      </div>
      <Modal
        open={launch}
        setOpen={setLaunch}
        title="Launch workflow run"
        description="Review the estimate and budget before the worker is scheduled."
      >
        <dl className="key-values" style={{ marginBottom: 20 }}>
          <dt>Samples requested</dt>
          <dd>{quote?.sample_count}</dd>
          <dt>Internal estimate</dt>
          <dd>{money(quote?.internal_estimate_usd || 0)}</dd>
          <dt>External charges</dt>
          <dd>$0.00</dd>
          <dt>Executor</dt>
          <dd>Local CPU</dd>
        </dl>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            const result = await action.perform(() =>
              call<Run>("/runs", {
                method: "POST",
                body: {
                  dataset_id: datasetId,
                  recipe_revision_id: savedRevision?.id,
                  max_budget_usd: budget,
                },
              }),
            );
            if (result) {
              setLaunch(false);
              queryClient.invalidateQueries();
              toast("Run accepted and queued.");
              router.push(`/runs/${result.id}`);
            }
          }}
        >
          <label className="field">
            <span>Run budget cap (USD)</span>
            <input
              type="number"
              min={0}
              max={parsed?.budget.maximum}
              step="0.001"
              required
              value={budget}
              onChange={(event) => setBudget(Number(event.target.value))}
            />
          </label>
          <ErrorNotice error={action.error} />
          <div className="modal-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setLaunch(false)}
            >
              Cancel
            </Button>
            <Button type="submit" busy={action.busy}>
              <Play size={13} />
              Confirm & launch
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
