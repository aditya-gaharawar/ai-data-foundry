import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const password = readFileSync(".env", "utf8")
  .split("\n")
  .find((line) => line.startsWith("DEV_PASSWORD="))!
  .slice("DEV_PASSWORD=".length);
const evidence = "verification/evidence/p06";
mkdirSync(`${evidence}/screenshots`, { recursive: true });

async function signIn(
  page: Page,
  email = "alex@foundry.local",
  secret = password,
) {
  await page.goto("/login");
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(secret);
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
      const auth = await (await fetch("/api/v1/auth/session")).json();
      const response = await fetch(`/api/v1${path}`, {
        method,
        headers: {
          "Content-Type": "application/json",
          "X-Organization-Id": auth.organizations[0].id,
          "X-CSRF-Token": auth.csrf_token,
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

async function fillCard(page: Page) {
  for (const [label, value] of [
    ["Purpose", "Browser proof of human-reviewed source data"],
    ["Intended training use", "Local synthetic acceptance tests"],
    [
      "Known limitations",
      "Small fixture; agreement is not ground-truth accuracy",
    ],
    ["Content risks", "Synthetic geometric shapes and test text"],
    ["Use restrictions", "Local fixture only"],
  ])
    await page.getByLabel(label, { exact: true }).fill(value);
  await page
    .getByRole("button", { name: "Save data card", exact: true })
    .click();
  await expect(
    page.getByText("Data card saved.", { exact: true }),
  ).toBeVisible();
}

async function keyboardTo(page: Page, locator: Locator) {
  await expect(locator).toBeVisible();
  for (let index = 0; index < 100; index++) {
    if (await locator.evaluate((element) => element === document.activeElement))
      return;
    await page.keyboard.press("Tab");
  }
  throw new Error("Review control was not keyboard reachable.");
}

test("image upload → box review → data card → durable publication → matching COCO and YOLO", async ({
  page,
}) => {
  test.slow();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await signIn(page);
  await page
    .getByRole("button", { name: "Create dataset", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  const datasetName = `Browser reviewed images ${Date.now()}`;
  await dialog.getByLabel("Dataset name", { exact: true }).fill(datasetName);
  await dialog.getByLabel("Modality", { exact: true }).selectOption("image");
  await dialog.getByRole("checkbox").check();
  await dialog
    .getByRole("button", { name: "Create dataset", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: datasetName, exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Upload image source", { exact: true })
    .setInputFiles("tests/fixtures/p06-shape.png");
  await expect(page.getByText("completed", { exact: true })).toBeVisible();
  await expect(
    page.getByAltText("Verified preview of p06-shape.png"),
  ).toBeVisible();
  const datasetPath = new URL(page.url()).pathname;
  await page
    .getByRole("link", { name: "Review & curate", exact: true })
    .click();
  await page
    .getByLabel("Session name", { exact: true })
    .fill("Browser image review");
  await page
    .getByRole("button", { name: "Create quality profile", exact: true })
    .click();
  const profileName = `Browser image profile ${Date.now()}`;
  await dialog.getByLabel("Profile name", { exact: true }).fill(profileName);
  await expect(
    dialog.getByRole("combobox", { name: "Profile modality", exact: true }),
  ).toHaveValue("image");
  await dialog
    .getByRole("button", { name: "Save quality profile", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page
      .getByRole("combobox", { name: "Quality profile", exact: true })
      .locator("option:checked"),
  ).toHaveText(profileName);
  await page
    .getByRole("combobox", { name: "Review policy", exact: true })
    .selectOption("1");
  await page.getByRole("checkbox", { name: /p06-shape.png/ }).check();
  await page
    .getByRole("button", { name: "Create review session", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Browser image review", exact: true }),
  ).toBeVisible();
  const curationPath = new URL(page.url()).pathname;
  await expect(
    page.getByText("Publication is blocked", { exact: true }),
  ).toBeVisible();
  await fillCard(page);
  await page.getByRole("link", { name: /^Sample 1/ }).click();
  await page.getByRole("button", { name: "Add box", exact: true }).click();
  await page.getByLabel("Box 1 x", { exact: true }).fill("8");
  await page.getByLabel("Box 1 y", { exact: true }).fill("6");
  await page.getByLabel("Box 1 width", { exact: true }).fill("32");
  await page.getByLabel("Box 1 height", { exact: true }).fill("24");
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Corrected the box to the actual blue rectangle.");
  await page
    .getByRole("button", { name: "Submit review", exact: true })
    .click();
  await expect(page.getByText("accepted", { exact: true })).toBeVisible();
  const taskPath = new URL(page.url()).pathname;
  await page.reload();
  await expect(page.getByLabel("Box 1 x", { exact: true })).toHaveValue("8");
  await expect(page.getByLabel("Box 1 width", { exact: true })).toHaveValue(
    "32",
  );
  for (const theme of ["light", "dark"]) {
    await page.evaluate((value) => localStorage.setItem("theme", value), theme);
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.goto(taskPath);
      await expect(
        page.getByRole("img", { name: /Image annotation preview/ }),
      ).toBeVisible();
      await expect(page.locator("svg image")).toHaveAttribute("href", /^blob:/);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: `${evidence}/screenshots/annotation-${theme}-${width}.png`,
        fullPage: true,
      });
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    for (const path of [
      taskPath,
      curationPath,
      "/curation/profiles",
      "/curation",
    ]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const results = await new AxeBuilder({ page }).analyze();
      expect(results.violations, JSON.stringify(results.violations)).toEqual(
        [],
      );
    }
  }
  await page.goto(curationPath);
  await expect(
    page.getByRole("button", { name: "Approve review snapshot", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Approve review snapshot", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Publish reviewed version", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: `${evidence}/screenshots/curation-approved-desktop.png`,
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Publish reviewed version", exact: true })
    .click();
  await expect(dialog).toBeVisible();
  await dialog
    .getByRole("button", { name: "Confirm publication", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Export JSONL", exact: true }),
  ).toBeVisible({ timeout: 60000 });
  await page.getByRole("link", { name: "View dataset", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`${datasetPath}$`));
  await page.getByRole("tab", { name: "Versions", exact: true }).click();
  const exports: Record<string, unknown> = {};
  for (const format of ["COCO", "YOLO"]) {
    const event = page.waitForEvent("download");
    await page
      .getByRole("button", { name: `Export ${format}`, exact: true })
      .click();
    const downloaded = await event;
    expect(downloaded.suggestedFilename()).toMatch(
      new RegExp(`\\.${format.toLowerCase()}\\.zip$`),
    );
    const path = (await downloaded.path())!;
    const metadata = JSON.parse(
      execFileSync(
        "python",
        [
          "-c",
          "import json,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); print(json.dumps({'names':z.namelist(),'annotations':json.loads(z.read('annotations.json')) if 'annotations.json' in z.namelist() else [z.read(n).decode() for n in z.namelist() if n.startswith('labels/')]}))",
          path,
        ],
        { encoding: "utf8" },
      ),
    );
    if (format === "COCO")
      expect(metadata.annotations.annotations[0].bbox).toEqual([8, 6, 32, 24]);
    else expect(metadata.annotations[0].trim()).toBe("0 0.375 0.375 0.5 0.5");
    exports[format.toLowerCase()] = {
      sha256: createHash("sha256").update(readFileSync(path)).digest("hex"),
      files: metadata.names,
      annotations: metadata.annotations,
    };
  }
  await page.getByRole("tab", { name: "Data card", exact: true }).click();
  await expect(
    page.getByText(/Browser proof of human-reviewed source data/),
  ).toBeVisible();
  writeFileSync(
    `${evidence}/browser-image-proof.json`,
    JSON.stringify(
      {
        dataset_path: datasetPath,
        curation_path: curationPath,
        task_path: taskPath,
        reviewed_box: [8, 6, 32, 24],
        exports,
      },
      null,
      2,
    ) + "\n",
  );
  expect(errors).toEqual([]);
});

test("two independent labelers correct, disagree, and receive independent adjudication", async ({
  page,
  browser,
}) => {
  test.slow();
  await signIn(page);
  const suffix = Date.now();
  const members = [];
  for (let index = 0; index < 2; index++) {
    const email = `browser-labeler-${suffix}-${index}@foundry.local`;
    const secret = randomBytes(18).toString("base64url");
    const member = await api<{ id: string }>(page, "/members", "POST", {
      email,
      password: secret,
      name: `Browser Labeler ${index + 1}`,
      role: "Labeler",
    });
    members.push({ ...member, email, secret });
  }
  const project = (await api<{ items: { id: string }[] }>(page, "/projects"))
    .items[0].id;
  const dataset = await api<{ id: string }>(page, "/datasets", "POST", {
    name: `Browser consensus ${suffix}`,
    project_id: project,
    policy: { allowed_training_use: true, origin: "synthetic-test" },
  });
  const raw =
    JSON.stringify({
      prompt: '<img src=x onerror="window.annotationExecuted=true">',
      response: "Escaped test source",
    }) + "\n";
  const upload = await api<{ id: string; upload_urls: string[] }>(
    page,
    "/uploads",
    "POST",
    {
      dataset_id: dataset.id,
      filename: "review.jsonl",
      content_type: "application/x-ndjson",
      bytes: Buffer.byteLength(raw),
      sha256: createHash("sha256").update(raw).digest("hex"),
    },
  );
  const etag = await page.evaluate(
    async ({ url, raw }) => {
      const response = await fetch(url, {
        method: "PUT",
        credentials: "omit",
        body: raw,
      });
      if (!response.ok) throw new Error("Source upload failed");
      return response.headers.get("etag");
    },
    { url: upload.upload_urls[0], raw },
  );
  await api(page, `/uploads/${upload.id}/complete`, "POST", {
    parts: [{ part_number: 1, etag }],
  });
  const profile = await api<{ id: string }>(page, "/quality-profiles", "POST", {
    name: "Consensus browser profile",
    modality: "text",
  });
  const curation = await api<{ id: string }>(page, "/curations", "POST", {
    name: "Browser independent consensus",
    dataset_id: dataset.id,
    profile_id: profile.id,
    categories: ["object", "other"],
    upload_ids: [upload.id],
  });
  const task = (
    await api<{ items: { id: string }[] }>(
      page,
      `/annotation-tasks?curation_id=${curation.id}`,
    )
  ).items[0];
  const taskPath = `/curation/tasks/${task.id}`;
  await page.goto(taskPath);
  await page
    .getByRole("combobox", { name: "Assigned reviewer", exact: true })
    .selectOption(members[0].id);
  await page
    .getByRole("button", { name: "Save assignment", exact: true })
    .click();
  await expect(
    page.getByText("Assignment saved.", { exact: true }),
  ).toBeVisible();
  const contexts = await Promise.all([
    browser.newContext(),
    browser.newContext(),
  ]);
  try {
    const first = await contexts[0].newPage();
    const second = await contexts[1].newPage();
    await signIn(first, members[0].email, members[0].secret);
    await signIn(second, members[1].email, members[1].secret);
    await expect(
      first.getByRole("button", { name: "Create dataset", exact: true }),
    ).toHaveCount(0);
    await first.goto(taskPath);
    await second.goto(taskPath);
    await expect(
      second.getByRole("button", { name: "Submit review", exact: true }),
    ).toHaveCount(0);
    await keyboardTo(
      first,
      first.getByRole("combobox", { name: "Sample category", exact: true }),
    );
    await first.keyboard.press("End");
    await keyboardTo(first, first.getByLabel("Review note", { exact: true }));
    await first.keyboard.type("Initial category chosen with the keyboard.");
    await keyboardTo(
      first,
      first.getByRole("button", { name: "Submit review", exact: true }),
    );
    await first.keyboard.press("Enter");
    await expect(
      first.getByText("needs review", { exact: true }),
    ).toBeVisible();
    await first
      .getByRole("combobox", { name: "Sample category", exact: true })
      .selectOption("object");
    await first
      .getByLabel("Review note", { exact: true })
      .fill("Corrected my original category after inspecting the source.");
    await first
      .getByRole("button", { name: "Submit review", exact: true })
      .click();
    await expect(
      first.getByText(
        "Corrected my original category after inspecting the source.",
        { exact: true },
      ),
    ).toBeVisible();
    await first.reload();
    await expect(
      first.getByRole("combobox", { name: "Sample category", exact: true }),
    ).toHaveValue("object");
    expect(
      await first.evaluate(
        () =>
          (window as unknown as { annotationExecuted?: boolean })
            .annotationExecuted,
      ),
    ).toBeUndefined();
    await second.reload();
    await second
      .getByRole("combobox", { name: "Sample category", exact: true })
      .selectOption("other");
    await second
      .getByLabel("Review note", { exact: true })
      .fill("Independent reviewer disagrees with this category.");
    await second
      .getByRole("button", { name: "Submit review", exact: true })
      .click();
    await expect(
      second.getByText("needs adjudication", { exact: true }),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Adjudication", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("combobox", { name: "Sample category", exact: true })
      .selectOption("object");
    await page
      .getByLabel("Review note", { exact: true })
      .fill(
        "Independent administrator adjudicates the source category as object.",
      );
    await page
      .getByRole("button", { name: "Accept adjudication", exact: true })
      .click();
    await expect(page.getByText("adjudicated", { exact: true })).toBeVisible();
    await page.screenshot({
      path: `${evidence}/screenshots/adjudicated-text-desktop.png`,
      fullPage: true,
    });
    await page
      .getByRole("link", { name: "Back to review queue", exact: true })
      .click();
    await fillCard(page);
    await expect(
      page.getByRole("button", {
        name: "Approve review snapshot",
        exact: true,
      }),
    ).toBeEnabled();
    await page
      .getByRole("button", { name: "Approve review snapshot", exact: true })
      .click();
    await expect(
      page.getByRole("button", {
        name: "Publish reviewed version",
        exact: true,
      }),
    ).toBeVisible();
    const persisted = await api<{ reviews: unknown[]; annotation: unknown }>(
      page,
      `/annotation-tasks/${task.id}`,
    );
    expect(persisted.reviews).toHaveLength(4);
    expect(persisted.annotation).toEqual({ kind: "category", label: "object" });
    writeFileSync(
      `${evidence}/browser-consensus-proof.json`,
      JSON.stringify(
        {
          curation_id: curation.id,
          task_id: task.id,
          reviewer_count: 2,
          recorded_decisions: persisted.reviews.length,
          annotation: persisted.annotation,
          state: "FROZEN",
          keyboard_review: true,
          uploaded_html_inert: true,
        },
        null,
        2,
      ) + "\n",
    );
  } finally {
    await Promise.all(contexts.map((context) => context.close()));
    for (const member of members)
      await api(page, `/members/${member.id}`, "DELETE");
  }
});
