"use client";
import { useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import type { Dataset, Page, Version } from "@/lib/api";
import { shortId } from "@/lib/api";
import { useResource, useWorkspace } from "./context";
import { Button, Code, ErrorNotice, PageHeader, Status, useAction } from "./ui";

type Benchmark = {
  id: string;
  name: string;
  version_id: string;
  source_kind: string;
};
type Evaluation = {
  id: string;
  version_id: string;
  model_ref: string;
  external_run_ref: string;
  benchmark_id: string;
  metrics: {
    accuracy: number;
    correct: number;
    total: number;
    wilson_95_interval: number[];
    limitations: string;
  };
};
type Feedback = {
  id: string;
  evaluation_id: string;
  status: string;
  proposal: Record<string, unknown>;
};

export function VersionPicker({
  label,
  value,
  onChange,
  holdouts = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  holdouts?: boolean;
}) {
  const datasets = useResource<Page<Dataset>>("/datasets?limit=100");
  const [datasetId, setDatasetId] = useState("");
  const versions = useResource<Page<Version>>(
    `/datasets/${datasetId || "none"}/versions`,
    false,
    !!datasetId,
  );
  return (
    <div className="field-row">
      <label className="field">
        <span>{label} dataset</span>
        <select
          aria-label={`${label} dataset`}
          required
          value={datasetId}
          onChange={(event) => {
            setDatasetId(event.target.value);
            onChange("");
          }}
        >
          <option value="">Select dataset</option>
          {datasets.data?.items
            .filter(
              (item) =>
                !item.archived &&
                (holdouts
                  ? item.protection === "holdout"
                  : item.protection !== "holdout"),
            )
            .map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
        </select>
      </label>
      <label className="field">
        <span>{label} version</span>
        <select
          aria-label={`${label} version`}
          required
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">Select version</option>
          {versions.data?.items.map((item) => (
            <option key={item.id} value={item.id}>
              v{item.number} · {item.sample_count} samples
            </option>
          ))}
        </select>
      </label>
      <ErrorNotice error={datasets.error || versions.error} />
    </div>
  );
}

export function EvaluationPage() {
  const { call, organization, toast } = useWorkspace();
  const cache = useQueryClient();
  const action = useAction();
  const canWrite = organization.scopes.includes("evaluations:write");
  const canHoldout = organization.scopes.includes("holdouts:read");
  const evaluations = useResource<Page<Evaluation>>("/evaluations?limit=100");
  const benchmarks = useResource<Page<Benchmark>>(
    "/benchmarks",
    false,
    canHoldout,
  );
  const feedback = useResource<Page<Feedback>>("/feedback");
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [difference, setDifference] = useState<unknown>(null);
  const [report, setReport] = useState<unknown>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<{
    items: {
      dataset_id: string;
      version_id: string;
      sample_id: string;
      excerpt: string;
    }[];
    next_offset: number | null;
    offset: number;
  } | null>(null);
  const [holdout, setHoldout] = useState("");
  const [benchmarkName, setBenchmarkName] = useState("");
  const [benchmarkSource, setBenchmarkSource] = useState("external_holdout");
  const [benchmarkRef, setBenchmarkRef] = useState("");
  const [independent, setIndependent] = useState(false);
  const [training, setTraining] = useState("");
  const [benchmarkId, setBenchmarkId] = useState("");
  const [model, setModel] = useState("");
  const [runRef, setRunRef] = useState("");
  const [correct, setCorrect] = useState(0);
  const [total, setTotal] = useState(1);
  const [slice, setSlice] = useState("");
  const [sliceCorrect, setSliceCorrect] = useState(0);
  const [sliceTotal, setSliceTotal] = useState(1);
  const [note, setNote] = useState("");
  const [baseline, setBaseline] = useState("");
  const [candidate, setCandidate] = useState("");
  const [comparison, setComparison] = useState<unknown>(null);
  const [selectedEvaluation, setSelectedEvaluation] = useState("");
  const [maximum, setMaximum] = useState(100);
  const [budget, setBudget] = useState(1);
  const [decisionNote, setDecisionNote] = useState("");
  async function mutate<T>(path: string, body: unknown) {
    const result = await action.perform(() =>
      call<T>(path, { method: "POST", body }),
    );
    if (result) cache.invalidateQueries();
    return result;
  }
  async function searchPage(offset = 0) {
    const result = await action.perform(() =>
      call<NonNullable<typeof search>>(
        `/search/samples?q=${encodeURIComponent(query)}&offset=${offset}&limit=10`,
      ),
    );
    if (result) setSearch(result);
  }
  return (
    <>
      <PageHeader
        eyebrow="MEASURE / EVALUATIONS"
        title="Evidence across versions"
        description="Inspect distributions, compare immutable data, and connect imported outcomes to bounded generation recommendations."
      />
      <ErrorNotice
        error={
          action.error ||
          evaluations.error ||
          benchmarks.error ||
          feedback.error
        }
      />
      <section className="panel">
        <div className="panel-heading">
          <h2>Search published samples</h2>
          <small>PostgreSQL lexical index</small>
        </div>
        <form
          className="panel-body"
          onSubmit={(event) => {
            event.preventDefault();
            searchPage();
          }}
        >
          <label className="field">
            <span>Search text</span>
            <input
              aria-label="Search text"
              required
              minLength={1}
              maxLength={200}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Find a phrase, tag, or class"
            />
          </label>
          <Button type="submit" busy={action.busy}>
            <Search size={14} />
            Search samples
          </Button>
        </form>
        {search && (
          <div className="panel-body" aria-live="polite">
            {search.items.length ? (
              search.items.map((item) => (
                <div
                  className="record-row"
                  key={item.version_id + item.sample_id}
                >
                  <div>
                    <Link href={`/datasets/${item.dataset_id}`}>
                      {shortId(item.sample_id)}
                    </Link>
                    <p>{item.excerpt}</p>
                    <small>{shortId(item.version_id)}</small>
                  </div>
                </div>
              ))
            ) : (
              <p>No matching samples in your accessible indexed versions.</p>
            )}
            <div className="studio-actions">
              <Button
                variant="ghost"
                disabled={search.offset === 0}
                onClick={() => searchPage(Math.max(0, search.offset - 10))}
              >
                Previous results
              </Button>
              <Button
                variant="ghost"
                disabled={search.next_offset === null}
                onClick={() => searchPage(search.next_offset || 0)}
              >
                Next results
              </Button>
            </div>
          </div>
        )}
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h2>Version distributions & differences</h2>
        </div>
        <div className="panel-body">
          <VersionPicker label="Baseline" value={left} onChange={setLeft} />
          <VersionPicker label="Candidate" value={right} onChange={setRight} />
          <div className="studio-actions">
            <Button
              variant="secondary"
              disabled={!left}
              busy={action.busy}
              onClick={async () => {
                const result = await action.perform(() =>
                  call(`/versions/${left}/distribution`),
                );
                if (result) setReport(result);
              }}
            >
              Inspect distribution
            </Button>
            <Button
              disabled={!left || !right}
              busy={action.busy}
              onClick={async () => {
                const result = await action.perform(() =>
                  call(
                    `/versions/compare?left_version_id=${left}&right_version_id=${right}`,
                  ),
                );
                if (result) setDifference(result);
              }}
            >
              Compare versions
            </Button>
          </div>
          {report !== null && <Code value={report} />}{" "}
          {difference !== null && <Code value={difference} />}
        </div>
      </section>
      <div className="notice">
        Imported metrics preserve their source and denominators. Synthetic
        fixtures and user attestations do not establish model gains. Evaluate
        improvements against an independent fixed benchmark.
      </div>
      {canWrite && canHoldout && (
        <details className="panel evidence-details">
          <summary>Register a protected benchmark</summary>
          <form
            className="panel-body"
            onSubmit={async (event) => {
              event.preventDefault();
              const result = await mutate<Benchmark>("/benchmarks", {
                name: benchmarkName,
                version_id: holdout,
                external_ref: benchmarkRef,
                source_kind: benchmarkSource,
                independent_of_training: independent,
              });
              if (result) {
                setBenchmarkId(result.id);
                toast("Benchmark registered with frozen evidence.");
              }
            }}
          >
            <p>
              First protect an independent dataset in{" "}
              <Link href="/settings/governance">Governance</Link>.
            </p>
            <VersionPicker
              label="Holdout"
              value={holdout}
              onChange={setHoldout}
              holdouts
            />
            <label className="field">
              <span>Benchmark name</span>
              <input
                aria-label="Benchmark name"
                required
                value={benchmarkName}
                maxLength={160}
                onChange={(event) => setBenchmarkName(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Benchmark source reference</span>
              <input
                aria-label="Benchmark source reference"
                required
                maxLength={400}
                value={benchmarkRef}
                onChange={(event) => setBenchmarkRef(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Benchmark evidence kind</span>
              <select
                aria-label="Benchmark evidence kind"
                value={benchmarkSource}
                onChange={(event) => setBenchmarkSource(event.target.value)}
              >
                <option value="external_holdout">
                  Independent external holdout · user attested
                </option>
                <option value="synthetic_fixture">
                  Synthetic fixture · protocol test only
                </option>
              </select>
            </label>
            <label className="check-field">
              <input
                required
                type="checkbox"
                checked={independent}
                onChange={(event) => setIndependent(event.target.checked)}
              />
              <span>
                This benchmark is independent of the training data being
                evaluated.
              </span>
            </label>
            <Button type="submit" busy={action.busy}>
              Register benchmark
            </Button>
          </form>
        </details>
      )}
      {canWrite && canHoldout && (
        <section className="panel">
          <div className="panel-heading">
            <h2>Import evaluation results</h2>
          </div>
          <form
            className="panel-body"
            onSubmit={async (event) => {
              event.preventDefault();
              const result = await mutate<Evaluation>("/evaluations", {
                version_id: training,
                benchmark_id: benchmarkId,
                model_ref: model,
                external_run_ref: runRef,
                result: { name: "overall", correct, total },
                slices: slice
                  ? [{ name: slice, correct: sliceCorrect, total: sliceTotal }]
                  : [],
                evidence_note: note,
              });
              if (result) {
                setSelectedEvaluation(result.id);
                toast("Evaluation imported with immutable evidence.");
              }
            }}
          >
            <VersionPicker
              label="Training"
              value={training}
              onChange={setTraining}
            />
            <label className="field">
              <span>Fixed benchmark</span>
              <select
                aria-label="Fixed benchmark"
                required
                value={benchmarkId}
                onChange={(event) => setBenchmarkId(event.target.value)}
              >
                <option value="">Select benchmark</option>
                {benchmarks.data?.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {item.source_kind}
                  </option>
                ))}
              </select>
            </label>
            <div className="field-row">
              <label className="field">
                <span>Evaluated model reference</span>
                <input
                  aria-label="Evaluated model reference"
                  required
                  maxLength={200}
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                />
              </label>
              <label className="field">
                <span>External evaluation run reference</span>
                <input
                  aria-label="External evaluation run reference"
                  required
                  maxLength={400}
                  value={runRef}
                  onChange={(event) => setRunRef(event.target.value)}
                />
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span>Correct answers</span>
                <input
                  aria-label="Correct answers"
                  required
                  type="number"
                  min={0}
                  max={total}
                  value={correct}
                  onChange={(event) => setCorrect(Number(event.target.value))}
                />
              </label>
              <label className="field">
                <span>Total answers</span>
                <input
                  aria-label="Total answers"
                  required
                  type="number"
                  min={1}
                  max={100000000}
                  value={total}
                  onChange={(event) => setTotal(Number(event.target.value))}
                />
              </label>
            </div>
            <label className="field">
              <span>Failure slice name (optional)</span>
              <input
                aria-label="Failure slice name (optional)"
                maxLength={100}
                value={slice}
                onChange={(event) => setSlice(event.target.value)}
              />
            </label>
            {slice && (
              <div className="field-row">
                <label className="field">
                  <span>Slice correct</span>
                  <input
                    aria-label="Slice correct"
                    type="number"
                    min={0}
                    max={sliceTotal}
                    value={sliceCorrect}
                    onChange={(event) =>
                      setSliceCorrect(Number(event.target.value))
                    }
                  />
                </label>
                <label className="field">
                  <span>Slice total</span>
                  <input
                    aria-label="Slice total"
                    type="number"
                    min={1}
                    value={sliceTotal}
                    onChange={(event) =>
                      setSliceTotal(Number(event.target.value))
                    }
                  />
                </label>
              </div>
            )}
            <label className="field">
              <span>Evidence and limitations</span>
              <textarea
                aria-label="Evidence and limitations"
                required
                minLength={8}
                maxLength={4000}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Where these measured counts came from, and what they cannot prove"
              />
            </label>
            <Button type="submit" busy={action.busy}>
              Import results
            </Button>
          </form>
        </section>
      )}
      <section className="panel">
        <div className="panel-heading">
          <h2>Recorded outcomes</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Model / run</th>
                <th>Accuracy</th>
                <th>95% Wilson interval</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {evaluations.data?.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    {item.model_ref}
                    <small>{item.external_run_ref}</small>
                  </td>
                  <td>
                    {(item.metrics.accuracy * 100).toFixed(1)}%
                    <small>
                      {item.metrics.correct} / {item.metrics.total}
                    </small>
                  </td>
                  <td>
                    {item.metrics.wilson_95_interval
                      .map((value) => (value * 100).toFixed(1) + "%")
                      .join(" – ")}
                  </td>
                  <td>
                    <small>{shortId(item.id)} · imported attestation</small>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!evaluations.data?.items.length && (
            <p className="panel-body muted">No evaluation outcomes recorded.</p>
          )}
        </div>
        <div className="panel-body">
          <div className="field-row">
            <label className="field">
              <span>Baseline evaluation</span>
              <select
                aria-label="Baseline evaluation"
                value={baseline}
                onChange={(event) => setBaseline(event.target.value)}
              >
                <option value="">Select baseline</option>
                {evaluations.data?.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.model_ref} · {shortId(item.id)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Candidate evaluation</span>
              <select
                aria-label="Candidate evaluation"
                value={candidate}
                onChange={(event) => setCandidate(event.target.value)}
              >
                <option value="">Select candidate</option>
                {evaluations.data?.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.model_ref} · {shortId(item.id)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <Button
            variant="secondary"
            busy={action.busy}
            disabled={!baseline || !candidate}
            onClick={async () => {
              const result = await action.perform(() =>
                call(
                  `/evaluations/compare?baseline_id=${baseline}&candidate_id=${candidate}`,
                ),
              );
              if (result) setComparison(result);
            }}
          >
            Compare outcomes
          </Button>
          {comparison !== null && <Code value={comparison} />}
        </div>
      </section>
      {canWrite && (
        <section className="panel">
          <div className="panel-heading">
            <h2>Targeted generation policy</h2>
            <small>Manual approval · no automatic jobs</small>
          </div>
          <form
            className="panel-body"
            onSubmit={async (event) => {
              event.preventDefault();
              const result = await mutate<Feedback>("/feedback", {
                evaluation_id: selectedEvaluation,
                maximum_new_samples: maximum,
                maximum_internal_budget_usd: budget,
                require_manual_approval: true,
              });
              if (result) toast("Bounded feedback proposal saved.");
            }}
          >
            <label className="field">
              <span>Source evaluation</span>
              <select
                aria-label="Source evaluation"
                required
                value={selectedEvaluation}
                onChange={(event) => setSelectedEvaluation(event.target.value)}
              >
                <option value="">Select evidence</option>
                {evaluations.data?.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.model_ref} · {shortId(item.id)}
                  </option>
                ))}
              </select>
            </label>
            <div className="field-row">
              <label className="field">
                <span>Maximum new samples</span>
                <input
                  aria-label="Maximum new samples"
                  required
                  type="number"
                  min={1}
                  max={1000}
                  value={maximum}
                  onChange={(event) => setMaximum(Number(event.target.value))}
                />
              </label>
              <label className="field">
                <span>Maximum internal budget</span>
                <input
                  aria-label="Maximum internal budget"
                  required
                  type="number"
                  min={0}
                  max={100}
                  step={0.001}
                  value={budget}
                  onChange={(event) => setBudget(Number(event.target.value))}
                />
              </label>
            </div>
            <Button type="submit" busy={action.busy}>
              Save feedback proposal
            </Button>
          </form>
          <div className="panel-body">
            <label className="field">
              <span>Feedback decision note</span>
              <input
                aria-label="Feedback decision note"
                value={decisionNote}
                maxLength={2000}
                onChange={(event) => setDecisionNote(event.target.value)}
              />
            </label>
            {feedback.data?.items.map((item) => (
              <details key={item.id} className="evidence-details">
                <summary>
                  <Status value={item.status} /> {shortId(item.id)}
                </summary>
                <Code value={item.proposal} />
                {item.status === "DRAFT" && (
                  <div className="studio-actions">
                    {["approve", "reject"].map((decision) => (
                      <Button
                        key={decision}
                        variant="secondary"
                        disabled={!decisionNote.trim()}
                        busy={action.busy}
                        onClick={async () => {
                          if (
                            await mutate(`/feedback/${item.id}/decision`, {
                              decision,
                              note: decisionNote,
                            })
                          )
                            toast("Feedback decision saved.");
                        }}
                      >
                        {decision === "approve"
                          ? "Approve proposal"
                          : "Reject proposal"}
                      </Button>
                    ))}
                  </div>
                )}
              </details>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
