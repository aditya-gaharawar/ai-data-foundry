import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFileSync, mkdirSync } from "node:fs";
import { randomBytes } from "node:crypto";

const env = Object.fromEntries(
  readFileSync(".env", "utf8")
    .trim()
    .split("\n")
    .map((line) => {
      const index = line.indexOf("=");
      return [line.slice(0, index), line.slice(index + 1)];
    }),
);
mkdirSync("verification/evidence/screenshots", { recursive: true });
async function signIn(
  page: Page,
  email = "alex@foundry.local",
  password = env.DEV_PASSWORD,
) {
  await page.goto("/login");
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
}

test("create → durable run → quality → immutable version → real JSONL download", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await signIn(page);
  await page
    .getByRole("button", { name: "Create dataset", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  const name = `Browser verified dataset ${Date.now()}`;
  await dialog.getByLabel("Dataset name", { exact: true }).fill(name);
  await dialog
    .getByLabel("Description (optional)")
    .fill(
      "100 deterministic examples, validated and exported through the real API.",
    );
  await dialog.getByRole("checkbox").check();
  await dialog
    .getByRole("button", { name: "Create dataset", exact: true })
    .click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Build workflow", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "Recipe JSON", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "verification/evidence/screenshots/workflow-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Save workflow", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Launch run", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Launch run", exact: true }).click();
  await page
    .getByRole("button", { name: "Confirm & launch", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Export JSONL", exact: true }),
  ).toBeVisible({ timeout: 60000 });
  await expect(page.getByText("Passed", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "verification/evidence/screenshots/run-desktop.png",
    fullPage: true,
  });
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSONL", exact: true }).click();
  const download = await downloadEvent;
  const file = await download.path();
  expect(file).not.toBeNull();
  const records = readFileSync(file!, "utf8")
    .trim()
    .split("\n")
    .map((line) => JSON.parse(line));
  expect(records).toHaveLength(100);
  expect(
    records.every(
      (record) =>
        record.payload.prompt &&
        record.content_hash &&
        record.dataset_version_id,
    ),
  ).toBe(true);
  await page.getByRole("link", { name: "View dataset", exact: true }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await expect(
    page.getByText("Sample explorer", { exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Quality", exact: true }).click();
  await expect(page.getByText("Quality report", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test("administrator provisions a separate viewer account and permissions apply", async ({
  page,
  browser,
}) => {
  await signIn(page);
  await page.getByRole("link", { name: "Members", exact: true }).click();
  await page.getByRole("button", { name: "Add member", exact: true }).click();
  const email = `viewer-${Date.now()}@foundry.local`;
  const password = randomBytes(18).toString("base64url");
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Full name", { exact: true }).fill("Browser Viewer");
  await dialog.getByLabel("Email address", { exact: true }).fill(email);
  await dialog.getByLabel(/^Initial password/).fill(password);
  await dialog.getByRole("combobox").selectOption("Viewer");
  await dialog.getByRole("button", { name: "Add member", exact: true }).click();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  const context = await browser.newContext();
  const viewer = await context.newPage();
  await signIn(viewer, email, password);
  await expect(
    viewer.getByRole("button", { name: "Create dataset", exact: true }),
  ).toHaveCount(0);
  await expect(
    viewer.getByRole("link", { name: "API keys", exact: true }),
  ).toHaveCount(0);
  await viewer.goto("/settings/api-keys");
  await expect(
    viewer.getByRole("alert").filter({ hasText: "requires keys:manage" }),
  ).toBeVisible();
  await context.close();
});

test("priority routes are responsive, accessible, and support both themes", async ({
  page,
}) => {
  await signIn(page);
  const routes = [
    "overview",
    "datasets",
    "workflows/new",
    "runs",
    "settings/api-keys",
  ];
  for (const theme of ["light", "dark"]) {
    await page.evaluate((value) => localStorage.setItem("theme", value), theme);
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 960 });
      await page.goto("/overview");
      await expect(
        page.getByRole("heading", { name: "Overview", exact: true }),
      ).toBeVisible();
      await expect(page.locator("html")).toHaveClass(new RegExp(theme));
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: `verification/evidence/screenshots/overview-${theme}-${width}.png`,
        fullPage: true,
      });
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    for (const route of routes) {
      await page.goto(`/${route}`);
      await expect(page.locator("main h1")).toBeVisible();
      await expect(page.locator(".loading-state")).toHaveCount(0);
      const audit = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();
      expect(
        audit.violations,
        JSON.stringify(
          audit.violations.map((value) => ({
            id: value.id,
            nodes: value.nodes.map((node) => node.target),
          })),
        ),
      ).toEqual([]);
      await page.screenshot({
        path: `verification/evidence/screenshots/${route.replaceAll("/", "-")}-${theme}-desktop.png`,
        fullPage: true,
      });
    }
  }
});

test("keyboard palette, mobile navigation, errors and logout", async ({
  page,
}) => {
  await signIn(page);
  await page.keyboard.press("Control+k");
  await expect(
    page.getByRole("dialog", { name: "Search workspace" }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Search pages and datasets" })
    .fill("Datasets");
  await page
    .getByRole("dialog")
    .getByRole("link", { name: "Datasets Page" })
    .focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Datasets", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 850 });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(
    page.getByRole("dialog", { name: "Workspace navigation" }),
  ).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("link", { name: "Runs", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Runs", exact: true }),
  ).toBeVisible();
  await page.route("**/api/v1/datasets?**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/problem+json",
      body: JSON.stringify({
        code: "DEPENDENCY_UNAVAILABLE",
        detail: "Object storage unavailable. Retry after recovery.",
        request_id: "req_e2e_failure",
      }),
    }),
  );
  await page.goto("/datasets");
  await expect(
    page.getByRole("alert").filter({ hasText: "Object storage unavailable" }),
  ).toContainText("Object storage unavailable");
  await page.unroute("**/api/v1/datasets?**");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Sign out", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Welcome to Foundry", exact: true }),
  ).toBeVisible();
});

test("browser multipart upload reaches a verified version and escapes sample HTML", async ({
  page,
}) => {
  await signIn(page);
  await page
    .getByRole("button", { name: "Create dataset", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  const name = `Browser upload ${Date.now()}`;
  await dialog.getByLabel("Dataset name", { exact: true }).fill(name);
  await dialog.getByRole("checkbox").check();
  await dialog
    .getByRole("button", { name: "Create dataset", exact: true })
    .click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  const source =
    Array.from({ length: 100 }, (_, index) =>
      JSON.stringify({
        prompt: `Uploaded record ${index} <img src=x onerror="window.__foundry_xss=true">`,
        response: String(index),
      }),
    ).join("\n") + "\n";
  await page.getByLabel("Upload JSONL source", { exact: true }).setInputFiles({
    name: "browser-source.jsonl",
    mimeType: "application/x-ndjson",
    buffer: Buffer.from(source),
  });
  await expect(
    page.getByText("browser-source.jsonl", { exact: true }),
  ).toBeVisible();
  await expect(
    page.locator(".source-row").filter({ hasText: "browser-source.jsonl" }),
  ).toContainText("completed", { timeout: 30000 });
  await page.getByRole("link", { name: "Build workflow", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Source", exact: true })
    .selectOption("ingest");
  await page
    .getByRole("combobox", { name: "Verified upload", exact: true })
    .selectOption({ label: "browser-source.jsonl · 100 samples" });
  await page
    .getByRole("button", { name: "Save workflow", exact: true })
    .click();
  await page.getByRole("button", { name: "Launch run", exact: true }).click();
  await page
    .getByRole("button", { name: "Confirm & launch", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Export JSONL", exact: true }),
  ).toBeVisible({ timeout: 60000 });
  await page.getByRole("link", { name: "View dataset", exact: true }).click();
  await expect(
    page.getByText(
      'Uploaded record 0 <img src=x onerror="window.__foundry_xss=true">',
      { exact: true },
    ),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => (window as Window & { __foundry_xss?: boolean }).__foundry_xss,
    ),
  ).toBeUndefined();
});
