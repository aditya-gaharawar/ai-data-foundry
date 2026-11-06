import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, readFileSync } from "node:fs";

const evidence = "verification/evidence/p13/screenshots";
mkdirSync(evidence, { recursive: true });
const password = readFileSync(".env", "utf8")
  .split("\n")
  .find((line) => line.startsWith("DEV_PASSWORD="))!
  .slice("DEV_PASSWORD=".length);
const istInput = (delay: number) =>
  new Date(Date.now() + delay + 330 * 60_000).toISOString().slice(0, 19);

async function signIn(page: Page) {
  await page.goto("/login");
  await page
    .getByLabel("Email address", { exact: true })
    .fill("alex@foundry.local");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
}

async function api<T>(
  page: Page,
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  return page.evaluate(
    async ({ path, method, body }) => {
      const session = await (await fetch("/api/v1/auth/session")).json();
      const response = await fetch(`/api/v1${path}`, {
        method,
        headers: {
          "Content-Type": "application/json",
          "X-Organization-Id": session.organizations[0].id,
          "X-CSRF-Token": session.csrf_token,
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const result = await response.json();
      if (!response.ok)
        throw Error(`${response.status} ${result.code}: ${result.detail}`);
      return result;
    },
    { path, method, body },
  ) as Promise<T>;
}

async function source(page: Page) {
  const project = (await api<{ items: { id: string }[] }>(page, "/projects"))
    .items[0].id;
  const data = await api<{ id: string; name: string }>(
    page,
    "/datasets",
    "POST",
    {
      project_id: project,
      name: `P13 browser dataset ${Date.now()}`,
      policy: {
        origin: "synthetic-browser-fixture",
        license: "local-synthetic",
        allowed_training_use: true,
      },
    },
  );
  const recipe = await api<{ id: string; revision: { id: string } }>(
    page,
    "/recipes",
    "POST",
    {
      project_id: project,
      definition: {
        name: `P13 browser workflow ${Date.now()}`,
        schema_version: "1.0",
        budget: { currency: "USD", maximum: 1 },
        nodes: [
          {
            id: "source",
            type: "generate",
            config: { count: 3, seed: Date.now() % 2147483647 },
          },
          {
            id: "quality",
            type: "validate",
            config: {
              minimum_samples: 3,
              max_duplicate_ratio: 0,
              max_invalid_ratio: 0,
            },
          },
          { id: "publish", type: "publish", config: {} },
        ],
        edges: [
          { from: "source", to: "quality" },
          { from: "quality", to: "publish" },
        ],
      },
    },
  );
  return { data, recipe };
}

async function fillSchedule(
  page: Page,
  data: { id: string },
  recipe: { id: string },
  name: string,
  delay = 20_000,
) {
  await page
    .getByRole("button", { name: "Create schedule", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Create a bounded schedule",
  });
  await dialog.getByLabel("Schedule name", { exact: true }).fill(name);
  await dialog
    .getByLabel("Schedule dataset", { exact: true })
    .selectOption(data.id);
  await dialog
    .getByLabel("Schedule workflow", { exact: true })
    .selectOption(recipe.id);
  await expect(
    dialog.getByLabel("Pinned revision", { exact: true }).locator("option"),
  ).toHaveCount(2);
  await dialog
    .getByLabel("Pinned revision", { exact: true })
    .selectOption({ index: 1 });
  await dialog.getByLabel("Interval (seconds)", { exact: true }).fill("10");
  await dialog
    .getByLabel("Schedule start (IST)", { exact: true })
    .fill(istInput(delay));
  await dialog
    .getByLabel("Schedule end (IST)", { exact: true })
    .fill(istInput(300_000));
  await dialog.getByLabel("Maximum launches", { exact: true }).fill("1");
  return dialog;
}

test("schedule preview and approval publish a real version and private inbox notice", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page);
  const { data, recipe } = await source(page);
  await page.goto("/schedules");
  const name = `P13 browser bounded ${Date.now()}`;
  const dialog = await fillSchedule(page, data, recipe, name);
  await dialog
    .getByRole("button", { name: "Preview launches and cost" })
    .click();
  await expect(dialog.getByLabel("Schedule preview")).toContainText(
    "3 samples",
  );
  await expect(
    dialog.getByRole("button", { name: "Activate schedule" }),
  ).toBeDisabled();
  await dialog
    .getByRole("button", { name: "Activate schedule" })
    .scrollIntoViewIfNeeded();
  await dialog.screenshot({
    path: `${evidence}/schedule-preview-light.png`,
  });
  await dialog
    .getByRole("checkbox", { name: /I approve these scheduled launches/ })
    .check();
  await dialog.getByRole("button", { name: "Activate schedule" }).click();
  await expect(dialog).not.toBeVisible();
  const detail = page.getByRole("region", { name: "Schedule details" });
  await expect(detail.getByRole("heading", { name })).toBeVisible();
  await expect(detail.getByText("completed", { exact: true })).toBeVisible({
    timeout: 45_000,
  });
  await expect(detail.getByRole("link", { name: "Open run →" })).toBeVisible();
  const runPath = (await detail
    .getByRole("link", { name: "Open run →" })
    .getAttribute("href"))!;
  await expect
    .poll(
      async () =>
        (await api<{ status: string; version: unknown }>(page, runPath)).status,
    )
    .toBe("SUCCEEDED");
  const published = await api<{
    version: { sample_count: number; manifest_hash: string };
  }>(page, runPath);
  expect(published.version.sample_count).toBe(3);
  expect(published.version.manifest_hash).toMatch(/^[a-f0-9]{64}$/);
  await page.screenshot({
    path: `${evidence}/schedules-light-desktop.png`,
    fullPage: true,
  });
  const violations = (await new AxeBuilder({ page }).analyze()).violations;
  expect(violations).toEqual([]);
  await page.getByRole("link", { name: /^Notifications,/ }).click();
  await expect(
    page.getByRole("heading", { name: "Notifications", exact: true }),
  ).toBeVisible();
  const notice = page
    .locator("article")
    .filter({ has: page.locator(`a[href="${runPath}"]`) });
  await expect(notice).toContainText("Run published");
  await notice
    .getByRole("button", { name: "Mark Run published as read" })
    .click();
  await expect(notice.getByText("Read", { exact: true })).toBeVisible();
  // Create a new real unread outcome; the test must also work on a previously read inbox.
  const another = await api<{ id: string }>(page, "/runs", "POST", {
    dataset_id: data.id,
    recipe_revision_id: recipe.revision.id,
    max_budget_usd: 1,
  });
  await expect
    .poll(
      async () =>
        (await api<{ status: string }>(page, `/runs/${another.id}`)).status,
    )
    .toBe("SUCCEEDED");
  await expect(
    page.getByRole("button", { name: "Mark all as read" }),
  ).toBeEnabled();
  await expect(
    page.locator(`article a[href="/runs/${another.id}"]`),
  ).toBeVisible();
  await page.getByRole("button", { name: "Mark all as read" }).click();
  await expect(page.getByText("0 unread", { exact: true })).toBeVisible();
  await page.screenshot({
    path: `${evidence}/notifications-light-desktop.png`,
    fullPage: true,
  });
  await page.getByRole("button", { name: "Toggle color theme" }).click();
  await page.screenshot({
    path: `${evidence}/notifications-dark-desktop.png`,
    fullPage: true,
  });
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("schedule pause resume cancel and responsive dark inbox controls", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page);
  const { data, recipe } = await source(page);
  await page.goto("/schedules");
  const name = `P13 browser controlled ${Date.now()}`;
  const dialog = await fillSchedule(page, data, recipe, name, 120_000);
  await dialog
    .getByRole("button", { name: "Preview launches and cost" })
    .click();
  await dialog
    .getByRole("checkbox", { name: /I approve these scheduled launches/ })
    .check();
  await dialog.getByRole("button", { name: "Activate schedule" }).click();
  const detail = page.getByRole("region", { name: "Schedule details" });
  await detail.getByRole("button", { name: "Pause schedule" }).click();
  await expect(detail.getByText("paused", { exact: true })).toBeVisible();
  await expect(
    detail.getByRole("button", { name: "Resume schedule" }),
  ).toBeDisabled();
  await detail
    .getByRole("checkbox", { name: /I authorize future launches/ })
    .check();
  await detail.getByRole("button", { name: "Resume schedule" }).click();
  await expect(detail.getByText("active", { exact: true })).toBeVisible();
  await detail.getByRole("button", { name: "Cancel schedule" }).click();
  await expect(detail.getByText("cancelled", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Toggle color theme" }).click();
  await page.screenshot({
    path: `${evidence}/schedules-dark-desktop.png`,
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: `${evidence}/schedules-dark-mobile.png`,
    fullPage: true,
  });
  await page.getByRole("link", { name: /^Notifications,/ }).click();
  await expect(
    page.getByRole("heading", { name: "Notifications", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/^\d+ unread$/)).toBeVisible();
  const markAll = page.getByRole("button", { name: "Mark all as read" });
  if (await markAll.isEnabled()) await markAll.click();
  await expect(page.getByText("0 unread", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: "Unread only" }).check();
  await expect(
    page.getByText("You're all caught up", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: `${evidence}/notifications-dark-mobile.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
