import type { components } from "./schema.js";
type Dataset = components["schemas"]["DatasetOut"];
type Run = components["schemas"]["RunOut"];
type Recipe = components["schemas"]["RecipeOut"];
type Curation = components["schemas"]["CurationOut"];
type Task = components["schemas"]["AnnotationTaskOut"];
type Profile = components["schemas"]["QualityProfileOut"];
type Page<T> = { items: T[]; next_cursor: string | null };
export class DataFoundryError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string,
  ) {
    super(message);
  }
}
export class DataFoundry {
  constructor(
    private options: {
      baseUrl: string;
      apiKey: string;
      organizationId?: string;
    },
  ) {}
  async request<T>(
    method: string,
    path: string,
    body?: unknown,
    idempotencyKey?: string,
    extraHeaders: Record<string, string> = {},
  ): Promise<T> {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.options.apiKey}`,
      "Content-Type": "application/json",
      ...extraHeaders,
    };
    if (this.options.organizationId)
      headers["X-Organization-Id"] = this.options.organizationId;
    if (method === "POST")
      headers["Idempotency-Key"] = idempotencyKey || crypto.randomUUID();
    const result = await fetch(this.options.baseUrl.replace(/\/$/, "") + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(30000),
    });
    if (!result.ok) {
      const error = await result.json();
      throw new DataFoundryError(
        result.status,
        error.code,
        error.detail,
        error.request_id,
      );
    }
    return result.status === 204 ? (undefined as T) : result.json();
  }
  datasets = {
    create: (body: components["schemas"]["DatasetCreate"], key?: string) =>
      this.request<Dataset>("POST", "/v1/datasets", body, key),
    list: () => this.request<Page<Dataset>>("GET", "/v1/datasets"),
    get: (id: string) => this.request<Dataset>("GET", `/v1/datasets/${id}`),
    upload: async (
      datasetId: string,
      filename: string,
      bytes: Uint8Array,
      contentType?: components["schemas"]["UploadCreate"]["content_type"],
    ) => {
      const sha = Array.from(
        new Uint8Array(
          await crypto.subtle.digest("SHA-256", new Uint8Array(bytes)),
        ),
      )
        .map((value) => value.toString(16).padStart(2, "0"))
        .join("");
      const mime =
        contentType ||
        (/\.png$/i.test(filename)
          ? "image/png"
          : /\.jpe?g$/i.test(filename)
            ? "image/jpeg"
            : "application/x-ndjson");
      const upload = await this.request<components["schemas"]["UploadOut"]>(
        "POST",
        "/v1/uploads",
        {
          dataset_id: datasetId,
          filename,
          content_type: mime,
          bytes: bytes.length,
          sha256: sha,
        },
      );
      const parts = [];
      for (const [index, url] of upload.upload_urls!.entries()) {
        const part = await fetch(url, {
          method: "PUT",
          body: new Uint8Array(
            bytes.slice(
              index * upload.part_size!,
              (index + 1) * upload.part_size!,
            ),
          ),
          signal: AbortSignal.timeout(60000),
        });
        if (!part.ok || !part.headers.get("etag"))
          throw new Error("Object storage rejected an upload part.");
        parts.push({ part_number: index + 1, etag: part.headers.get("etag")! });
      }
      return this.request<components["schemas"]["UploadOut"]>(
        "POST",
        `/v1/uploads/${upload.id}/complete`,
        { parts },
      );
    },
    download: async (
      versionId: string,
      format: "jsonl" | "coco" | "yolo" = "jsonl",
    ) => {
      const created = await this.request<{ id: string }>(
        "POST",
        "/v1/exports",
        { version_id: versionId, format },
      );
      const ready = await this.request<{ download_url: string }>(
        "GET",
        `/v1/exports/${created.id}`,
      );
      const headers: Record<string, string> = {
        Authorization: `Bearer ${this.options.apiKey}`,
      };
      if (this.options.organizationId)
        headers["X-Organization-Id"] = this.options.organizationId;
      const result = await fetch(this.options.baseUrl + ready.download_url, {
        headers,
        signal: AbortSignal.timeout(30000),
      });
      if (!result.ok) throw new Error("Export download failed.");
      const bytes = await result.arrayBuffer();
      const sha = Array.from(
        new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
      )
        .map((value) => value.toString(16).padStart(2, "0"))
        .join("");
      if (sha !== result.headers.get("X-Content-SHA256"))
        throw new Error("Export checksum mismatch.");
      return new Uint8Array(bytes);
    },
  };
  recipes = {
    create: (body: components["schemas"]["RecipeCreate"], key?: string) =>
      this.request<Recipe>("POST", "/v1/recipes", body, key),
  };
  runs = {
    create: (body: components["schemas"]["RunCreate"], key?: string) =>
      this.request<Run>("POST", "/v1/runs", body, key),
    get: (id: string) => this.request<Run>("GET", `/v1/runs/${id}`),
    wait: async (id: string, timeoutMs = 120000): Promise<Run> => {
      const end = Date.now() + timeoutMs;
      while (Date.now() < end) {
        const run = await this.runs.get(id);
        if (["SUCCEEDED", "FAILED", "CANCELLED"].includes(run.status))
          return run;
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
      throw new Error(`Run ${id} did not finish before the timeout.`);
    },
  };
  qualityProfiles = {
    create: (
      body: components["schemas"]["QualityProfileCreate"],
      key?: string,
    ) => this.request<Profile>("POST", "/v1/quality-profiles", body, key),
    list: () => this.request<Page<Profile>>("GET", "/v1/quality-profiles"),
    get: (id: string) =>
      this.request<Profile>("GET", `/v1/quality-profiles/${id}`),
  };
  curations = {
    create: (body: components["schemas"]["CurationCreate"], key?: string) =>
      this.request<Curation>("POST", "/v1/curations", body, key),
    list: (datasetId?: string) =>
      this.request<Page<Curation>>(
        "GET",
        "/v1/curations" +
          (datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : ""),
      ),
    get: (id: string) => this.request<Curation>("GET", `/v1/curations/${id}`),
    updateCard: (id: string, body: components["schemas"]["CardUpdate"]) =>
      this.request<Curation>("PATCH", `/v1/curations/${id}/data-card`, body),
    freeze: (
      id: string,
      body: components["schemas"]["FreezeCuration"],
      key?: string,
    ) =>
      this.request<Curation>("POST", `/v1/curations/${id}/freeze`, body, key),
  };
  annotations = {
    list: (curationId?: string) =>
      this.request<Page<Task>>(
        "GET",
        "/v1/annotation-tasks" +
          (curationId ? `?curation_id=${encodeURIComponent(curationId)}` : ""),
      ),
    get: (id: string) =>
      this.request<Task>("GET", `/v1/annotation-tasks/${id}`),
    assign: (
      id: string,
      body: components["schemas"]["TaskAssignment"],
      key?: string,
    ) =>
      this.request<Task>(
        "POST",
        `/v1/annotation-tasks/${id}/assign`,
        body,
        key,
      ),
    review: (
      id: string,
      body: components["schemas"]["ReviewDecision"],
      key?: string,
    ) =>
      this.request<Task>(
        "POST",
        `/v1/annotation-tasks/${id}/decision`,
        body,
        key,
      ),
    adjudicate: (
      id: string,
      body: components["schemas"]["ReviewDecision"],
      key?: string,
    ) =>
      this.request<Task>(
        "POST",
        `/v1/annotation-tasks/${id}/adjudicate`,
        body,
        key,
      ),
    reopen: (
      id: string,
      body: components["schemas"]["TaskReopen"],
      key?: string,
    ) =>
      this.request<Task>(
        "POST",
        `/v1/annotation-tasks/${id}/reopen`,
        body,
        key,
      ),
  };
  providers = {
    catalog: () =>
      this.request<{ items: Record<string, unknown>[] }>(
        "GET",
        "/v1/providers/catalog",
      ),
    list: () =>
      this.request<Page<components["schemas"]["ProviderOut"]>>(
        "GET",
        "/v1/providers",
      ),
    get: (id: string) =>
      this.request<components["schemas"]["ProviderOut"]>(
        "GET",
        `/v1/providers/${id}`,
      ),
    create: (body: components["schemas"]["ProviderCreate"], key?: string) =>
      this.request<components["schemas"]["ProviderOut"]>(
        "POST",
        "/v1/providers",
        body,
        key,
      ),
    revoke: (id: string, key?: string) =>
      this.request("POST", `/v1/providers/${id}/revoke`, {}, key),
  };
  compute = {
    pools: () =>
      this.request<Page<Record<string, unknown>>>(
        "GET",
        "/v1/compute/registered-pools",
      ),
    registerPool: (body: components["schemas"]["PoolCreate"], key?: string) =>
      this.request<Record<string, unknown>>(
        "POST",
        "/v1/compute/registered-pools",
        body,
        key,
      ),
    agents: () =>
      this.request<Page<Record<string, unknown>>>("GET", "/v1/compute/agents"),
    enroll: (body: components["schemas"]["AgentCreate"], key?: string) =>
      this.request<Record<string, unknown>>(
        "POST",
        "/v1/compute/agents",
        body,
        key,
      ),
    revoke: (id: string, key?: string) =>
      this.request("POST", `/v1/compute/agents/${id}/revoke`, {}, key),
    placement: (body: components["schemas"]["Placement"]) =>
      this.request<Record<string, unknown>>(
        "POST",
        "/v1/compute/placement",
        body,
      ),
    submit: (body: components["schemas"]["ComputeJobCreate"], key?: string) =>
      this.request<Record<string, unknown>>(
        "POST",
        "/v1/compute/jobs",
        body,
        key,
      ),
    jobs: () =>
      this.request<Page<Record<string, unknown>>>("GET", "/v1/compute/jobs"),
    job: (id: string) =>
      this.request<Record<string, unknown>>("GET", `/v1/compute/jobs/${id}`),
    cancel: (id: string, key?: string) =>
      this.request("POST", `/v1/compute/jobs/${id}/cancel`, {}, key),
  };
  simulations = {
    capabilities: () =>
      this.request<{ items: Record<string, unknown>[] }>(
        "GET",
        "/v1/simulations/capabilities",
      ),
  };
  scim = {
    configuration: () =>
      this.request<Record<string, unknown>>(
        "GET",
        "/v1/scim/v2/ServiceProviderConfig",
      ),
    users: (startIndex = 1, count = 25) =>
      this.request<Record<string, unknown>>(
        "GET",
        `/v1/scim/v2/Users?${new URLSearchParams({ startIndex: String(startIndex), count: String(count) })}`,
      ),
    user: (id: string) =>
      this.request<Record<string, unknown>>("GET", `/v1/scim/v2/Users/${id}`),
    create: (body: components["schemas"]["ScimUser"]) =>
      this.request<Record<string, unknown>>("POST", "/v1/scim/v2/Users", body),
    replace: (
      id: string,
      body: components["schemas"]["ScimUser"],
      etag: string,
    ) =>
      this.request<Record<string, unknown>>(
        "PUT",
        `/v1/scim/v2/Users/${id}`,
        body,
        undefined,
        { "If-Match": etag },
      ),
    patch: (
      id: string,
      body: components["schemas"]["ScimPatch"],
      etag: string,
    ) =>
      this.request<Record<string, unknown>>(
        "PATCH",
        `/v1/scim/v2/Users/${id}`,
        body,
        undefined,
        { "If-Match": etag },
      ),
    delete: (id: string, etag: string) =>
      this.request<void>(
        "DELETE",
        `/v1/scim/v2/Users/${id}`,
        undefined,
        undefined,
        { "If-Match": etag },
      ),
  };
  evaluations = {
    distribution: (versionId: string) =>
      this.request<Record<string, unknown>>(
        "GET",
        `/v1/versions/${versionId}/distribution`,
      ),
    compareVersions: (left: string, right: string) =>
      this.request<Record<string, unknown>>(
        "GET",
        `/v1/versions/compare?${new URLSearchParams({ left_version_id: left, right_version_id: right })}`,
      ),
    search: (query: string, offset = 0) =>
      this.request<Record<string, unknown>>(
        "GET",
        `/v1/search/samples?${new URLSearchParams({ q: query, offset: String(offset) })}`,
      ),
    benchmarks: () =>
      this.request<Page<Record<string, unknown>>>("GET", "/v1/benchmarks"),
    createBenchmark: (
      body: components["schemas"]["BenchmarkCreate"],
      key?: string,
    ) =>
      this.request<Record<string, unknown>>(
        "POST",
        "/v1/benchmarks",
        body,
        key,
      ),
    importResults: (
      body: components["schemas"]["EvaluationCreate"],
      key?: string,
    ) =>
      this.request<Record<string, unknown>>(
        "POST",
        "/v1/evaluations",
        body,
        key,
      ),
    list: () =>
      this.request<Page<Record<string, unknown>>>("GET", "/v1/evaluations"),
    get: (id: string) =>
      this.request<Record<string, unknown>>("GET", `/v1/evaluations/${id}`),
    compare: (baseline: string, candidate: string) =>
      this.request<Record<string, unknown>>(
        "GET",
        `/v1/evaluations/compare?${new URLSearchParams({ baseline_id: baseline, candidate_id: candidate })}`,
      ),
    feedback: () =>
      this.request<Page<Record<string, unknown>>>("GET", "/v1/feedback"),
    propose: (body: components["schemas"]["FeedbackCreate"], key?: string) =>
      this.request<Record<string, unknown>>("POST", "/v1/feedback", body, key),
    decide: (
      id: string,
      body: components["schemas"]["FeedbackDecision"],
      key?: string,
    ) => this.request("POST", `/v1/feedback/${id}/decision`, body, key),
  };
  governance = {
    policy: () =>
      this.request<Record<string, unknown>>("GET", "/v1/governance/policy"),
    policies: () =>
      this.request<Page<Record<string, unknown>>>(
        "GET",
        "/v1/governance/policies",
      ),
    setPolicy: (
      body: components["schemas"]["GovernancePolicyCreate"],
      key?: string,
    ) =>
      this.request<Record<string, unknown>>(
        "POST",
        "/v1/governance/policies",
        body,
        key,
      ),
    protect: (
      id: string,
      body: components["schemas"]["DatasetGovernance"],
      key?: string,
    ) => this.request("POST", `/v1/governance/datasets/${id}`, body, key),
    approvals: () =>
      this.request<Page<Record<string, unknown>>>(
        "GET",
        "/v1/governance/approvals",
      ),
    decideApproval: (
      id: string,
      body: components["schemas"]["ApprovalDecision"],
      key?: string,
    ) =>
      this.request(
        "POST",
        `/v1/governance/approvals/${id}/decision`,
        body,
        key,
      ),
    retention: () =>
      this.request<Record<string, unknown>>(
        "GET",
        "/v1/governance/retention-plan",
      ),
    erasures: () =>
      this.request<Page<Record<string, unknown>>>(
        "GET",
        "/v1/governance/erasures",
      ),
    erasure: (id: string) =>
      this.request<Record<string, unknown>>(
        "GET",
        `/v1/governance/erasures/${id}`,
      ),
    requestErasure: (
      body: components["schemas"]["ErasureCreate"],
      key?: string,
    ) =>
      this.request<Record<string, unknown>>(
        "POST",
        "/v1/governance/erasures",
        body,
        key,
      ),
    decideErasure: (
      id: string,
      body: components["schemas"]["ApprovalDecision"],
      key?: string,
    ) =>
      this.request("POST", `/v1/governance/erasures/${id}/decision`, body, key),
    previewErasure: (id: string, key?: string) =>
      this.request<Record<string, unknown>>(
        "POST",
        `/v1/governance/erasures/${id}/preview`,
        {},
        key,
      ),
    executeErasure: (
      id: string,
      body: components["schemas"]["ErasureExecute"],
      key?: string,
    ) =>
      this.request("POST", `/v1/governance/erasures/${id}/execute`, body, key),
    retryErasure: (id: string, key?: string) =>
      this.request("POST", `/v1/governance/erasures/${id}/retry`, {}, key),
    provisioningTokens: () =>
      this.request<Page<Record<string, unknown>>>(
        "GET",
        "/v1/governance/scim-tokens",
      ),
    createProvisioningToken: (
      body: components["schemas"]["ScimTokenCreate"],
      key?: string,
    ) =>
      this.request<Record<string, unknown>>(
        "POST",
        "/v1/governance/scim-tokens",
        body,
        key,
      ),
    revokeProvisioningToken: (id: string, key?: string) =>
      this.request("POST", `/v1/governance/scim-tokens/${id}/revoke`, {}, key),
  };
  schedules = {
    health: () =>
      this.request<components["schemas"]["SchedulerHealth"]>(
        "GET",
        "/v1/schedules/health",
      ),
    preview: (body: components["schemas"]["SchedulePreview"]) =>
      this.request<components["schemas"]["SchedulePreviewOut"]>(
        "POST",
        "/v1/schedules/preview",
        body,
      ),
    create: (body: components["schemas"]["ScheduleCreate"], key?: string) =>
      this.request<components["schemas"]["ScheduleOut"]>(
        "POST",
        "/v1/schedules",
        body,
        key,
      ),
    list: (query: { limit?: number; cursor?: string } = {}) =>
      this.request<Page<components["schemas"]["ScheduleOut"]>>(
        "GET",
        "/v1/schedules?" +
          new URLSearchParams(
            Object.entries(query).map(([key, value]) => [key, String(value)]),
          ),
      ),
    retrieve: (id: string) =>
      this.request<components["schemas"]["ScheduleOut"]>(
        "GET",
        `/v1/schedules/${id}`,
      ),
    control: (
      id: string,
      body: components["schemas"]["ScheduleControl"],
      key?: string,
    ) =>
      this.request<components["schemas"]["ScheduleOut"]>(
        "POST",
        `/v1/schedules/${id}/control`,
        body,
        key,
      ),
    occurrences: (
      id: string,
      query: { limit?: number; cursor?: string } = {},
    ) =>
      this.request<Page<components["schemas"]["OccurrenceOut"]>>(
        "GET",
        `/v1/schedules/${id}/occurrences?` +
          new URLSearchParams(
            Object.entries(query).map(([key, value]) => [key, String(value)]),
          ),
      ),
  };
  notifications = {
    summary: () =>
      this.request<components["schemas"]["NotificationSummary"]>(
        "GET",
        "/v1/notifications/summary",
      ),
    list: (query: { limit?: number; cursor?: string; unread?: boolean } = {}) =>
      this.request<Page<components["schemas"]["NotificationOut"]>>(
        "GET",
        "/v1/notifications?" +
          new URLSearchParams(
            Object.entries(query).map(([key, value]) => [key, String(value)]),
          ),
      ),
    read: (id: string, key?: string) =>
      this.request<components["schemas"]["NotificationOut"]>(
        "POST",
        `/v1/notifications/${id}/read`,
        {},
        key,
      ),
    readAll: (before: string, key?: string) =>
      this.request<components["schemas"]["ReadAllOut"]>(
        "POST",
        "/v1/notifications/read-all",
        { before },
        key,
      ),
  };
  operations = {
    status: () =>
      this.request<Record<string, unknown>>("GET", "/v1/operations/status"),
    reconcile: (key?: string) =>
      this.request<Record<string, unknown>>(
        "POST",
        "/v1/operations/reconciliations",
        {},
        key,
      ),
    reconciliations: () =>
      this.request<Page<Record<string, unknown>>>(
        "GET",
        "/v1/operations/reconciliations",
      ),
    scan: (key?: string) =>
      this.request("POST", "/v1/operations/incidents/scan", {}, key),
    incidents: () =>
      this.request<Page<Record<string, unknown>>>(
        "GET",
        "/v1/operations/incidents",
      ),
    acknowledge: (id: string, key?: string) =>
      this.request(
        "POST",
        `/v1/operations/incidents/${id}/acknowledge`,
        {},
        key,
      ),
    proofs: () =>
      this.request<Page<Record<string, unknown>>>(
        "GET",
        "/v1/operations/proofs",
      ),
    importProof: (body: components["schemas"]["ProofImport"], key?: string) =>
      this.request("POST", "/v1/operations/proofs", body, key),
    readiness: () =>
      this.request<Page<Record<string, unknown>>>(
        "GET",
        "/v1/operations/readiness",
      ),
    signReadiness: (key?: string) =>
      this.request<Record<string, unknown>>(
        "POST",
        "/v1/operations/readiness",
        {},
        key,
      ),
  };
}
export type { components } from "./schema.js";
