"use client";
import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Check,
  CircleCheck,
  Clock3,
  Cpu,
  Database,
  FileCheck2,
  FileJson2,
  FileText,
  GitBranch,
  HardDrive,
  Info,
  Layers3,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  UploadCloud,
  X,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import type {
  Dataset,
  Overview,
  Page,
  Quality,
  Run,
  Upload,
  UploadSession,
  Version,
} from "@/lib/api";
import { date, money, saveExport, shortId } from "@/lib/api";
import { useResource, useWorkspace } from "./context";
import { BoxEditor, PrivateImage } from "./annotation-image";
import { SimulationSample } from "./simulation-sample";
import type { Annotation } from "@/lib/curation";
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
  TextLink,
  useAction,
} from "./ui";

export function OverviewPage({ onCreate }: { onCreate: () => void }) {
  const query = useResource<Overview>("/overview", true);
  const { organization } = useWorkspace();
  const data = query.data;
  if (query.isPending) return <Loading />;
  if (!data) return <ErrorNotice error={query.error} />;
  const stats = [
    {
      title: "Datasets",
      value: data.counts.datasets,
      icon: Database,
      note: "In your organization",
    },
    {
      title: "Published versions",
      value: data.counts.versions,
      icon: Layers3,
      note: "Immutable & traceable",
    },
    {
      title: "Workflow runs",
      value: data.counts.runs,
      icon: GitBranch,
      note: "Across your workspace",
    },
    {
      title: "Samples processed",
      value: data.usage.meters.processed_samples || 0,
      icon: FileCheck2,
      note: "From durable checkpoints",
    },
  ];
  return (
    <>
      <PageHeader
        title="Overview"
        description="Your data, from source to training-ready."
      >
        {organization.scopes.includes("datasets:write") && (
          <Button onClick={onCreate}>
            <Plus size={14} />
            Create dataset
          </Button>
        )}
      </PageHeader>
      <div className="stats">
        {stats.map((item) => (
          <div className="stat" key={item.title}>
            <div className="stat-title">
              {item.title}
              <item.icon size={15} />
            </div>
            <div className="stat-number">{item.value.toLocaleString()}</div>
            <div className="stat-note">
              {item.title === "Published versions" && (
                <ShieldCheck size={11} className="positive-text" />
              )}
              {item.note}
            </div>
          </div>
        ))}
      </div>
      <div className="overview-grid">
        <section>
          <div className="section-row">
            <div>
              <h2>Recent activity</h2>
              <p>The latest work happening in your organization.</p>
            </div>
            <TextLink href="/runs">View all runs</TextLink>
          </div>
          <div className="panel">
            {data.recent_runs.length ? (
              <>
                <div className="panel-heading">
                  <h2>Workflow runs</h2>
                  <span className="mono muted">
                    {data.recent_runs.length} recent
                  </span>
                </div>
                <div className="compact-list">
                  {data.recent_runs.map((run) => (
                    <Link key={run.id} href={`/runs/${run.id}`}>
                      <span className="resource-icon">
                        <GitBranch size={16} />
                      </span>
                      <div>
                        <span className="mono">{shortId(run.id)}</span>
                        <div className="cell-subtitle">
                          {run.processed} / {run.sample_count} samples ·{" "}
                          {date(run.created_at)}
                        </div>
                      </div>
                      <Status value={run.status} />
                    </Link>
                  ))}
                </div>
                <div className="panel-footer">
                  <ShieldCheck size={12} /> Every run keeps its own provenance
                  and execution history.
                </div>
              </>
            ) : (
              <Empty
                icon={Activity}
                title="Your next run starts here"
                description="Create a dataset and connect a workflow. Your activity will appear as it happens."
                action={
                  <Link href="/workflows/new" className="button secondary">
                    Build a workflow <ArrowUpRight size={13} />
                  </Link>
                }
              />
            )}
          </div>
        </section>
        <section>
          <div className="section-row">
            <h2>Execution environment</h2>
          </div>
          <div className="panel worker-card">
            <div className="worker-icon">
              <Cpu size={22} strokeWidth={1.4} />
            </div>
            <Status value={data.worker} />
            <h3>Local CPU worker</h3>
            <p>
              A private execution environment for reproducible text data and
              validation.
            </p>
            <div className="subtle-rule" />
            <dl className="key-values">
              <dt>Engine</dt>
              <dd>deterministic.text</dd>
              <dt>External spend</dt>
              <dd>{money(data.usage.external_cost_usd)}</dd>
              <dt>Internal usage</dt>
              <dd>{money(data.usage.internal_spent_usd)}</dd>
            </dl>
          </div>
        </section>
      </div>
      <section className="workflow-intro">
        <div className="eyebrow">A BETTER DATA LIFECYCLE</div>
        <h2>From an idea to an immutable dataset.</h2>
        <p>
          Build once. Validate every sample. Know exactly what you trained on.
        </p>
        <div className="journey">
          {[
            {
              n: "01",
              title: "Give your data a home",
              text: "Create a dataset and declare your source rights.",
              href: "/datasets",
              done: data.counts.datasets > 0,
            },
            {
              n: "02",
              title: "Make the process repeatable",
              text: "Connect a source, quality gates, and a publisher.",
              href: "/workflows",
              done: data.counts.runs > 0,
            },
            {
              n: "03",
              title: "Ship with confidence",
              text: "Inspect provenance and export a verified version.",
              href: "/runs",
              done: data.counts.versions > 0,
            },
          ].map((item) => (
            <Link className="journey-item" key={item.n} href={item.href}>
              <div className="journey-number">
                {item.n}
                {item.done ? <Check size={12} /> : <ArrowUpRight size={13} />}
              </div>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}

export function DatasetsPage({ onCreate }: { onCreate: () => void }) {
  const [search, setSearch] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const { project, organization } = useWorkspace();
  const query = useResource<Page<Dataset>>(
    `/datasets?limit=15&q=${encodeURIComponent(search)}${project ? `&project_id=${project}` : ""}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
  );
  return (
    <>
      <PageHeader
        title="Datasets"
        description="A single source of truth for your training data."
      >
        {organization.scopes.includes("datasets:write") && (
          <Button onClick={onCreate}>
            <Plus size={14} />
            Create dataset
          </Button>
        )}
      </PageHeader>
      <div className="toolbar">
        <div className="input-search">
          <Search size={14} />
          <input
            aria-label="Search datasets"
            placeholder="Search datasets…"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setCursor(null);
            }}
          />
        </div>
        <span className="muted" style={{ fontSize: 11 }}>
          Text datasets · JSONL
        </span>
      </div>
      <ErrorNotice error={query.error} />
      {query.isPending ? (
        <Loading />
      ) : !query.data?.items.length ? (
        <div className="panel">
          <Empty
            icon={Database}
            title={search ? "No matching datasets" : "A home for every dataset"}
            description={
              search
                ? "Try a different name or clear the search."
                : "Keep your sources, samples, quality reports, and versions together."
            }
            action={
              !search && organization.scopes.includes("datasets:write") ? (
                <Button onClick={onCreate}>
                  <Plus size={13} />
                  Create your first dataset
                </Button>
              ) : undefined
            }
          />
        </div>
      ) : (
        <>
          <div
            className="table-wrap"
            role="region"
            aria-label="Datasets table"
            tabIndex={0}
          >
            <table>
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>Modality</th>
                  <th>Versions</th>
                  <th>Created</th>
                  <th>
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((dataset) => (
                  <tr key={dataset.id}>
                    <td>
                      <div className="cell-title">
                        <span className="resource-icon">
                          <Database size={16} />
                        </span>
                        <div>
                          <Link href={`/datasets/${dataset.id}`}>
                            {dataset.name}
                          </Link>
                          <div className="cell-subtitle">
                            {dataset.description || shortId(dataset.id)}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="status">
                        {dataset.modality === "image" ? "Image" : "Text"}
                      </span>
                    </td>
                    <td className="mono muted">
                      {dataset.versions_count || 0}
                    </td>
                    <td className="muted">{date(dataset.created_at)}</td>
                    <td>
                      <Link
                        className="icon-button"
                        href={`/datasets/${dataset.id}`}
                        aria-label={`Open ${dataset.name}`}
                      >
                        <ArrowUpRight size={15} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="table-end">
            <span>{query.data.items.length} datasets on this page</span>
            <div>
              {cursor && (
                <Button variant="ghost" onClick={() => setCursor(null)}>
                  First page
                </Button>
              )}
              {query.data.next_cursor && (
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

export function DatasetDetail({ id }: { id: string }) {
  const { call, organization, toast } = useWorkspace();
  const client = useQueryClient();
  const action = useAction();
  const query = useResource<Dataset>(`/datasets/${id}`);
  const versions = useResource<{ items: Version[] }>(
    `/datasets/${id}/versions`,
    true,
  );
  const uploads = useResource<Page<Upload>>(`/uploads?dataset_id=${id}`);
  const [tab, setTab] = useState("Samples");
  const [versionId, setVersionId] = useState("");
  const [offset, setOffset] = useState(0);
  const [edit, setEdit] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [progress, setProgress] = useState(0);
  const samples = useResource<{
    items: {
      sample_id: string;
      content_hash: string;
      payload: Record<string, unknown>;
      annotation?: Annotation;
    }[];
    total: number;
    next_offset: number | null;
  }>(
    `/datasets/${id}/samples?limit=10&offset=${offset}${versionId ? `&version_id=${versionId}` : ""}`,
  );
  const selected =
    versions.data?.items.find((version) => version.id === versionId) ||
    versions.data?.items[0];
  useEffect(() => {
    if (query.data) {
      setName(query.data.name);
      setDescription(query.data.description);
    }
  }, [query.data]);
  if (query.isPending) return <Loading />;
  if (!query.data) return <ErrorNotice error={query.error} />;
  const dataset = query.data;
  async function upload(file: File) {
    setUploading(true);
    setProgress(0);
    await action.perform(async () => {
      if (
        !(dataset.modality === "image"
          ? /\.(png|jpe?g)$/i.test(file.name)
          : file.name.endsWith(".jsonl")) ||
        file.size > 20 * 1024 * 1024 ||
        file.size === 0
      )
        throw new Error(
          `Choose a nonempty ${dataset.modality === "image" ? "PNG/JPEG image" : ".jsonl file"} under 20 MiB.`,
        );
      const sha = Array.from(
        new Uint8Array(
          await crypto.subtle.digest("SHA-256", await file.arrayBuffer()),
        ),
      )
        .map((value) => value.toString(16).padStart(2, "0"))
        .join("");
      const session = await call<UploadSession>("/uploads", {
        method: "POST",
        body: {
          dataset_id: id,
          filename: file.name,
          content_type:
            dataset.modality === "image"
              ? /\.png$/i.test(file.name)
                ? "image/png"
                : "image/jpeg"
              : "application/x-ndjson",
          bytes: file.size,
          sha256: sha,
        },
      });
      const parts = [];
      for (let index = 0; index < session.upload_urls.length; index++) {
        const response = await fetch(session.upload_urls[index], {
          method: "PUT",
          body: file.slice(
            index * session.part_size,
            (index + 1) * session.part_size,
          ),
        });
        if (!response.ok || !response.headers.get("etag"))
          throw new Error(
            "Object storage rejected an upload part. Start a new upload to retry.",
          );
        parts.push({
          part_number: index + 1,
          etag: response.headers.get("etag"),
        });
        setProgress(
          Math.round(((index + 1) / session.upload_urls.length) * 100),
        );
      }
      await call(`/uploads/${session.id}/complete`, {
        method: "POST",
        body: { parts },
      });
      client.invalidateQueries();
      toast("Upload verified and ready for a workflow.");
    });
    setUploading(false);
  }
  return (
    <>
      <PageHeader
        eyebrow="DATASETS"
        title={dataset.name}
        description={
          dataset.description || "Versioned data with complete provenance."
        }
      >
        {organization.scopes.includes("annotations:manage") && (
          <Link
            href={`/curation/new?dataset=${id}`}
            className="button secondary"
          >
            Review & curate
          </Link>
        )}
        {organization.scopes.includes("datasets:write") && (
          <Button variant="secondary" onClick={() => setEdit(true)}>
            Edit details
          </Button>
        )}
        {organization.scopes.includes("runs:execute") && (
          <Link
            href={`/workflows/new?dataset=${id}`}
            className="button primary"
          >
            <GitBranch size={14} />
            Build workflow
          </Link>
        )}
      </PageHeader>
      <div className="detail-meta" style={{ marginTop: -14, marginBottom: 22 }}>
        <span>
          <FileText size={12} />{" "}
          {dataset.modality === "image" ? "Image · PNG/JPEG" : "Text · JSONL"}
        </span>
        <span>
          <Layers3 size={12} /> {versions.data?.items.length || 0} versions
        </span>
        <span className="mono">
          {shortId(id)}
          <Copy value={id} label="Copy dataset ID" />
        </span>
      </div>
      <div className="tabs" role="tablist" aria-label="Dataset views">
        {["Samples", "Versions", "Quality", "Data card", "Lineage"].map(
          (value) => (
            <button
              key={value}
              role="tab"
              aria-selected={tab === value}
              className={`tab ${tab === value ? "active" : ""}`}
              onClick={() => setTab(value)}
            >
              {value}
            </button>
          ),
        )}
      </div>
      <ErrorNotice
        error={action.error || versions.error || samples.error || uploads.error}
      />
      <div className="two-columns">
        <section>
          {tab === "Samples" && (
            <div className="panel">
              <div className="panel-heading">
                <h2>Sample explorer</h2>
                {!!versions.data?.items.length && (
                  <select
                    className="form-input"
                    style={{ width: "auto", fontSize: 11 }}
                    aria-label="Dataset version"
                    value={selected?.id || ""}
                    onChange={(event) => {
                      setVersionId(event.target.value);
                      setOffset(0);
                    }}
                  >
                    {versions.data.items.map((value) => (
                      <option key={value.id} value={value.id}>
                        Version {value.number} · {value.sample_count} samples
                      </option>
                    ))}
                  </select>
                )}
              </div>
              {!samples.data?.items.length ? (
                <Empty
                  icon={FileJson2}
                  title="No published samples yet"
                  description="Upload source data or generate samples in a workflow. They appear here after the quality gates pass."
                />
              ) : (
                <>
                  {samples.data.items.map((sample, index) => (
                    <article
                      className="sample-row"
                      key={sample.sample_id || index}
                    >
                      <header>
                        <span className="mono muted">
                          {String(offset + index + 1).padStart(3, "0")}{" "}
                          <span style={{ marginLeft: 10 }}>
                            {shortId(sample.sample_id || "sample")}
                          </span>
                        </span>
                        <Copy
                          value={JSON.stringify(sample, null, 2)}
                          label="Copy sample"
                        />
                      </header>
                      {dataset.modality === "image" && selected ? (
                        <div className="panel-body">
                          <BoxEditor
                            path={`/v1/datasets/${id}/versions/${selected.id}/samples/${sample.sample_id}/image`}
                            width={
                              (sample.payload.image as { width: number }).width
                            }
                            height={
                              (sample.payload.image as { height: number })
                                .height
                            }
                            categories={
                              sample.annotation?.kind === "boxes"
                                ? [
                                    ...new Set(
                                      sample.annotation.boxes.map(
                                        (box) => box.label,
                                      ),
                                    ),
                                  ]
                                : []
                            }
                            boxes={
                              sample.annotation?.kind === "boxes"
                                ? sample.annotation.boxes
                                : []
                            }
                            onChange={() => {}}
                            readOnly
                          />
                        </div>
                      ) : (
                        <dl>
                          <dt>Prompt</dt>
                          <dd>
                            {String(
                              sample.payload?.prompt ??
                                JSON.stringify(sample.payload),
                            )}
                          </dd>
                          <dt>Response</dt>
                          <dd className="response-text">
                            {String(sample.payload?.response ?? "—")}
                          </dd>
                        </dl>
                      )}
                      {sample.annotation?.kind === "category" && (
                        <div className="detail-meta">
                          <span className="status">
                            {sample.annotation.label}
                          </span>
                          <span>Human-reviewed category</span>
                        </div>
                      )}
                      {!!sample.payload.simulation && selected && (
                        <SimulationSample
                          versionId={selected.id}
                          sampleId={sample.sample_id}
                          metadata={sample.payload.simulation}
                        />
                      )}
                    </article>
                  ))}
                  <div
                    className="panel-footer"
                    style={{ justifyContent: "space-between" }}
                  >
                    <span>
                      {offset + 1}–{Math.min(offset + 10, samples.data.total)}{" "}
                      of {samples.data.total}
                    </span>
                    <div>
                      <Button
                        variant="ghost"
                        disabled={offset === 0}
                        onClick={() => setOffset(Math.max(0, offset - 10))}
                      >
                        Previous
                      </Button>
                      <Button
                        variant="ghost"
                        disabled={samples.data.next_offset === null}
                        onClick={() =>
                          setOffset(samples.data?.next_offset || 0)
                        }
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
          {tab === "Versions" && (
            <div className="panel">
              {!versions.data?.items.length ? (
                <Empty
                  icon={Layers3}
                  title="Your first version is ahead"
                  description="A version is published only after your workflow passes every required gate."
                />
              ) : (
                versions.data.items.map((version) => (
                  <div key={version.id} className="sample-row">
                    <div className="section-row">
                      <div>
                        <h3>Version {version.number}</h3>
                        <small>
                          {version.sample_count} samples ·{" "}
                          {date(version.created_at)}
                        </small>
                      </div>
                      <Button
                        variant="secondary"
                        busy={action.busy}
                        onClick={() =>
                          action.perform(async () => {
                            await saveExport(call, version.id, organization.id);
                            toast("Verified JSONL export downloaded.");
                          })
                        }
                      >
                        <ArrowDownToLine size={13} />
                        Export JSONL
                      </Button>
                      {(["coco", "yolo"] as const)
                        .filter((format) => version.manifest.exports?.[format])
                        .map((format) => (
                          <Button
                            key={format}
                            variant="secondary"
                            busy={action.busy}
                            onClick={() =>
                              action.perform(async () => {
                                await saveExport(
                                  call,
                                  version.id,
                                  organization.id,
                                  format,
                                );
                                toast(
                                  `${format.toUpperCase()} export downloaded.`,
                                );
                              })
                            }
                          >
                            Export {format.toUpperCase()}
                          </Button>
                        ))}
                    </div>
                    <div className="detail-meta mono">
                      <ShieldCheck size={12} />
                      sha256:{shortId(version.manifest_hash)}
                      <Copy
                        value={version.manifest_hash}
                        label="Copy manifest digest"
                      />
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
          {tab === "Quality" &&
            (selected ? (
              <QualityPanel report={selected.manifest.quality} />
            ) : (
              <div className="panel">
                <Empty
                  icon={FileCheck2}
                  title="No quality report yet"
                  description="Schema and duplication checks run before each publication."
                />
              </div>
            ))}
          {tab === "Data card" && (
            <div className="panel">
              <div className="panel-heading">
                <h2>Published data card</h2>
                <ShieldCheck size={14} />
              </div>
              {selected?.manifest.data_card ? (
                <div className="panel-body">
                  <Code value={selected.manifest.data_card} />
                  <p className="muted">
                    Publication approval and review provenance are sealed in the
                    version manifest.
                  </p>
                </div>
              ) : (
                <Empty
                  icon={FileCheck2}
                  title="Document this dataset through review"
                  description="Create a curation session and complete its data card before approving publication."
                />
              )}
            </div>
          )}
          {tab === "Lineage" &&
            (selected ? (
              <div className="panel">
                <div className="panel-heading">
                  <h2>Immutable provenance manifest</h2>
                  <Button
                    variant="ghost"
                    onClick={() =>
                      action.perform(async () => {
                        const value = await call(
                          `/datasets/${id}/versions/${selected.id}/manifest`,
                        );
                        const url = URL.createObjectURL(
                          new Blob([JSON.stringify(value, null, 2)], {
                            type: "application/json",
                          }),
                        );
                        const link = document.createElement("a");
                        link.href = url;
                        link.download = "manifest.json";
                        link.click();
                        setTimeout(() => URL.revokeObjectURL(url), 1000);
                      })
                    }
                  >
                    <ArrowDownToLine size={13} />
                    Download
                  </Button>
                </div>
                <Code value={selected.manifest} />
              </div>
            ) : (
              <div className="panel">
                <Empty
                  icon={GitBranch}
                  title="Every sample has a story"
                  description="Source records, recipe revisions, and content hashes are sealed at publication."
                />
              </div>
            ))}
        </section>
        <aside className="stack">
          {organization.scopes.includes("datasets:write") && (
            <div className="panel">
              <div className="panel-heading">
                <h2>Source data</h2>
                <UploadCloud size={14} className="muted" />
              </div>
              <div className="panel-body">
                <label className="upload-area">
                  <UploadCloud size={23} strokeWidth={1.4} />
                  <strong>
                    {uploading
                      ? `Uploading ${progress}%`
                      : dataset.modality === "image"
                        ? "Add a PNG/JPEG image"
                        : "Add a JSONL source"}
                  </strong>
                  <span>
                    {dataset.modality === "image"
                      ? "PNG/JPEG · 6 MP · 4096 px per edge"
                      : "UTF-8"}{" "}
                    · up to 20 MiB
                  </span>
                  <input
                    type="file"
                    accept={
                      dataset.modality === "image"
                        ? ".png,.jpg,.jpeg"
                        : ".jsonl"
                    }
                    aria-label={
                      dataset.modality === "image"
                        ? "Upload image source"
                        : "Upload JSONL source"
                    }
                    disabled={uploading}
                    onChange={(event) => {
                      if (event.target.files?.[0])
                        upload(event.target.files[0]);
                      event.target.value = "";
                    }}
                  />
                </label>
                {uploads.data?.items.map((value) => (
                  <div className="source-row" key={value.id}>
                    {dataset.modality === "image" &&
                      value.status === "COMPLETED" && (
                        <PrivateImage
                          path={`/v1/uploads/${value.id}/media`}
                          alt={`Verified preview of ${value.filename}`}
                        />
                      )}
                    <FileText size={13} />
                    <span style={{ overflowWrap: "anywhere" }}>
                      {value.filename}
                    </span>
                    <Status value={value.status} />
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="panel">
            <div className="panel-heading">
              <h2>Dataset policy</h2>
              <ShieldCheck size={14} className="muted" />
            </div>
            <div className="panel-body">
              <dl className="key-values" style={{ margin: 0 }}>
                <dt>Training use</dt>
                <dd>
                  {dataset.policy.allowed_training_use
                    ? "Permitted"
                    : "Blocked"}
                </dd>
                <dt>Source</dt>
                <dd>{String(dataset.policy.origin || "Unspecified")}</dd>
                <dt>Published versions</dt>
                <dd>Immutable</dd>
              </dl>
            </div>
            <div className="panel-footer">
              <Info size={12} /> Rights are checked before execution.
            </div>
          </div>
        </aside>
      </div>
      <Modal
        open={edit}
        setOpen={setEdit}
        title="Edit dataset"
        description="Update the dataset identity. Published content stays immutable."
      >
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            const result = await action.perform(() =>
              call(`/datasets/${id}`, {
                method: "PATCH",
                body: { name, description },
              }),
            );
            if (result) {
              setEdit(false);
              client.invalidateQueries();
              toast("Dataset details saved.");
            }
          }}
        >
          <label className="field">
            <span>Name</span>
            <input
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={160}
            />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={4000}
            />
          </label>
          <ErrorNotice error={action.error} />
          <div className="modal-actions">
            <Button
              variant="secondary"
              type="button"
              onClick={() => setEdit(false)}
            >
              Cancel
            </Button>
            <Button busy={action.busy}>Save changes</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

export function QualityPanel({ report }: { report: Quality }) {
  return (
    <div className="panel">
      <div className="panel-heading">
        <h2>Quality report</h2>
        <Status value={report.passed ? "PASS" : "FAIL"} />
      </div>
      <div className="panel-body">
        <div className="check-grid">
          {[
            { name: "Samples checked", value: report.total },
            { name: "Schema valid", value: report.valid },
            { name: "Invalid samples", value: report.invalid },
            { name: "Exact duplicates", value: report.duplicates },
          ].map((item) => (
            <div className="quality-check" key={item.name}>
              <CircleCheck size={15} />
              <span>{item.name}</span>
              <strong style={{ marginLeft: "auto" }}>{item.value}</strong>
            </div>
          ))}
        </div>
        <dl className="key-values">
          <dt>Schema coverage</dt>
          <dd>100%</dd>
          <dt>Duplicate ratio</dt>
          <dd>{(report.duplicate_ratio * 100).toFixed(1)}%</dd>
        </dl>
        <div className="notice" style={{ marginTop: 20, marginBottom: 0 }}>
          <Info size={14} />
          <span>{report.limitations.join(" ")}</span>
        </div>
      </div>
    </div>
  );
}

export function RunsPage() {
  const [status, setStatus] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const query = useResource<Page<Run>>(
    `/runs?limit=20${status ? `&status=${status}` : ""}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    true,
  );
  return (
    <>
      <PageHeader
        title="Runs"
        description="Watch your data take shape. Every step, accounted for."
      >
        <Link href="/workflows" className="button secondary">
          <GitBranch size={14} />
          View workflows
        </Link>
      </PageHeader>
      <div className="toolbar">
        <label className="field" style={{ margin: 0 }}>
          <span className="sr-only">Filter run status</span>
          <select
            aria-label="Filter run status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setCursor(null);
            }}
          >
            <option value="">All statuses</option>
            {[
              "QUEUED",
              "RUNNING",
              "VERIFYING",
              "SUCCEEDED",
              "FAILED",
              "CANCELLED",
            ].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <span className="muted" style={{ fontSize: 11 }}>
          Live status · refreshes automatically
        </span>
      </div>
      <ErrorNotice error={query.error} />
      {query.isPending ? (
        <Loading />
      ) : !query.data?.items.length ? (
        <div className="panel">
          <Empty
            icon={Activity}
            title="No runs here yet"
            description="Launch a workflow to generate or process a dataset."
            action={
              <Link className="button secondary" href="/workflows/new">
                Build a workflow <ArrowUpRight size={13} />
              </Link>
            }
          />
        </div>
      ) : (
        <>
          <div
            className="table-wrap"
            role="region"
            aria-label="Runs table"
            tabIndex={0}
          >
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Samples</th>
                  <th>Internal usage</th>
                  <th>Created</th>
                  <th>
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((run) => (
                  <tr key={run.id}>
                    <td>
                      <Link href={`/runs/${run.id}`} className="cell-title">
                        <GitBranch size={15} />
                        <span className="mono">{shortId(run.id)}</span>
                      </Link>
                    </td>
                    <td>
                      <Status value={run.status} />
                    </td>
                    <td className="mono">
                      {run.processed} / {run.sample_count}
                    </td>
                    <td className="mono">{money(run.spent_usd)}</td>
                    <td className="muted">{date(run.created_at)}</td>
                    <td>
                      <Link
                        href={`/runs/${run.id}`}
                        className="icon-button"
                        aria-label={`Open run ${run.id}`}
                      >
                        <ArrowUpRight size={15} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="table-end">
            <span>{query.data.items.length} runs on this page</span>
            <div>
              {cursor && (
                <Button variant="ghost" onClick={() => setCursor(null)}>
                  First page
                </Button>
              )}
              {query.data.next_cursor && (
                <Button
                  variant="secondary"
                  onClick={() => setCursor(query.data?.next_cursor || null)}
                >
                  Next page
                </Button>
              )}
            </div>
          </div>
        </>
      )}
    </>
  );
}

export function RunDetail({ id }: { id: string }) {
  const query = useResource<Run>(`/runs/${id}`, true);
  const logs = useResource<{
    items: {
      id: string;
      message: string;
      event_type: string;
      created_at: string;
    }[];
  }>(`/runs/${id}/events`, true);
  const { call, organization, toast } = useWorkspace();
  const action = useAction();
  const client = useQueryClient();
  const [filter, setFilter] = useState("");
  if (query.isPending) return <Loading />;
  if (!query.data) return <ErrorNotice error={query.error} />;
  const run = query.data;
  const terminal = ["SUCCEEDED", "FAILED", "CANCELLED"].includes(run.status);
  return (
    <>
      <PageHeader
        eyebrow="WORKFLOW RUN"
        title={shortId(id)}
        description="A complete record of execution, quality, and output."
      >
        {!terminal && organization.scopes.includes("runs:execute") && (
          <Button
            variant="secondary"
            disabled={run.cancel_requested}
            busy={action.busy}
            onClick={() =>
              action.perform(async () => {
                await call(`/runs/${id}/cancel`, { method: "POST" });
                client.invalidateQueries();
                toast("Cancellation requested.");
              })
            }
          >
            <X size={13} />
            {run.cancel_requested ? "Cancellation requested" : "Cancel run"}
          </Button>
        )}
        {["FAILED", "CANCELLED"].includes(run.status) &&
          organization.scopes.includes("runs:execute") && (
            <Button
              variant="secondary"
              busy={action.busy}
              onClick={() =>
                action.perform(async () => {
                  const result = await call<Run>(`/runs/${id}/retry`, {
                    method: "POST",
                  });
                  location.assign(`/runs/${result.id}`);
                })
              }
            >
              <RefreshCw size={13} />
              Retry run
            </Button>
          )}
        {run.version && (
          <Button
            busy={action.busy}
            onClick={() =>
              action.perform(async () => {
                await saveExport(call, run.version!.id, organization.id);
                toast("Verified JSONL export downloaded.");
              })
            }
          >
            <ArrowDownToLine size={13} />
            Export JSONL
          </Button>
        )}
      </PageHeader>
      <div className="detail-meta" style={{ marginTop: -13, marginBottom: 25 }}>
        <Status value={run.status} />
        <span>
          <Clock3 size={12} />
          {date(run.created_at)}
        </span>
        <Link href={`/datasets/${run.dataset_id}`} className="text-link">
          <Database size={12} />
          View dataset <ArrowUpRight size={12} />
        </Link>
        <Copy value={id} label="Copy run ID" />
      </div>
      <ErrorNotice error={action.error || logs.error} />
      {run.error && <ErrorNotice error={new Error(run.error)} />}
      <div className="stats">
        <div className="stat">
          <div className="stat-title">
            Samples processed
            <FileText size={14} />
          </div>
          <div className="stat-number">{run.processed.toLocaleString()}</div>
          <div className="stat-note">
            of {run.sample_count.toLocaleString()} requested
          </div>
        </div>
        <div className="stat">
          <div className="stat-title">
            Quality gate
            <ShieldCheck size={14} />
          </div>
          <div className="stat-number" style={{ fontSize: 24 }}>
            {run.quality
              ? run.quality.passed
                ? "Passed"
                : "Failed"
              : "Pending"}
          </div>
          <div className="stat-note">Schema, integrity & duplication</div>
        </div>
        <div className="stat">
          <div className="stat-title">
            Internal usage
            <Cpu size={14} />
          </div>
          <div className="stat-number">{money(run.spent_usd)}</div>
          <div className="stat-note">Nonbillable local rate card</div>
        </div>
        <div className="stat">
          <div className="stat-title">
            External charges
            <HardDrive size={14} />
          </div>
          <div className="stat-number">$0</div>
          <div className="stat-note">Local execution only</div>
        </div>
      </div>
      <div className="two-columns">
        <div className="stack">
          <div className="panel">
            <div className="panel-heading">
              <h2>Execution timeline</h2>
              <Status value={run.status} />
            </div>
            <div className="log-toolbar">
              <input
                aria-label="Filter run logs"
                placeholder="Filter logs…"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
              />
              <Button
                variant="ghost"
                onClick={() => {
                  const data = JSON.stringify(logs.data?.items || [], null, 2);
                  const url = URL.createObjectURL(
                    new Blob([data], { type: "application/json" }),
                  );
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `${id}-logs.json`;
                  a.click();
                  setTimeout(() => URL.revokeObjectURL(url), 1000);
                }}
              >
                <ArrowDownToLine size={12} />
                Logs
              </Button>
            </div>
            <div className="timeline" aria-live="polite">
              {logs.data?.items
                .filter((value) =>
                  value.message.toLowerCase().includes(filter.toLowerCase()),
                )
                .map((value) => (
                  <div className="timeline-item" key={value.id}>
                    <time>
                      {new Date(value.created_at).toLocaleTimeString()}
                    </time>
                    {value.message}
                  </div>
                ))}
            </div>
          </div>
          {run.quality && <QualityPanel report={run.quality} />}
        </div>
        <aside className="stack">
          <div className="panel">
            <div className="panel-heading">
              <h2>Run details</h2>
            </div>
            <div className="panel-body">
              <dl className="key-values" style={{ margin: 0 }}>
                <dt>Executor</dt>
                <dd>Local CPU</dd>
                <dt>Budget cap</dt>
                <dd>{money(run.max_budget_usd)}</dd>
                <dt>Remaining reservation</dt>
                <dd>{money(run.reserved_usd)}</dd>
                <dt>Recipe revision</dt>
                <dd>{shortId(run.recipe_revision_id)}</dd>
              </dl>
              <div className="progress-track">
                <div
                  style={{
                    width: `${run.sample_count ? (run.processed / run.sample_count) * 100 : 0}%`,
                  }}
                />
              </div>
              <small>
                {run.processed} / {run.sample_count} samples persisted
              </small>
            </div>
          </div>
          {run.version && (
            <div className="panel">
              <div className="panel-heading">
                <h2>Published output</h2>
                <Check size={14} style={{ color: "var(--green)" }} />
              </div>
              <div className="panel-body">
                <h3>Version {run.version.number}</h3>
                <p
                  className="muted"
                  style={{ fontSize: 12, margin: "6px 0 15px" }}
                >
                  {run.version.sample_count} samples · immutable
                </p>
                <div className="mono" style={{ overflowWrap: "anywhere" }}>
                  sha256:{run.version.manifest_hash}
                </div>
                <TextLink href={`/datasets/${run.dataset_id}`}>
                  Inspect dataset
                </TextLink>
              </div>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}
