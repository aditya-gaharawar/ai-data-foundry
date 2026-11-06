import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync, readFileSync } from "node:fs";
import { request as httpRequest } from "node:http";

const password = readFileSync(".env", "utf8")
  .split("\n")
  .find((line) => line.startsWith("DEV_PASSWORD="))!
  .slice("DEV_PASSWORD=".length);

async function signIn(page: Page, email = "alex@foundry.local") {
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
}

test("API outage has an accessible recovery screen and reconnects to real sign-in", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/v1/auth/session", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/problem+json",
      body: JSON.stringify({
        code: "API_UNAVAILABLE",
        detail: "The control API is unavailable.",
        request_id: "req_recovery_test",
      }),
    }),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/overview");
  await expect(
    page.getByRole("heading", { name: "Unable to open your workspace" }),
  ).toBeVisible();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "req_recovery_test",
  );
  await expect(page.getByLabel("Password", { exact: true })).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  mkdirSync("verification/evidence/p14", { recursive: true });
  await page.screenshot({
    path: "verification/evidence/p14/session-recovery-mobile.png",
    fullPage: true,
  });
  await page.unroute("**/api/v1/auth/session");
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome to Foundry" }),
  ).toBeVisible();
  await signIn(page);
  expect(errors).toEqual([]);
});

for (const payload of [
  "null",
  '{"detail":{"unexpected":"object"}}',
  "upstream offline",
]) {
  test(`malformed API errors remain actionable: ${payload}`, async ({
    page,
  }) => {
    await page.route("**/api/v1/auth/session", (route) =>
      route.fulfill({
        status: 502,
        contentType: "application/json",
        body: payload,
        headers: { "X-Request-Id": "req_malformed_error" },
      }),
    );
    await page.goto("/login");
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
      "The request could not be completed",
    );
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
      "req_malformed_error",
    );
    await expect(
      page.getByRole("button", { name: "Try again", exact: true }),
    ).toBeEnabled();
  });
}

test("network failure and unreadable success responses support retry", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/session", (route) => route.abort("failed"));
  await page.goto("/login");
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Check your connection",
  );
  await page.unroute("**/api/v1/auth/session");
  await page.route("**/api/v1/auth/session", (route) =>
    route.fulfill({ status: 200, body: "invalid JSON" }),
  );
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "unreadable response",
  );
  await page.unroute("**/api/v1/auth/session");
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
});

test("expired session hides cached workspace and allows another user to sign in", async ({
  page,
  context,
}) => {
  await page.goto("/login");
  await signIn(page);
  await expect(
    page.getByLabel("Organization", { exact: true }).locator("option:checked"),
  ).toHaveText("Atlas Research");
  await context.clearCookies();
  await page.getByRole("link", { name: "Datasets", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome to Foundry" }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Main navigation" }),
  ).toHaveCount(0);
  await signIn(page, "blair@foundry.local");
  await expect(
    page.getByLabel("Organization", { exact: true }).locator("option:checked"),
  ).toHaveText("Meridian Lab");
  await expect(page.getByText("Atlas Research", { exact: true })).toHaveCount(
    0,
  );
});

test("background session expiry replaces a cached successful session", async ({
  page,
  context,
}) => {
  await page.goto("/login");
  await signIn(page);
  // Let the cached session become stale before expiring its cookie.
  await page.waitForTimeout(2100);
  await context.clearCookies();
  const checked = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/auth/session") &&
      response.status() === 401,
  );
  await page.evaluate(() =>
    window.dispatchEvent(new Event("visibilitychange")),
  );
  await checked;
  await expect(
    page.getByRole("heading", { name: "Welcome to Foundry" }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Main navigation" }),
  ).toHaveCount(0);
});

test("proxy bounds both declared and chunked bodies without rejecting the exact limit", async ({
  request,
}) => {
  const oversized = await request.post("/api/v1/projects", {
    data: "x".repeat(1024 * 1024 + 1),
  });
  expect(oversized.status()).toBe(413);
  const problem = await oversized.json();
  expect(problem.code).toBe("REQUEST_TOO_LARGE");
  expect(problem.request_id).toMatch(/^req_proxy_/);
  expect(oversized.headers()["x-request-id"]).toBe(problem.request_id);
  expect(oversized.headers()["cache-control"]).toBe("no-store");

  const chunked = await new Promise<{ status: number; body: string }>(
    (resolve, reject) => {
      const outgoing = httpRequest(
        "http://localhost:3000/api/v1/projects",
        { method: "POST", headers: { "Content-Type": "application/json" } },
        (incoming) => {
          let body = "";
          incoming.setEncoding("utf8");
          incoming.on("data", (chunk) => {
            body += chunk;
          });
          incoming.on("end", () =>
            resolve({ status: incoming.statusCode!, body }),
          );
          incoming.on("error", reject);
        },
      );
      outgoing.on("error", reject);
      for (let count = 0; count < 17; count++)
        outgoing.write(Buffer.alloc(65536, "x"));
      outgoing.end();
    },
  );
  expect(chunked.status).toBe(413);
  expect(JSON.parse(chunked.body).request_id).toMatch(/^req_proxy_/);

  const exact = await request.post("/api/v1/projects", {
    data: JSON.stringify({ name: "x".repeat(1024 * 1024 - 11) }),
    headers: { "Content-Type": "application/json" },
  });
  expect([401, 422]).toContain(exact.status());
  expect(exact.headers()["x-request-id"]).not.toMatch(/^req_proxy_/);
});
