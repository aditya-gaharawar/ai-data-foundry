import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync, mkdirSync } from "node:fs";

const password = readFileSync(".env", "utf8")
  .split("\n")
  .find((line) => line.startsWith("DEV_PASSWORD="))!
  .slice("DEV_PASSWORD=".length);
const evidence = "verification/evidence/p07-p12/screenshots";
mkdirSync(evidence, { recursive: true });

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
async function api<T = Record<string, unknown>>(
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
      const value = await response.json();
      if (!response.ok)
        throw new Error(`${response.status} ${value.code}: ${value.detail}`);
      return value;
    },
    { path, method, body },
  ) as Promise<T>;
}
async function createDataset(
  page: Page,
  modality = "text",
  name = `Browser expansion ${Date.now()}`,
) {
  const projects = await api<{ items: { id: string }[] }>(page, "/projects");
  return api<{ id: string; name: string; project_id: string }>(
    page,
    "/datasets",
    "POST",
    {
      name,
      project_id: projects.items[0].id,
      modality,
      policy: {
        origin: "synthetic-browser-fixture",
        license: "local-synthetic",
        allowed_training_use: true,
      },
    },
  );
}
async function generate(
  page: Page,
  data: { id: string; project_id: string },
  seed = Date.now() % 10000000,
) {
  const recipe = await api<{ revision: { id: string } }>(
    page,
    "/recipes",
    "POST",
    {
      project_id: data.project_id,
      definition: {
        name: "Browser deterministic source",
        schema_version: "1.0",
        nodes: [
          { id: "source", type: "generate", config: { count: 3, seed } },
          {
            id: "validate",
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
          { from: "source", to: "validate" },
          { from: "validate", to: "publish" },
        ],
        budget: { currency: "USD", maximum: 1 },
      },
    },
  );
  const run = await api<{ id: string }>(page, "/runs", "POST", {
    dataset_id: data.id,
    recipe_revision_id: recipe.revision.id,
    max_budget_usd: 1,
  });
  return waitRun(page, run.id);
}
async function waitRun(page: Page, id: string) {
  await expect
    .poll(
      async () => (await api<{ status: string }>(page, `/runs/${id}`)).status,
      { timeout: 180000 },
    )
    .toBe("SUCCEEDED");
  return api<{ status: string; version: { id: string; number: number } }>(
    page,
    `/runs/${id}`,
  );
}
async function screenshot(page: Page, name: string) {
  await page.screenshot({
    path: `${evidence}/${name}.png`,
    animations: "disabled",
  });
}

test("Teacher Studio records rights and launches genuine local inference", async ({
  page,
}) => {
  test.setTimeout(240000);
  await signIn(page);
  const data = await createDataset(
    page,
    "text",
    `Browser model output ${Date.now()}`,
  );
  await page.route("**/api/v1/providers/catalog", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1200));
    await route.continue();
  });
  await page.goto("/teacher");
  await page
    .getByRole("button", { name: "Connect provider", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  const name = `Browser local model ${Date.now()}`;
  await dialog.getByLabel("Connection name", { exact: true }).fill(name);
  await dialog
    .getByLabel("Rights evidence", { exact: true })
    .fill(
      "Apache-2.0 public model. Local synthetic browser proof only; no factual quality claim.",
    );
  await dialog.getByRole("checkbox").check();
  await dialog
    .getByRole("button", { name: "Save connection", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  const connection = await api<{ items: { id: string; name: string }[] }>(
    page,
    "/providers?limit=100",
  );
  const id = connection.items.find((item) => item.name === name)!.id;
  await page
    .getByLabel("Target dataset", { exact: true })
    .selectOption(data.id);
  await page
    .getByLabel("Provider connection", { exact: true })
    .selectOption(id);
  await page
    .getByLabel("Generation instructions", { exact: true })
    .fill("Write one short instruction and answer about numbers.");
  await page
    .getByRole("button", { name: "Save recipe & estimate", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Start generation", exact: true }),
  ).toBeEnabled();
  await screenshot(page, "teacher-estimated-light");
  await page
    .getByRole("button", { name: "Start generation", exact: true })
    .click();
  await expect(page).toHaveURL(/\/runs\/run_/);
  const run = await waitRun(page, page.url().split("/").at(-1)!);
  expect(run.version.id).toBeTruthy();
  await page.goto(`/datasets/${data.id}`);
  await expect(
    page.getByText("No published samples yet", { exact: true }),
  ).toHaveCount(0);
  await screenshot(page, "teacher-real-output-light");
  const samples = await api<{
    items: {
      review_status: string;
      payload: { prompt: string; response: string };
    }[];
  }>(page, `/datasets/${data.id}/samples`);
  expect(samples.items[0].review_status).toBe("UNREVIEWED_MODEL");
  expect(samples.items[0].payload.response.length).toBeGreaterThan(0);
});

test("Simulation Studio renders frames and shows a verified protected 3D scene", async ({
  page,
}) => {
  test.setTimeout(240000);
  await signIn(page);
  const data = await createDataset(
    page,
    "image",
    `Browser Blender scene ${Date.now()}`,
  );
  await page.goto("/simulations");
  await page
    .getByLabel("Target dataset", { exact: true })
    .selectOption(data.id);
  await page.getByLabel("Frames per scene", { exact: true }).fill("2");
  await page.getByLabel("Resolution", { exact: true }).selectOption("64");
  await page
    .getByRole("button", { name: "Save recipe & estimate", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Start render", exact: true }),
  ).toBeEnabled();
  await screenshot(page, "simulation-admission-light");
  await page.getByRole("button", { name: "Start render", exact: true }).click();
  await expect(page).toHaveURL(/\/runs\/run_/);
  await waitRun(page, page.url().split("/").at(-1)!);
  await page.goto(`/datasets/${data.id}`);
  await page
    .getByText("Inspect scene, object mask & sensor metadata", { exact: true })
    .first()
    .click();
  await expect(
    page.getByText(
      "Verified GLB · drag to orbit, scroll to zoom, arrow keys to pan",
      { exact: true },
    ),
  ).toBeVisible({ timeout: 45000 });
  await expect(
    page.getByRole("img", { name: "Rendered object-index mask", exact: true }),
  ).toBeVisible();
  await screenshot(page, "simulation-frame-scene-mask-light");
});

test("Compute console enrolls an actual outbound verifier and records its result", async ({
  page,
}) => {
  test.setTimeout(180000);
  await signIn(page);
  const data = await createDataset(page);
  await generate(page, data);
  await page.goto("/compute");
  await page
    .getByRole("button", { name: "Register pool", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  const name = `Browser CPU ${Date.now()}`;
  await dialog.getByLabel("Pool name", { exact: true }).fill(name);
  await dialog
    .getByRole("button", { name: "Register pool", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  await page
    .getByLabel("Agent name", { exact: true })
    .fill(`Browser verifier ${Date.now()}`);
  await page
    .getByRole("button", { name: "Enroll in selected pool", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Save agent credential", exact: true }),
  ).toBeVisible();
  const token = await page
    .getByRole("dialog")
    .locator(".secret-box code")
    .innerText();
  await page
    .getByRole("button", { name: "I saved the credential", exact: true })
    .click();
  await page
    .getByLabel("Dataset to verify", { exact: true })
    .selectOption(data.id);
  const versions = await api<{ items: { id: string }[] }>(
    page,
    `/datasets/${data.id}/versions`,
  );
  await page
    .getByLabel("Artifact version", { exact: true })
    .selectOption(versions.items[0].id);
  await page
    .getByRole("button", { name: "Queue verification", exact: true })
    .click();
  await expect(
    page.getByText("Artifact verification queued.", { exact: true }),
  ).toBeVisible();
  execFileSync(".venv/bin/python", ["-m", "foundry.agent", "--once"], {
    env: { ...process.env, FOUNDRY_AGENT_TOKEN: token },
    timeout: 30000,
    stdio: "pipe",
  });
  await expect(
    page.getByText("Checksum verified by API", { exact: true }).first(),
  ).toBeVisible();
  await screenshot(page, "compute-real-agent-result-light");
});

test("Evaluations console compares versions, imports fixture counts, and saves approved feedback", async ({
  page,
}) => {
  test.setTimeout(240000);
  await signIn(page);
  const training = await createDataset(
    page,
    "text",
    `Browser evaluation training ${Date.now()}`,
  );
  const left = await generate(page, training, 391122);
  const right = await generate(page, training, 391123);
  const held = await createDataset(
    page,
    "text",
    `Browser benchmark ${Date.now()}`,
  );
  const heldRun = await generate(page, held, Date.now() % 10000000);
  await api(page, `/governance/datasets/${held.id}`, "POST", {
    expected_revision: 1,
    action: "protect_holdout",
    note: "Independent synthetic benchmark fixture, no model gain claim",
  });
  await page.goto("/evaluations");
  await page.getByLabel("Search text", { exact: true }).fill("Example");
  await page
    .getByRole("button", { name: "Search samples", exact: true })
    .click();
  await expect(page.locator(".record-row").first()).toBeVisible();
  await page
    .getByLabel("Baseline dataset", { exact: true })
    .selectOption(training.id);
  await page
    .getByLabel("Baseline version", { exact: true })
    .selectOption(left.version.id);
  await page
    .getByLabel("Candidate dataset", { exact: true })
    .selectOption(training.id);
  await page
    .getByLabel("Candidate version", { exact: true })
    .selectOption(right.version.id);
  await page
    .getByRole("button", { name: "Compare versions", exact: true })
    .click();
  await expect(
    page.locator("pre").filter({ hasText: '"added": 3' }),
  ).toBeVisible();
  await page
    .getByText("Register a protected benchmark", { exact: true })
    .click();
  await page
    .getByLabel("Holdout dataset", { exact: true })
    .selectOption(held.id);
  await page
    .getByLabel("Holdout version", { exact: true })
    .selectOption(heldRun.version.id);
  const benchmark = `Browser fixed fixture ${Date.now()}`;
  await page.getByLabel("Benchmark name", { exact: true }).fill(benchmark);
  await page
    .getByLabel("Benchmark source reference", { exact: true })
    .fill("local:synthetic-browser-fixture");
  await page
    .getByLabel("Benchmark evidence kind", { exact: true })
    .selectOption("synthetic_fixture");
  await page
    .getByLabel(
      "This benchmark is independent of the training data being evaluated.",
      { exact: true },
    )
    .check();
  await page
    .getByRole("button", { name: "Register benchmark", exact: true })
    .click();
  await expect(
    page.getByText("Benchmark registered with frozen evidence.", {
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByLabel("Training dataset", { exact: true })
    .selectOption(training.id);
  await page
    .getByLabel("Training version", { exact: true })
    .selectOption(right.version.id);
  await page
    .getByLabel("Evaluated model reference", { exact: true })
    .fill("synthetic-counts-fixture");
  await page
    .getByLabel("External evaluation run reference", { exact: true })
    .fill(`fixture:${Date.now()}`);
  await page.getByLabel("Total answers", { exact: true }).fill("10");
  await page.getByLabel("Correct answers", { exact: true }).fill("8");
  await page
    .getByLabel("Failure slice name (optional)", { exact: true })
    .fill("arithmetic");
  await page.getByLabel("Slice total", { exact: true }).fill("5");
  await page.getByLabel("Slice correct", { exact: true }).fill("2");
  await page
    .getByLabel("Evidence and limitations", { exact: true })
    .fill(
      "Synthetic imported counts exercise this protocol only. No model or scientific improvement was measured.",
    );
  // A slow list refresh must not leave a successfully imported evaluation
  // missing from the feedback form's required select.
  let delayEvaluationRefresh = true;
  await page.route("**/api/v1/evaluations?limit=100", async (route) => {
    if (delayEvaluationRefresh)
      await new Promise((resolve) => setTimeout(resolve, 1200));
    await route.continue();
  });
  const importedResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/evaluations") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Import results", exact: true })
    .click();
  const imported = await (await importedResponse).json();
  await expect(
    page.getByText("Evaluation imported with immutable evidence.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Source evaluation", { exact: true }),
  ).toHaveValue(imported.id);
  const feedbackResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/feedback") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Save feedback proposal", exact: true })
    .click();
  expect((await (await feedbackResponse).json()).evaluation_id).toBe(
    imported.id,
  );
  await expect(
    page.getByText("Bounded feedback proposal saved.", { exact: true }),
  ).toBeVisible();
  delayEvaluationRefresh = false;
  await page
    .getByLabel("Feedback decision note", { exact: true })
    .fill("Reviewed bounded fixture recommendation, manual launch only");
  const proposals = page.locator("details").filter({
    has: page.locator("summary .status").filter({ hasText: "draft" }),
  });
  await proposals.first().locator("summary").click();
  await proposals
    .first()
    .getByRole("button", { name: "Approve proposal", exact: true })
    .click();
  await expect(
    page.getByText("Feedback decision saved.", { exact: true }),
  ).toBeVisible();
  await screenshot(page, "evaluation-diff-feedback-light");
  await page.unrouteAll({ behavior: "wait" });
});

test("Governance console records policy, legal hold, independent request, and SCIM revocation", async ({
  page,
}) => {
  test.setTimeout(180000);
  await signIn(page);
  const data = await createDataset(
    page,
    "text",
    `Browser governance ${Date.now()}`,
  );
  const protectionNote = `Browser hold and independent release request proof ${Date.now()}`;
  try {
    await page.goto("/settings/governance");
    await page
      .getByRole("button", { name: "Load current values", exact: true })
      .click();
    await page
      .getByLabel("Retention period (days)", { exact: true })
      .fill("31");
    await page
      .getByRole("button", { name: "Save policy revision", exact: true })
      .click();
    await expect(
      page.getByText("New policy revision enforced.", { exact: true }),
    ).toBeVisible();
    await page
      .getByLabel("Dataset to protect", { exact: true })
      .selectOption(data.id);
    await page
      .getByLabel("Protection decision note", { exact: true })
      .fill(protectionNote);
    await page
      .getByRole("button", { name: "Place legal hold", exact: true })
      .click();
    await expect(
      page.getByText("Legal hold active", { exact: false }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Request hold release", exact: true })
      .click();
    await page
      .getByLabel("Approval decision note", { exact: true })
      .fill("A separate administrator must approve this request");
    const own = page.locator(".record-row").filter({
      hasText: protectionNote,
    });
    await expect(
      own.getByRole("button", { name: "Approve release", exact: true }),
    ).toBeDisabled();
    const tokenName = `Browser SCIM ${Date.now()}`;
    await page
      .getByLabel("Provisioning token name", { exact: true })
      .fill(tokenName);
    await page
      .getByRole("button", { name: "Create provisioning token", exact: true })
      .click();
    await page
      .getByRole("button", { name: "I saved the credential", exact: true })
      .click();
    const row = page.locator(".record-row").filter({ hasText: tokenName });
    await row.getByRole("button", { name: "Revoke", exact: true }).click();
    await expect(
      row.getByText("foundry.local · Revoked", { exact: true }),
    ).toBeVisible();
    await screenshot(page, "governance-policy-approval-light");
  } finally {
    await api(page, "/governance/policies", "POST", { definition: {} });
  }
});

test("Governance erasure previews a sealed plan and completes after independent approval", async ({
  page,
  playwright,
}) => {
  test.setTimeout(180000);
  await signIn(page);
  const data = await createDataset(
    page,
    "text",
    `Browser disposable erasure ${Date.now()}`,
  );
  await generate(page, data);
  await api(page, "/governance/policies", "POST", {
    definition: { erasure_delay_seconds: 0 },
  });
  const email = `browser-approver-${Date.now()}@foundry.local`;
  const secret = `local-approver-${Date.now()}-isolated`;
  await api(page, "/members", "POST", {
    name: "Independent browser erasure reviewer",
    email,
    password: secret,
    role: "Admin",
  });
  try {
    await page.goto("/settings/governance");
    await page
      .getByLabel("Dataset for erasure request", { exact: true })
      .selectOption(data.id);
    const reason = `Disposable browser fixture removal ${Date.now()}`;
    await page.getByLabel("Erasure reason", { exact: true }).fill(reason);
    await page
      .getByRole("button", { name: "Request artifact erasure", exact: true })
      .click();
    await expect(
      page.getByText("Erasure request saved for independent approval.", {
        exact: true,
      }),
    ).toBeVisible();
    const records = await api<{ items: { id: string; dataset_id: string }[] }>(
      page,
      "/governance/erasures",
    );
    const id = records.items.find((item) => item.dataset_id === data.id)!.id;
    const approver = await playwright.request.newContext({
      baseURL: "http://localhost:8000",
      extraHTTPHeaders: { Origin: "http://localhost:3000" },
    });
    try {
      const login = await approver.post("/v1/auth/login", {
        data: { email, password: secret },
      });
      expect(login.ok()).toBeTruthy();
      const auth = await login.json();
      const approval = await approver.post(
        `/v1/governance/erasures/${id}/decision`,
        {
          headers: {
            "X-CSRF-Token": auth.csrf_token,
            "X-Organization-Id": auth.organizations[0].id,
            "Idempotency-Key": crypto.randomUUID(),
          },
          data: {
            decision: "approve",
            note: "Reviewed independent local synthetic browser fixture",
          },
        },
      );
      expect(approval.status()).toBe(200);
    } finally {
      await approver.dispose();
    }
    const row = page.locator(".record-row").filter({ hasText: reason });
    await row
      .getByRole("button", { name: "Preview erasure plan", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText(data.name, { exact: true })).toBeVisible();
    await dialog
      .getByLabel("Confirm exact dataset name", { exact: true })
      .fill(data.name);
    await screenshot(page, "erasure-sealed-plan-light");
    await dialog
      .getByRole("button", { name: "Start artifact erasure", exact: true })
      .click();
    await expect(dialog).toBeHidden();
    await expect
      .poll(
        async () =>
          (await api<{ status: string }>(page, `/governance/erasures/${id}`))
            .status,
        { timeout: 45000 },
      )
      .toBe("ERASED");
    await expect(row.locator(".status")).toHaveText(/erased/);
    await screenshot(page, "erasure-worker-completed-light");
  } finally {
    await api(page, "/governance/policies", "POST", { definition: {} });
  }
});

test("Operations console persists reconciliation, incidents, and signed readiness", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/operations");
  await page
    .getByRole("button", { name: "Reconcile ledger", exact: true })
    .click();
  await expect(
    page.getByText("Ledger reconciliation recorded.", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Scan incidents", exact: true })
    .click();
  await expect(
    page.getByText("Actual failure signals scanned.", { exact: true }),
  ).toBeVisible();
  const acknowledge = page.getByRole("button", {
    name: "Acknowledge",
    exact: true,
  });
  if (await acknowledge.count()) await acknowledge.first().click();
  await page
    .getByRole("button", { name: "Sign current readiness report", exact: true })
    .click();
  await expect(
    page.getByText("Signed local readiness report saved.", { exact: true }),
  ).toBeVisible();
  await screenshot(page, "operations-readiness-light");
});

test("All expansion pages are accessible and fit desktop, tablet, mobile, and 200% zoom", async ({
  page,
}) => {
  test.setTimeout(240000);
  await signIn(page);
  const pages = [
    ["teacher", "Generate with provenance"],
    ["simulations", "From scene to sample"],
    ["compute", "Your compute, connected"],
    ["evaluations", "Evidence across versions"],
    ["settings/governance", "Decisions with a record"],
    ["operations", "Know what is proven"],
  ];
  for (const [route, title] of pages) {
    await page.goto("/" + route);
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    const scan = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(scan.violations, route).toEqual([]);
    await screenshot(page, route.replaceAll("/", "-") + "-desktop-light");
  }
  await page
    .getByRole("button", { name: "Toggle color theme", exact: true })
    .click();
  for (const [route, title] of pages) {
    await page.goto("/" + route);
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    const scan = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(scan.violations, route + " dark").toEqual([]);
    await screenshot(page, route.replaceAll("/", "-") + "-desktop-dark");
  }
  await page
    .getByRole("button", { name: "Toggle color theme", exact: true })
    .click();
  for (const width of [1024, 768, 390, 360]) {
    await page.setViewportSize({ width, height: 900 });
    for (const [route, title] of pages) {
      await page.goto("/" + route);
      await expect(
        page.getByRole("heading", { name: title, exact: true }),
      ).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
        `${route} at ${width}`,
      ).toBeTruthy();
    }
    await screenshot(page, `operations-${width}-light`);
  }
  await page.setViewportSize({ width: 390, height: 900 });
  await page
    .getByRole("button", { name: "Toggle color theme", exact: true })
    .click();
  await page.goto("/simulations");
  await screenshot(page, "simulations-390-dark");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/teacher");
  await page.evaluate(() => {
    document.documentElement.style.zoom = "2";
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  await screenshot(page, "teacher-200-percent-dark");
});
