import { NextRequest } from "next/server";

const origin = process.env.API_INTERNAL_URL || "http://localhost:8000";
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
    return new Response("Invalid path", { status: 400 });
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
  ]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  try {
    const result = await fetch(
      `${origin}/v1/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        cache: "no-store",
        redirect: "manual",
        body: ["GET", "HEAD"].includes(request.method)
          ? undefined
          : await request.arrayBuffer(),
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
    ]) {
      const value = result.headers.get(name);
      if (value) outgoing.set(name, value);
    }
    for (const cookie of result.headers.getSetCookie())
      outgoing.append("set-cookie", cookie);
    return new Response(result.body, {
      status: result.status,
      headers: outgoing,
    });
  } catch {
    return Response.json(
      {
        status: 503,
        code: "API_UNAVAILABLE",
        detail: "The control API is unavailable. Check the local services.",
      },
      { status: 503 },
    );
  }
}
export { proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE };
