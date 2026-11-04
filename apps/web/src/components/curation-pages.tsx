"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCheck,
  ClipboardCheck,
  FileCheck2,
  Filter,
  ListChecks,
  Plus,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import type { Dataset, Page, Recipe, Run, Upload, Version } from "@/lib/api";
import { date, money, shortId } from "@/lib/api";
import type {
  Annotation,
  Box,
  Curation,
  QualityProfile,
  Reviewer,
  Task,
} from "@/lib/curation";
import { cardFields } from "@/lib/curation";
import { BoxEditor } from "./annotation-image";
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

export function CurationsPage() {
  const { organization } = useWorkspace();
  const [cursor, setCursor] = useState("");
  const query = useResource<Page<Curation>>(
    `/curations?limit=25${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
  );
  return (
    <>
      <PageHeader
        title="Curation"
        description="Turn source data into a dataset your team has reviewed."
      >
        <Link href="/curation/profiles" className="button secondary">
          <Filter size={14} />
          Quality profiles
        </Link>
        {organization.scopes.includes("annotations:manage") && (
          <Link href="/curation/new" className="button primary">
            <Plus size={14} />
            New review session
          </Link>
        )}
      </PageHeader>
      <div className="notice">
        <ShieldCheck size={16} />
        <span>
          Review decisions keep their author and history. Only a passing,
          approved snapshot can be published.
        </span>
      </div>
      <ErrorNotice error={query.error} />
      {query.isPending ? (
        <Loading />
      ) : !query.data?.items.length ? (
        <div className="panel">
          <Empty
            icon={ClipboardCheck}
            title="Good data deserves a second look"
            description="Choose a source, set a quality profile, and ask your team to review its labels."
          />
        </div>
      ) : (
        <div className="panel">
          <div className="panel-heading">
            <h2>Review sessions</h2>
            <span className="muted">
              {query.data.items.length} on this page
            </span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Session</th>
                  <th>Source samples</th>
                  <th>Review policy</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link
                        href={`/curation/${item.id}`}
                        className="resource-name"
                      >
                        <span className="resource-icon">
                          <ListChecks size={16} />
                        </span>
                        <span>
                          {item.name}
                          <span className="cell-subtitle mono">
                            {shortId(item.id)}
                          </span>
                        </span>
                      </Link>
                    </td>
                    <td>{Number(item.dedupe_report.total)}</td>
                    <td>
                      {item.required_reviews}{" "}
                      {item.required_reviews === 1
                        ? "reviewer"
                        : "independent reviewers"}
                    </td>
                    <td>
                      <Status value={item.state} />
                    </td>
                    <td className="muted">{date(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="table-end">
            <span>Labels stay linked to their source.</span>
            <div>
              {cursor && (
                <Button variant="ghost" onClick={() => setCursor("")}>
                  First page
                </Button>
              )}
              {query.data.next_cursor && (
                <Button
                  variant="secondary"
                  onClick={() => setCursor(query.data?.next_cursor || "")}
                >
                  Next page
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function ProfileDialog({
  open,
  setOpen,
  onCreated,
  modality = "text",
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
  onCreated?: (profile: QualityProfile) => void;
  modality?: string;
}) {
  const { call, toast } = useWorkspace();
  const client = useQueryClient();
  const action = useAction();
  const [name, setName] = useState("");
  const [kind, setKind] = useState(modality);
  const [dedupe, setDedupe] = useState("exact");
  const [minimum, setMinimum] = useState(1);
  const [acceptance, setAcceptance] = useState(50);
  const [exactMax, setExactMax] = useState(0);
  const [nearMax, setNearMax] = useState(100);
  const [similarity, setSimilarity] = useState(85);
  const [distance, setDistance] = useState(4);
  return (
    <Modal
      open={open}
      setOpen={setOpen}
      title="Create quality profile"
      description="Profiles are immutable. Create another profile when your criteria change."
    >
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          const result = await action.perform(() =>
            call<QualityProfile>("/quality-profiles", {
              method: "POST",
              body: {
                name,
                modality: kind,
                config: {
                  dedupe,
                  minimum_samples: minimum,
                  minimum_acceptance_ratio: acceptance / 100,
                  max_duplicate_ratio: exactMax / 100,
                  max_near_duplicate_ratio: nearMax / 100,
                  text_similarity: similarity / 100,
                  image_hamming_distance: distance,
                },
              },
            }),
          );
          if (result) {
            client.invalidateQueries();
            setOpen(false);
            toast("Quality profile saved.");
            onCreated?.(result);
          }
        }}
      >
        <label className="field">
          <span>Profile name</span>
          <input
            required
            maxLength={160}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Human-reviewed training set"
          />
        </label>
        <div className="field-row">
          <label className="field">
            <span>Profile modality</span>
            <select
              value={kind}
              onChange={(event) => setKind(event.target.value)}
            >
              <option value="text">Text</option>
              <option value="image">Image</option>
            </select>
          </label>
          <label className="field">
            <span>Duplicate removal</span>
            <select
              value={dedupe}
              onChange={(event) => setDedupe(event.target.value)}
            >
              <option value="none">Keep all; measure only</option>
              <option value="exact">Remove exact duplicates</option>
              <option value="near">Remove exact and near duplicates</option>
            </select>
          </label>
        </div>
        <div className="field-row">
          <label className="field">
            <span>Minimum accepted samples</span>
            <input
              type="number"
              required
              min={1}
              max={500}
              value={minimum}
              onChange={(event) => setMinimum(Number(event.target.value))}
            />
          </label>
          <label className="field">
            <span>Minimum acceptance %</span>
            <input
              type="number"
              required
              min={0}
              max={100}
              step="any"
              value={acceptance}
              onChange={(event) => setAcceptance(Number(event.target.value))}
            />
          </label>
        </div>
        <div className="field-row">
          <label className="field">
            <span>Maximum exact duplicate %</span>
            <input
              type="number"
              required
              min={0}
              max={100}
              step="any"
              value={exactMax}
              onChange={(event) => setExactMax(Number(event.target.value))}
            />
          </label>
          <label className="field">
            <span>Maximum near duplicate %</span>
            <input
              type="number"
              required
              min={0}
              max={100}
              step="any"
              value={nearMax}
              onChange={(event) => setNearMax(Number(event.target.value))}
            />
          </label>
        </div>
        {kind === "text" ? (
          <label className="field">
            <span>Lexical similarity threshold %</span>
            <input
              type="number"
              required
              min={50}
              max={100}
              step="any"
              value={similarity}
              onChange={(event) => setSimilarity(Number(event.target.value))}
            />
            <small>
              Jaccard similarity of normalized word trigrams. This does not
              measure semantic equivalence.
            </small>
          </label>
        ) : (
          <label className="field">
            <span>Perceptual hash distance</span>
            <input
              type="number"
              required
              min={0}
              max={8}
              value={distance}
              onChange={(event) => setDistance(Number(event.target.value))}
            />
            <small>
              Maximum differing bits in a 64-bit dHash. Visually different
              images can still collide.
            </small>
          </label>
        )}
        <ErrorNotice error={action.error} />
        <div className="modal-actions">
          <Button
            type="button"
            variant="secondary"
            onClick={() => setOpen(false)}
          >
            Cancel
          </Button>
          <Button type="submit" busy={action.busy}>
            Save quality profile
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function QualityProfilesPage() {
  const { organization } = useWorkspace();
  const [create, setCreate] = useState(false);
  const [cursor, setCursor] = useState("");
  const query = useResource<Page<QualityProfile>>(
    `/quality-profiles?limit=25${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
  );
  return (
    <>
      <PageHeader
        title="Quality profiles"
        description="Reusable, immutable criteria for a reviewed dataset."
      >
        <Link href="/curation" className="button secondary">
          Review sessions
        </Link>
        {organization.scopes.includes("annotations:manage") && (
          <Button onClick={() => setCreate(true)}>
            <Plus size={14} />
            Create quality profile
          </Button>
        )}
      </PageHeader>
      <ErrorNotice error={query.error} />
      {query.isPending ? (
        <Loading />
      ) : !query.data?.items.length ? (
        <div className="panel">
          <Empty
            icon={Filter}
            title="Define what ready means"
            description="Choose duplicate handling, minimum acceptance, and publication thresholds."
          />
        </div>
      ) : (
        <div className="profile-grid">
          {query.data.items.map((profile) => (
            <section className="panel" key={profile.id}>
              <div className="panel-heading">
                <h2>{profile.name}</h2>
                <span className="status">{profile.modality}</span>
              </div>
              <div className="panel-body">
                <dl className="key-values">
                  <dt>Removal</dt>
                  <dd>{String(profile.config.dedupe)}</dd>
                  <dt>Minimum samples</dt>
                  <dd>{Number(profile.config.minimum_samples)}</dd>
                  <dt>Minimum acceptance</dt>
                  <dd>
                    {Number(profile.config.minimum_acceptance_ratio) * 100}%
                  </dd>
                  <dt>Maximum exact duplicates</dt>
                  <dd>{Number(profile.config.max_duplicate_ratio) * 100}%</dd>
                  <dt>Maximum near duplicates</dt>
                  <dd>
                    {Number(profile.config.max_near_duplicate_ratio) * 100}%
                  </dd>
                  <dt>
                    {profile.modality === "text"
                      ? "Lexical threshold"
                      : "dHash distance"}
                  </dt>
                  <dd>
                    {profile.modality === "text"
                      ? `${Number(profile.config.text_similarity) * 100}%`
                      : Number(profile.config.image_hamming_distance)}
                  </dd>
                </dl>
              </div>
              <div className="panel-footer">
                <ShieldCheck size={12} />
                Immutable · {date(profile.created_at)}
              </div>
            </section>
          ))}
        </div>
      )}
      <div className="table-end">
        <span>Every accepted payload and annotation must pass validation.</span>
        <div>
          {cursor && (
            <Button variant="ghost" onClick={() => setCursor("")}>
              First page
            </Button>
          )}
          {query.data?.next_cursor && (
            <Button
              variant="secondary"
              onClick={() => setCursor(query.data?.next_cursor || "")}
            >
              Next page
            </Button>
          )}
        </div>
      </div>
      {create && <ProfileDialog open={create} setOpen={setCreate} />}
    </>
  );
}

export function CreateCurationPage() {
  const { call, project, organization, toast } = useWorkspace();
  const params = useSearchParams();
  const router = useRouter();
  const action = useAction();
  const [datasetId, setDatasetId] = useState(params.get("dataset") || "");
  const [name, setName] = useState("");
  const [profileId, setProfileId] = useState("");
  const [categories, setCategories] = useState("object, other");
  const [reviewCount, setReviewCount] = useState(2);
  const [sourceKind, setSourceKind] = useState("uploads");
  const [versionId, setVersionId] = useState("");
  const [uploadIds, setUploadIds] = useState<string[]>([]);
  const [createProfile, setCreateProfile] = useState(false);
  const datasets = useResource<Page<Dataset>>(
    `/datasets?limit=100&project_id=${project}`,
    false,
    !!project,
  );
  const dataset = useResource<Dataset>(
    `/datasets/${datasetId}`,
    false,
    !!datasetId,
  );
  const modality = dataset.data?.modality || "text";
  const profiles = useResource<Page<QualityProfile>>(
    `/quality-profiles?limit=100&modality=${modality}`,
  );
  const uploads = useResource<Page<Upload>>(
    `/uploads?dataset_id=${datasetId}`,
    false,
    !!datasetId,
  );
  const versions = useResource<Page<Version>>(
    `/datasets/${datasetId}/versions`,
    false,
    !!datasetId,
  );
  if (!organization.scopes.includes("annotations:manage"))
    return (
      <div className="notice">
        Creating a review session requires annotation management permission.
      </div>
    );
  return (
    <>
      <PageHeader
        eyebrow="CURATION"
        title="New review session"
        description="Freeze the source, define its labels, and choose how it will be reviewed."
      >
        <Link href="/curation" className="button secondary">
          All sessions
        </Link>
      </PageHeader>
      <ErrorNotice
        error={
          datasets.error ||
          dataset.error ||
          profiles.error ||
          uploads.error ||
          versions.error
        }
      />
      <div className="two-columns">
        <section className="panel">
          <div className="panel-heading">
            <h2>Session setup</h2>
          </div>
          <form
            className="panel-body"
            onSubmit={async (event) => {
              event.preventDefault();
              const result = await action.perform(() =>
                call<Curation>("/curations", {
                  method: "POST",
                  body: {
                    name,
                    dataset_id: datasetId,
                    profile_id: profileId,
                    categories: categories
                      .split(",")
                      .map((item) => item.trim()),
                    required_reviews: reviewCount,
                    ...(sourceKind === "version"
                      ? { source_version_id: versionId }
                      : { upload_ids: uploadIds }),
                  },
                }),
              );
              if (result) {
                toast("Review session created.");
                router.push(`/curation/${result.id}`);
              }
            }}
          >
            <label className="field">
              <span>Session name</span>
              <input
                required
                maxLength={160}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. November training-set review"
              />
            </label>
            <label className="field">
              <span>Review dataset</span>
              <select
                required
                value={datasetId}
                onChange={(event) => {
                  setDatasetId(event.target.value);
                  setUploadIds([]);
                  setVersionId("");
                  setProfileId("");
                }}
              >
                <option value="">Choose a dataset</option>
                {dataset.data &&
                  !datasets.data?.items.some(
                    (item) => item.id === datasetId,
                  ) && <option value={datasetId}>{dataset.data.name}</option>}
                {datasets.data?.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {item.modality}
                  </option>
                ))}
              </select>
            </label>
            <div className="field-row">
              <label className="field">
                <span>Quality profile</span>
                <select
                  required
                  value={profileId}
                  onChange={(event) => setProfileId(event.target.value)}
                >
                  <option value="">Choose a {modality} profile</option>
                  {profiles.data?.items.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="field" style={{ justifyContent: "end" }}>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setCreateProfile(true)}
                >
                  Create quality profile
                </Button>
              </div>
            </div>
            <label className="field">
              <span>Label categories</span>
              <input
                required
                maxLength={8100}
                value={categories}
                onChange={(event) => setCategories(event.target.value)}
              />
              <small>
                Comma-separated category names. Text uses one category; images
                use boxes with these categories.
              </small>
            </label>
            <label className="field">
              <span>Review policy</span>
              <select
                value={reviewCount}
                onChange={(event) => setReviewCount(Number(event.target.value))}
              >
                <option value={2}>
                  Two independent reviewers; adjudicate disagreements
                </option>
                <option value={1}>
                  One reviewer; no independent consensus
                </option>
              </select>
            </label>
            <label className="field">
              <span>Review source</span>
              <select
                value={sourceKind}
                onChange={(event) => setSourceKind(event.target.value)}
              >
                <option value="uploads">Completed uploads</option>
                <option value="version">Published version</option>
              </select>
            </label>
            {sourceKind === "version" ? (
              <label className="field">
                <span>Source version</span>
                <select
                  required
                  value={versionId}
                  onChange={(event) => setVersionId(event.target.value)}
                >
                  <option value="">Choose a version</option>
                  {versions.data?.items.map((item) => (
                    <option key={item.id} value={item.id}>
                      Version {item.number} · {item.sample_count} samples
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <fieldset className="source-selection">
                <legend>Source uploads</legend>
                {uploads.data?.items
                  .filter((item) => item.status === "COMPLETED")
                  .map((item) => (
                    <label className="check-field" key={item.id}>
                      <input
                        type="checkbox"
                        checked={uploadIds.includes(item.id)}
                        onChange={(event) =>
                          setUploadIds(
                            event.target.checked
                              ? [...uploadIds, item.id]
                              : uploadIds.filter((id) => id !== item.id),
                          )
                        }
                      />
                      <span>
                        {item.filename}
                        <small>{item.sample_count} samples</small>
                      </span>
                    </label>
                  ))}
                {!uploads.data?.items.some(
                  (item) => item.status === "COMPLETED",
                ) && (
                  <p className="muted">
                    Choose a dataset with a completed upload, or{" "}
                    <Link
                      className="text-link"
                      href={datasetId ? `/datasets/${datasetId}` : "/datasets"}
                    >
                      upload a source
                    </Link>
                    .
                  </p>
                )}
              </fieldset>
            )}
            <ErrorNotice error={action.error} />
            <div className="modal-actions">
              <Button
                type="submit"
                busy={action.busy}
                disabled={
                  !datasetId ||
                  !profileId ||
                  (sourceKind === "version" ? !versionId : !uploadIds.length)
                }
              >
                Create review session
                <ArrowRight size={14} />
              </Button>
            </div>
          </form>
        </section>
        <aside className="stack" aria-label="Curation guidance">
          <div className="panel">
            <div className="panel-heading">
              <h2>From source to approved</h2>
              <CheckCheck size={16} />
            </div>
            <div className="panel-body curation-steps">
              <p>
                <strong>01 · Clean</strong>Reproducible exact and near duplicate
                checks keep their source-row evidence.
              </p>
              <p>
                <strong>02 · Review</strong>Assigned reviewers edit labels.
                Independent votes establish agreement; conflicts go to
                adjudication.
              </p>
              <p>
                <strong>03 · Document</strong>Complete the data card and inspect
                every blocking quality check.
              </p>
              <p>
                <strong>04 · Publish</strong>Approve an immutable snapshot, then
                run it through the durable worker.
              </p>
            </div>
          </div>
          <div className="notice">
            Local sessions support 500 samples and 20 MiB of source data.
            Agreement is a review metric, not measured accuracy.
          </div>
        </aside>
      </div>
      {createProfile && (
        <ProfileDialog
          key={modality}
          modality={modality}
          open={createProfile}
          setOpen={setCreateProfile}
          onCreated={(profile) => {
            if (profile.modality === modality) setProfileId(profile.id);
          }}
        />
      )}
    </>
  );
}

export function CurationDetail({ id }: { id: string }) {
  const query = useResource<Curation>(`/curations/${id}`);
  if (query.isPending) return <Loading />;
  if (!query.data) return <ErrorNotice error={query.error} />;
  return (
    <CurationWorkspace
      key={`${id}-${query.data.revision}`}
      curation={query.data}
    />
  );
}

function CurationWorkspace({ curation }: { curation: Curation }) {
  const { call, organization, toast } = useWorkspace();
  const client = useQueryClient();
  const router = useRouter();
  const action = useAction();
  const [status, setStatus] = useState("");
  const [mine, setMine] = useState(false);
  const { session } = useWorkspace();
  const [cursor, setCursor] = useState("");
  const [card, setCard] = useState<Record<string, string>>(
    Object.fromEntries(
      cardFields.map(([field]) => [
        field,
        String(curation.data_card[field] || ""),
      ]),
    ),
  );
  const [publication, setPublication] = useState<{
    revision: string;
    estimate: number;
  } | null>(null);
  const [budget, setBudget] = useState("1");
  const tasks = useResource<Page<Task>>(
    `/annotation-tasks?curation_id=${curation.id}&limit=25${status ? `&status=${status}` : ""}${mine ? `&assigned_to=${session.user.id}` : ""}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
  );
  const quality = curation.quality;
  const canManage = organization.scopes.includes("annotations:manage");
  const isOpen = curation.state === "OPEN";
  async function preparePublication() {
    await action.perform(async () => {
      const accepted = quality?.accepted || 1;
      const recipe = await call<Recipe>("/recipes", {
        method: "POST",
        body: {
          project_id: (await call<Dataset>(`/datasets/${curation.dataset_id}`))
            .project_id,
          definition: {
            name: `Reviewed: ${curation.name}`.slice(0, 160),
            schema_version: "1.0",
            nodes: [
              {
                id: "source",
                type: "curate",
                config: { curation_id: curation.id },
              },
              {
                id: "quality",
                type: "validate",
                config: {
                  minimum_samples: accepted,
                  max_duplicate_ratio: Number(
                    (curation.dedupe_report.config &&
                      (curation.dedupe_report.config as Record<string, unknown>)
                        .max_duplicate_ratio) ||
                      0,
                  ),
                  max_invalid_ratio: 0,
                },
              },
              { id: "publish", type: "publish", config: {} },
            ],
            edges: [
              { from: "source", to: "quality" },
              { from: "quality", to: "publish" },
            ],
            budget: { currency: "USD", maximum: 1000 },
          },
        },
      });
      const estimate = await call<{ internal_estimate_usd: number }>(
        `/recipes/${recipe.id}/estimate`,
        { method: "POST" },
      );
      setBudget(String(Math.max(1, estimate.internal_estimate_usd)));
      setPublication({
        revision: recipe.revision!.id,
        estimate: estimate.internal_estimate_usd,
      });
    });
  }
  return (
    <>
      <PageHeader
        eyebrow="CURATION"
        title={curation.name}
        description={`${curation.required_reviews} ${curation.required_reviews === 1 ? "reviewer" : "independent reviewers"} · ${curation.categories.join(", ")}`}
      >
        <Button variant="secondary" onClick={() => client.invalidateQueries()}>
          <RefreshCw size={13} />
          Refresh reviews
        </Button>
        <Link
          href={`/datasets/${curation.dataset_id}`}
          className="button secondary"
        >
          View dataset
        </Link>
        {isOpen && canManage && (
          <Button
            busy={action.busy}
            disabled={!quality?.passed}
            onClick={() =>
              action.perform(async () => {
                await call(`/curations/${curation.id}/freeze`, {
                  method: "POST",
                  body: {
                    expected_revision: curation.revision,
                    approved_for_publication: true,
                  },
                });
                client.invalidateQueries();
                toast("Review snapshot approved and frozen.");
              })
            }
          >
            <ShieldCheck size={14} />
            Approve review snapshot
          </Button>
        )}
        {!isOpen && organization.scopes.includes("runs:execute") && (
          <Button busy={action.busy} onClick={preparePublication}>
            <Plus size={14} />
            Publish reviewed version
          </Button>
        )}
      </PageHeader>
      <div className="detail-meta" style={{ marginBottom: 22 }}>
        <Status value={curation.state} />
        <span className="mono">{shortId(curation.id)}</span>
        {!isOpen && (
          <span>
            Approved {curation.frozen_at ? date(curation.frozen_at) : ""} ·
            immutable review evidence
          </span>
        )}
      </div>
      <ErrorNotice error={action.error || tasks.error} />
      <div className="stats curation-stats">
        {[
          [
            "Accepted samples",
            `${quality?.accepted || 0} / ${quality?.eligible || 0}`,
            "Eligible after duplicate removal",
          ],
          [
            "Review coverage",
            `${Math.round((quality?.review_coverage || 0) * 100)}%`,
            `${quality?.pending || 0} tasks unresolved`,
          ],
          [
            "Duplicates removed",
            String(quality?.excluded || 0),
            `${Number(curation.dedupe_report.exact_duplicates)} exact · ${Number(curation.dedupe_report.near_duplicates)} near detected`,
          ],
          [
            "Reviewer agreement",
            quality?.agreement.ratio == null
              ? "—"
              : `${Math.round(quality.agreement.ratio * 100)}%`,
            `${quality?.agreement.paired_tasks || 0} paired tasks; not accuracy`,
          ],
        ].map(([title, value, note]) => (
          <div className="stat" key={title}>
            <div className="stat-title">{title}</div>
            <div className="stat-number">{value}</div>
            <div className="stat-note">{note}</div>
          </div>
        ))}
      </div>
      {quality && (
        <div className={`curation-gate ${quality.passed ? "gate-pass" : ""}`}>
          <FileCheck2 size={19} />
          <div>
            <strong>
              {quality.passed
                ? "Review quality gate passed"
                : "Publication is blocked"}
            </strong>
            {quality.reasons.length ? (
              <ul>
                {quality.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            ) : (
              <p>
                All required reviews, schema, label, duplicate, data-card and
                source-use checks pass.
              </p>
            )}
          </div>
        </div>
      )}
      <div className="two-columns">
        <section className="stack">
          <div className="panel">
            <div className="panel-heading">
              <h2>Review queue</h2>
              <span className="muted">
                {tasks.data?.items.length || 0} on this page
              </span>
            </div>
            <div className="toolbar curation-toolbar">
              <select
                className="form-input"
                aria-label="Task status"
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value);
                  setCursor("");
                }}
              >
                <option value="">All statuses</option>
                {[
                  "NEW",
                  "NEEDS_REVIEW",
                  "NEEDS_ADJUDICATION",
                  "ACCEPTED",
                  "REJECTED",
                  "ADJUDICATED",
                  "EXCLUDED",
                ].map((value) => (
                  <option key={value} value={value}>
                    {value.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={mine}
                  onChange={(event) => {
                    setMine(event.target.checked);
                    setCursor("");
                  }}
                />
                <span>Assigned to me</span>
              </label>
            </div>
            {tasks.isPending ? (
              <Loading />
            ) : !tasks.data?.items.length ? (
              <Empty
                icon={ListChecks}
                title="No tasks match these filters"
                description="Change the status or assignment filter to see more tasks."
              />
            ) : (
              <div className="compact-list">
                {tasks.data.items.map((task) => (
                  <Link href={`/curation/tasks/${task.id}`} key={task.id}>
                    <span className="resource-icon">
                      <ClipboardCheck size={16} />
                    </span>
                    <div>
                      <strong>Sample {task.sample_index + 1}</strong>
                      <div className="cell-subtitle">
                        {task.excluded_reason ||
                          `Round ${task.round} · revision ${task.revision}`}
                      </div>
                    </div>
                    <Status value={task.status} />
                    <ArrowRight size={13} />
                  </Link>
                ))}
              </div>
            )}
            <div className="table-end">
              <span>Conflicting edits require a refresh.</span>
              <div>
                {cursor && (
                  <Button variant="ghost" onClick={() => setCursor("")}>
                    First page
                  </Button>
                )}
                {tasks.data?.next_cursor && (
                  <Button
                    variant="secondary"
                    onClick={() => setCursor(tasks.data?.next_cursor || "")}
                  >
                    Next page
                  </Button>
                )}
              </div>
            </div>
          </div>
          <details className="panel curation-details">
            <summary>Reproducible deduplication report</summary>
            <Code value={curation.dedupe_report} />
          </details>
          <details className="panel curation-details">
            <summary>Full quality report</summary>
            <Code value={quality} />
          </details>
        </section>
        <aside className="stack" aria-label="Data card and review policy">
          <section className="panel">
            <div className="panel-heading">
              <h2>Data card</h2>
              <ShieldCheck size={14} />
            </div>
            <form
              className="panel-body"
              onSubmit={async (event) => {
                event.preventDefault();
                const result = await action.perform(() =>
                  call(`/curations/${curation.id}/data-card`, {
                    method: "PATCH",
                    body: {
                      expected_revision: curation.revision,
                      data_card: card,
                    },
                  }),
                );
                if (result) {
                  client.invalidateQueries();
                  toast("Data card saved.");
                }
              }}
            >
              {cardFields.map(([field, label]) => (
                <label className="field" key={field}>
                  <span>{label}</span>
                  <textarea
                    required
                    maxLength={4000}
                    rows={2}
                    readOnly={!isOpen || !canManage}
                    value={card[field]}
                    onChange={(event) =>
                      setCard({ ...card, [field]: event.target.value })
                    }
                  />
                </label>
              ))}
              {isOpen && canManage && (
                <Button type="submit" busy={action.busy} variant="secondary">
                  Save data card
                </Button>
              )}
            </form>
          </section>
          <div className="notice">
            Human agreement does not establish ground-truth accuracy. Near
            duplicates are lexical or perceptual matches; no model confidence is
            used.
          </div>
        </aside>
      </div>
      <Modal
        open={!!publication}
        setOpen={(open) => {
          if (!open) setPublication(null);
        }}
        title="Publish reviewed version"
        description="The durable worker will verify the frozen snapshot and publish an immutable dataset version."
      >
        <dl className="key-values">
          <dt>Accepted samples</dt>
          <dd>{quality?.accepted}</dd>
          <dt>Internal estimate</dt>
          <dd>{money(publication?.estimate || 0)}</dd>
          <dt>External cost</dt>
          <dd>$0.00</dd>
        </dl>
        <p className="muted">
          Local usage is nonbillable. The run and organization budget limits
          still apply.
        </p>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            if (!publication) return;
            const run = await action.perform(() =>
              call<Run>("/runs", {
                method: "POST",
                body: {
                  dataset_id: curation.dataset_id,
                  recipe_revision_id: publication.revision,
                  max_budget_usd: budget,
                },
              }),
            );
            if (run) {
              client.invalidateQueries();
              router.push(`/runs/${run.id}`);
            }
          }}
        >
          <label className="field">
            <span>Publication budget USD</span>
            <input
              required
              type="number"
              min={0}
              max={1000}
              step="0.000001"
              value={budget}
              onChange={(event) => setBudget(event.target.value)}
            />
          </label>
          <ErrorNotice error={action.error} />
          <div className="modal-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setPublication(null)}
            >
              Cancel
            </Button>
            <Button type="submit" busy={action.busy}>
              Confirm publication
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

export function AnnotationTaskPage({ id }: { id: string }) {
  const query = useResource<Task>(`/annotation-tasks/${id}`);
  if (query.isPending) return <Loading />;
  if (!query.data) return <ErrorNotice error={query.error} />;
  return (
    <TaskWorkspace key={`${id}-${query.data.revision}`} task={query.data} />
  );
}

function TaskWorkspace({ task }: { task: Task }) {
  const { call, organization, session, toast } = useWorkspace();
  const client = useQueryClient();
  const action = useAction();
  const reviewers = useResource<{ items: Reviewer[] }>(
    "/annotations/reviewers",
  );
  const categories = task.categories || [];
  const [label, setLabel] = useState(
    task.annotation?.kind === "category"
      ? task.annotation.label
      : categories[0],
  );
  const [boxes, setBoxes] = useState<Box[]>(
    task.annotation?.kind === "boxes" ? task.annotation.boxes : [],
  );
  const [note, setNote] = useState("");
  const [assignment, setAssignment] = useState(task.assigned_to || "");
  const isOpen = task.curation_state === "OPEN";
  const needsAdjudication = task.status === "NEEDS_ADJUDICATION";
  const currentVoters = task.reviews
    .filter(
      (review) =>
        review.round === task.round &&
        ["accept", "reject"].includes(review.decision),
    )
    .map((review) => review.user_id);
  const mayAdjudicate =
    organization.scopes.includes("annotations:adjudicate") &&
    !currentVoters.includes(session.user.id);
  const unresolved = ["NEW", "NEEDS_REVIEW"].includes(task.status);
  const assignedElsewhere =
    !!task.assigned_to && task.assigned_to !== session.user.id;
  const mayReview =
    isOpen &&
    organization.scopes.includes("annotations:review") &&
    (needsAdjudication ? mayAdjudicate : unresolved && !assignedElsewhere);
  const image = task.payload.image;
  const annotation: Annotation =
    task.modality === "image"
      ? { kind: "boxes", boxes }
      : { kind: "category", label };
  async function decide(decision: "accept" | "reject") {
    const result = await action.perform(() =>
      call(
        `/annotation-tasks/${task.id}/${needsAdjudication ? "adjudicate" : "decision"}`,
        {
          method: "POST",
          body: {
            expected_revision: task.revision,
            decision,
            annotation: decision === "accept" ? annotation : null,
            note,
          },
        },
      ),
    );
    if (result) {
      client.invalidateQueries();
      toast(needsAdjudication ? "Adjudication saved." : "Review saved.");
    }
  }
  return (
    <>
      <PageHeader
        eyebrow="ANNOTATION"
        title={`Sample ${task.sample_index + 1}`}
        description={`Round ${task.round} · ${task.required_reviews} ${task.required_reviews === 1 ? "reviewer" : "independent reviewers required"}`}
      >
        <Button variant="secondary" onClick={() => client.invalidateQueries()}>
          <RefreshCw size={13} />
          Refresh task
        </Button>
        <Link
          href={`/curation/${task.curation_id}`}
          className="button secondary"
        >
          Back to review queue
        </Link>
      </PageHeader>
      <div className="detail-meta" style={{ marginBottom: 20 }}>
        <Status value={task.status} />
        <span className="mono">
          {shortId(task.id)} · revision {task.revision}
        </span>
      </div>
      <ErrorNotice error={action.error || reviewers.error} />
      {task.excluded_reason && (
        <div className="notice">
          Excluded by this session&apos;s quality profile:{" "}
          {task.excluded_reason}.
        </div>
      )}
      {needsAdjudication && (
        <div className="notice">
          The reviewers disagree. An administrator who did not vote in this
          round must adjudicate or reopen the task.
        </div>
      )}
      {assignedElsewhere && (
        <div className="notice">
          Assigned to{" "}
          {reviewers.data?.items.find((item) => item.id === task.assigned_to)
            ?.name || "another reviewer"}
          . Assignment must be changed before you review.
        </div>
      )}
      <div className="two-columns">
        <section className="stack">
          <div className="panel">
            <div className="panel-heading">
              <h2>{image ? "Box annotation editor" : "Source sample"}</h2>
              <span className="muted">{task.modality}</span>
            </div>
            <div className="panel-body">
              {image && task.media_url ? (
                <BoxEditor
                  path={task.media_url}
                  width={image.width}
                  height={image.height}
                  categories={categories}
                  boxes={boxes}
                  onChange={setBoxes}
                  readOnly={!mayReview}
                />
              ) : (
                <Code value={task.payload} />
              )}
            </div>
          </div>
          <section className="panel">
            <div className="panel-heading">
              <h2>Review history</h2>
              <span className="muted">
                {task.reviews.length} recorded decisions
              </span>
            </div>
            {!task.reviews.length ? (
              <div className="panel-body">
                <p className="muted">
                  No decisions yet. Every review and correction will appear
                  here.
                </p>
              </div>
            ) : (
              <ol className="review-history">
                {task.reviews.map((review) => (
                  <li key={review.id}>
                    <div className="section-row">
                      <strong>
                        {reviewers.data?.items.find(
                          (item) => item.id === review.user_id,
                        )?.name || shortId(review.user_id)}
                      </strong>
                      <span className="muted">
                        Round {review.round} ·{" "}
                        {new Date(review.created_at).toLocaleString()}
                      </span>
                    </div>
                    <span className="status">
                      {review.decision.replaceAll("_", " ")}
                    </span>
                    <p>{review.note}</p>
                    {review.annotation && <Code value={review.annotation} />}
                  </li>
                ))}
              </ol>
            )}
          </section>
        </section>
        <aside className="stack" aria-label="Review decision and assignment">
          <section className="panel">
            <div className="panel-heading">
              <h2>{needsAdjudication ? "Adjudication" : "Your review"}</h2>
              <ClipboardCheck size={15} />
            </div>
            <form
              className="panel-body"
              onSubmit={(event) => {
                event.preventDefault();
                void decide("accept");
              }}
            >
              {task.modality === "text" && (
                <label className="field">
                  <span>Sample category</span>
                  <select
                    value={label}
                    disabled={!mayReview}
                    onChange={(event) => setLabel(event.target.value)}
                  >
                    {categories.map((category) => (
                      <option key={category}>{category}</option>
                    ))}
                  </select>
                </label>
              )}
              <label className="field">
                <span>Review note</span>
                <textarea
                  required
                  maxLength={2000}
                  value={note}
                  readOnly={
                    !mayReview &&
                    !(
                      isOpen &&
                      organization.scopes.includes("annotations:adjudicate") &&
                      task.status !== "EXCLUDED"
                    )
                  }
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="Explain your decision or correction."
                />
              </label>
              {mayReview && (
                <div className="review-actions">
                  <Button
                    type="submit"
                    busy={action.busy}
                    disabled={!note.trim()}
                  >
                    {needsAdjudication
                      ? "Accept adjudication"
                      : "Submit review"}
                  </Button>
                  <Button
                    type="button"
                    variant="danger"
                    busy={action.busy}
                    disabled={!note.trim()}
                    onClick={() => decide("reject")}
                  >
                    {needsAdjudication
                      ? "Reject adjudication"
                      : "Reject sample"}
                  </Button>
                </div>
              )}
              {!mayReview && (
                <p className="muted">
                  {!isOpen
                    ? "This review snapshot is frozen."
                    : task.status === "EXCLUDED"
                      ? "Duplicate exclusions preserve the source unchanged."
                      : needsAdjudication
                        ? "An independent administrator can resolve this disagreement."
                        : !unresolved
                          ? "This task is resolved. An administrator can reopen it for a new review round."
                          : assignedElsewhere
                            ? "This task is assigned to another reviewer."
                            : "Your role can view this task."}
                </p>
              )}
              {isOpen &&
                organization.scopes.includes("annotations:adjudicate") &&
                !unresolved &&
                task.status !== "EXCLUDED" && (
                  <Button
                    type="button"
                    variant="secondary"
                    busy={action.busy}
                    disabled={!note.trim()}
                    onClick={() =>
                      action.perform(async () => {
                        await call(`/annotation-tasks/${task.id}/reopen`, {
                          method: "POST",
                          body: { expected_revision: task.revision, note },
                        });
                        client.invalidateQueries();
                        toast("New review round opened.");
                      })
                    }
                  >
                    Reopen for review
                  </Button>
                )}
            </form>
          </section>
          {isOpen &&
            unresolved &&
            organization.scopes.includes("annotations:review") && (
              <section className="panel">
                <div className="panel-heading">
                  <h2>Assignment</h2>
                </div>
                <div className="panel-body">
                  {organization.scopes.includes("annotations:manage") ? (
                    <>
                      <label className="field">
                        <span>Assigned reviewer</span>
                        <select
                          value={assignment}
                          onChange={(event) =>
                            setAssignment(event.target.value)
                          }
                        >
                          <option value="">Unassigned</option>
                          {reviewers.data?.items.map((person) => (
                            <option key={person.id} value={person.id}>
                              {person.name} · {person.role}
                            </option>
                          ))}
                        </select>
                      </label>
                      <Button
                        variant="secondary"
                        busy={action.busy}
                        onClick={() =>
                          action.perform(async () => {
                            await call(`/annotation-tasks/${task.id}/assign`, {
                              method: "POST",
                              body: {
                                expected_revision: task.revision,
                                user_id: assignment || null,
                              },
                            });
                            client.invalidateQueries();
                            toast("Assignment saved.");
                          })
                        }
                      >
                        Save assignment
                      </Button>
                    </>
                  ) : (
                    !assignedElsewhere && (
                      <Button
                        variant="secondary"
                        disabled={task.assigned_to === session.user.id}
                        busy={action.busy}
                        onClick={() =>
                          action.perform(async () => {
                            await call(`/annotation-tasks/${task.id}/assign`, {
                              method: "POST",
                              body: {
                                expected_revision: task.revision,
                                user_id: session.user.id,
                              },
                            });
                            client.invalidateQueries();
                            toast("Task assigned to you.");
                          })
                        }
                      >
                        Claim task
                      </Button>
                    )
                  )}
                </div>
              </section>
            )}
          <div className="notice">
            Human reviews record a decision and provenance. Agreement and
            accepted labels are not a guarantee of accuracy.
          </div>
        </aside>
      </div>
    </>
  );
}
