import { NextRequest } from "next/server";

const origin = process.env.API_INTERNAL_URL || "http://localhost:8000";
const maxControlBytes = 1024 * 1024;

function problem(status: number, code: string, detail: string) {
  const requestId = `req_proxy_${crypto.randomUUID()}`;
  return Response.json(
    {
      type: `urn:foundry:problem:${code.toLowerCase()}`,
      title: code.replaceAll("_", " "),
      status,
      code,
      detail,
      request_id: requestId,
    },
    {
      status,
      headers: {
        "Content-Type": "application/problem+json",
        "Cache-Control": "no-store",
        "X-Request-Id": requestId,
      },
    },
  );
}

async function readBody(
  request: NextRequest,
): Promise<Uint8Array<ArrayBuffer> | null> {
  if (Number(request.headers.get("content-length")) > maxControlBytes)
    return null;
  const reader = request.body?.getReader();
  if (!reader) return new Uint8Array(0);
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxControlBytes) {
        await reader.cancel();
        return null;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const body = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  if (
    path.some(
      (segment) =>
        segment.includes("..") ||
        segment.includes("/") ||
        segment.includes("\\"),
    )
  ) {
    return problem(400, "INVALID_PATH", "The requested API path is invalid.");
  }
  const headers = new Headers();
  for (const name of [
    "content-type",
    "authorization",
    "cookie",
    "idempotency-key",
    "x-csrf-token",
    "x-organization-id",
    "origin",
    "if-match",
    "x-lease-token",
  ]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  try {
    const body = ["GET", "HEAD"].includes(request.method)
      ? undefined
      : await readBody(request);
    if (body === null)
      return problem(
        413,
        "REQUEST_TOO_LARGE",
        "JSON control requests are limited to 1 MiB; dataset uploads use bounded object-storage sessions.",
      );
    const result = await fetch(
      `${origin}/v1/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        cache: "no-store",
        redirect: "manual",
        body,
        signal: AbortSignal.timeout(30000),
      },
    );
    const outgoing = new Headers();
    for (const name of [
      "content-type",
      "content-disposition",
      "x-request-id",
      "x-content-sha256",
      "cache-control",
      "location",
      "etag",
      "retry-after",
    ]) {
      const value = result.headers.get(name);
      if (value) outgoing.set(name, value);
    }
    for (const cookie of result.headers.getSetCookie())
      outgoing.append("set-cookie", cookie);
    outgoing.set("cache-control", "no-store");
    return new Response(result.body, {
      status: result.status,
      headers: outgoing,
    });
  } catch (error) {
    if (error instanceof Error && error.name === "TimeoutError")
      return problem(
        504,
        "API_TIMEOUT",
        "The control API took too long to respond. Please try again.",
      );
    return problem(
      503,
      "API_UNAVAILABLE",
      "The control API is unavailable. Check the local services and try again.",
    );
  }
}
export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
};
