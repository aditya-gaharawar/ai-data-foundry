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
  ): Promise<T> {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.options.apiKey}`,
      "Content-Type": "application/json",
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
}
export type { components } from "./schema.js";
