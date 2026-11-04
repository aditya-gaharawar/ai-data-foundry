import type { components } from "./schema.js";
type Dataset = components["schemas"]["DatasetOut"];
type Run = components["schemas"]["RunOut"];
type Recipe = components["schemas"]["RecipeOut"];
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
    download: async (versionId: string) => {
      const created = await this.request<{ id: string }>(
        "POST",
        "/v1/exports",
        { version_id: versionId, format: "jsonl" },
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
}
export type { components } from "./schema.js";
