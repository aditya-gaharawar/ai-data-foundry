export type Page<T> = { items: T[]; next_cursor?: string | null };
export type Organization = {
  id: string;
  name: string;
  role: string;
  scopes: string[];
};
export type SessionInfo = {
  user: { id: string; email: string; name: string };
  organizations: Organization[];
  csrf_token: string;
  demo_data: boolean;
};
export type Project = { id: string; name: string };
export type Dataset = {
  id: string;
  name: string;
  description: string;
  project_id: string;
  modality: string;
  created_at: string;
  versions_count?: number;
  schema: Record<string, unknown>;
  policy: Record<string, unknown>;
  archived: boolean;
};
export type Version = {
  id: string;
  dataset_id: string;
  number: number;
  sample_count: number;
  manifest_hash: string;
  created_at: string;
  manifest: {
    quality: Quality;
    data_artifact: { bytes: number; sha256: string };
    exports?: Record<string, unknown>;
    recipe_revision_id: string;
    policy: Record<string, unknown>;
    [key: string]: unknown;
  };
};
export type Quality = {
  passed: boolean;
  total: number;
  valid: number;
  invalid: number;
  duplicates: number;
  duplicate_ratio: number;
  checks: string[];
  limitations: string[];
};
export type Run = {
  id: string;
  dataset_id: string;
  recipe_revision_id: string;
  status: string;
  sample_count: number;
  processed: number;
  spent_usd: number;
  reserved_usd: number;
  max_budget_usd: number;
  created_at: string;
  finished_at?: string;
  error?: string;
  quality?: Quality;
  version?: Version;
  cancel_requested: boolean;
};
export type RecipeDefinition = {
  name: string;
  description?: string;
  schema_version: "1.0";
  nodes: {
    id: string;
    type: string;
    config: Record<string, string | number>;
  }[];
  edges: { from: string; to: string }[];
  budget: { currency: "USD"; maximum: number };
};
export type Revision = {
  id: string;
  digest: string;
  definition: RecipeDefinition;
  created_at: string;
};
export type Recipe = {
  id: string;
  name: string;
  project_id: string;
  created_at: string;
  revisions: Revision[];
  revision?: Revision;
};
export type Upload = {
  dataset_id: string;
  id: string;
  filename: string;
  status: string;
  sample_count: number;
  expected_bytes: number;
  created_at: string;
};
export type UploadSession = Upload & {
  part_size: number;
  upload_urls: string[];
};
export type Key = {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  revoked: boolean;
  secret?: string;
  created_at: string;
};
export type Hook = {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  signing_secret?: string;
  created_at: string;
};
export type Delivery = {
  id: string;
  webhook_id: string;
  status: string;
  attempts: number;
  last_status?: number;
  error?: string;
  created_at: string;
};
export type Member = { id: string; name: string; email: string; role: string };
export type Usage = {
  meters: Record<string, number>;
  budget_usd: number;
  reserved_usd: number;
  internal_spent_usd: number;
  external_cost_usd: number;
  billing_status: string;
  rate_micro_usd_per_sample: number;
};
export type Overview = {
  counts: { datasets: number; versions: number; runs: number };
  recent_runs: Run[];
  worker: string;
  usage: Usage;
  capabilities: Record<string, boolean | string>;
};
export type Options = { method?: string; body?: unknown; key?: string };
export type ApiCall = <T>(path: string, options?: Options) => Promise<T>;

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  options: Options = {},
  organization?: string,
  csrf?: string,
): Promise<T> {
  const method = options.method || "GET";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (organization && !path.startsWith("/auth/"))
    headers["X-Organization-Id"] = organization;
  if (csrf) headers["X-CSRF-Token"] = csrf;
  if (method === "POST")
    headers["Idempotency-Key"] = options.key || crypto.randomUUID();
  const result = await fetch(`/api/v1${path}`, {
    method,
    credentials: "same-origin",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  if (!result.ok) {
    const error = await result.json().catch(() => ({
      code: "REQUEST_FAILED",
      detail: "The request could not be completed.",
    }));
    throw new ApiError(
      result.status,
      error.code,
      error.detail,
      error.request_id || result.headers.get("X-Request-Id"),
    );
  }
  return result.status === 204
    ? (undefined as T)
    : (result.json() as Promise<T>);
}
export async function saveExport(
  call: ApiCall,
  versionId: string,
  organization: string,
  format: "jsonl" | "coco" | "yolo" = "jsonl",
) {
  const created = await call<{ id: string }>("/exports", {
    method: "POST",
    body: { version_id: versionId, format },
  });
  const ready = await call<{ download_url: string }>(`/exports/${created.id}`);
  const result = await fetch(`/api${ready.download_url}`, {
    headers: { "X-Organization-Id": organization },
  });
  if (!result.ok)
    throw new Error("Export download failed. Refresh the grant and retry.");
  const bytes = await result.arrayBuffer();
  const checksum = Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
  )
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
  if (checksum !== result.headers.get("X-Content-SHA256"))
    throw new Error(
      "Export checksum verification failed. Request a new export and retry.",
    );
  const url = URL.createObjectURL(
    new Blob([bytes], {
      type: result.headers.get("Content-Type") || "application/octet-stream",
    }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `${versionId}.${format === "jsonl" ? "jsonl" : `${format}.zip`}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const date = (value: string) =>
  new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
export const money = (value: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 3,
  }).format(value);
export const shortId = (value: string) =>
  value.length > 22 ? value.slice(0, 10) + "…" + value.slice(-6) : value;
