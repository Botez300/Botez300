import { expect, test, type Page } from "playwright/test";

const shots = process.env.E2E_SCREENSHOTS;
const snap = async (page: Page, name: string) => { if (shots) await page.screenshot({ path: `${shots}/${name}.png` }); };

const email = `e2e-${Date.now()}@example.com`;
const password = "correct-horse-battery";

test.describe.configure({ mode: "serial" });

let page: Page;
const failures: string[] = [];

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
  page.on("pageerror", (e) => failures.push(`pageerror: ${e.message}`));
  page.on("response", (r) => { if (r.status() >= 500) failures.push(`${r.status()} ${r.url()}`); });
});

test.afterAll(async () => {
  expect(failures, "no uncaught page errors or 5xx responses during the run").toEqual([]);
  await page.close();
});

test("signed-out visitors are sent to the sign-in page", async () => {
  await page.goto("/charts?symbol=ALFA");
  await expect(page).toHaveURL(/\/login\?next=/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("registration opens the Command Center in clearly labelled demo mode", async () => {
  await page.goto("/register");
  await page.getByLabel("Name").fill("E2E Trader");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel(/Password/).fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Command Center" })).toBeVisible();
  await expect(page.getByTestId("demo-banner")).toContainText("synthetic");
  await expect(page.getByTestId("data-status").first()).toHaveText("SIMULATED");
  await expect(page.getByTestId("empty-watchlists")).toContainText("Start with a watchlist");
  // Scan pulse runs every template against the demo universe and shows real counts.
  const pulse = page.getByTestId("scan-pulse");
  await expect(pulse.getByText("Scanning…")).toHaveCount(0, { timeout: 30_000 });
  await expect(pulse.getByText("Scan failed")).toHaveCount(0);
  await expect(page.getByTestId("monitor").getByRole("link", { name: "SIMX" })).toBeVisible();
  await snap(page, "01-command-center");
});

test("symbol search opens a working chart with provenance and server-computed indicators", async () => {
  await page.keyboard.press("/");
  const search = page.getByRole("combobox", { name: "Symbol search" });
  await expect(search).toBeFocused();
  await search.fill("qub");
  await expect(page.getByRole("option").first()).toContainText("QBIT");
  await search.press("Enter");
  await expect(page).toHaveURL(/\/charts\?symbol=QBIT/);
  await expect(page.getByTestId("chart-symbol")).toHaveText("QBIT");
  await expect(page.getByTestId("chart-quote")).toContainText("Vol");
  const provenance = page.getByTestId("chart-provenance");
  await expect(provenance).toContainText("Provider demo");
  await expect(provenance).toContainText("SIMULATED");
  await expect(provenance.getByRole("link", { name: "Charts by Vela" })).toBeVisible();

  // The chart paints (a canvas with non-blank pixels) and the default indicators mount.
  const active = page.getByRole("list", { name: "Active indicators" });
  await expect(active.getByRole("listitem")).toHaveCount(2, { timeout: 30_000 });
  const canvas = page.getByTestId("chart-host").locator("canvas").first();
  await expect(canvas).toBeVisible();

  const computed = page.waitForResponse((r) => r.url().endsWith("/indicators/compute") && r.request().postDataJSON().indicator === "macd");
  await page.getByLabel("Add indicator").selectOption("macd");
  const body = await (await computed).json();
  expect(body.data_status).toBe("SIMULATED");
  expect(body.outputs.histogram.filter((v: number | null) => v !== null).length).toBeGreaterThan(1000);
  await expect(active.getByRole("listitem")).toHaveCount(3);

  await page.getByRole("button", { name: "Weekly" }).click();
  await expect(provenance).toContainText("→");
  await expect(page.getByRole("button", { name: "Weekly" })).toHaveAttribute("aria-pressed", "true");
  await page.waitForTimeout(1500);
  await snap(page, "02-chart");
  const box = (await page.getByTestId("chart-host").boundingBox())!;
  const png = await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } });
  expect(png.byteLength, "chart area is not a flat empty rectangle").toBeGreaterThan(20_000);

  await active.getByRole("button", { name: "Remove MACD" }).click();
  await expect(active.getByRole("listitem")).toHaveCount(2);
});

test("watchlists are created, edited and persist across reloads", async () => {
  await page.getByRole("link", { name: "Watchlists" }).click();
  await page.getByLabel("New watchlist name").fill("Leaders");
  await page.getByRole("button", { name: "Create" }).click();
  const list = page.getByTestId("watchlist").filter({ hasText: "Leaders" });
  for (const [query, symbol] of [["alf", "ALFA"], ["qbit", "QBIT"], ["petr", "PETR"]] as const) {
    const add = list.getByRole("combobox");
    await add.fill(query);
    await expect(page.getByRole("option").first()).toContainText(symbol);
    await add.press("Enter");
    await expect(list.getByRole("link", { name: symbol })).toBeVisible();
  }
  await list.getByRole("button", { name: "Remove PETR from Leaders" }).click();
  await expect(list.getByRole("link", { name: "PETR" })).toHaveCount(0);

  await page.reload();
  const reloaded = page.getByTestId("watchlist").filter({ hasText: "Leaders" });
  await expect(reloaded.getByRole("link")).toHaveText(["ALFA", "QBIT"]);
  await snap(page, "03-watchlists");

  await page.getByRole("link", { name: "Command Center" }).click();
  const monitor = page.getByTestId("monitor").filter({ hasText: "Watchlist · Leaders" });
  await expect(monitor.getByRole("row")).toHaveCount(3); // header + 2 symbols
  await expect(monitor.getByRole("link", { name: "ALFA" })).toBeVisible();
});

test("the scanner shows its conditions, returns real matches, exports and saves", async () => {
  await page.getByRole("link", { name: "Market Scanner" }).click();
  await page.getByRole("button", { name: /^Trend alignment/ }).click();
  const preview = page.getByTestId("conditions-preview");
  await expect(preview).toContainText("close 1D > sma(50) 1D");
  await expect(preview).toContainText("sma(50) 1D > sma(200) 1D");
  await expect(preview).toContainText("rsi(14) 1D > 50");
  await expect(page.getByTestId("rule")).toHaveCount(3);

  await page.getByRole("button", { name: "Run scan" }).click();
  const results = page.getByTestId("scan-results");
  await expect(page.getByTestId("scan-summary")).toHaveText(/^\d+ of 70 matched$/);
  const rows = results.locator("tbody tr");
  expect(await rows.count()).toBeGreaterThan(0);
  await expect(rows.first()).toContainText("SIMULATED");
  await snap(page, "04-scanner");

  // Every returned row really satisfies the rules: re-check the first one from the numbers on screen.
  const headers = await results.locator("thead th").allTextContents();
  const cells = await rows.first().locator("td").allTextContents();
  const value = (h: string) => Number(cells[headers.indexOf(h)]!.replace(/,/g, ""));
  expect(value("Close")).toBeGreaterThan(value("sma(50) 1D"));
  expect(value("sma(50) 1D")).toBeGreaterThan(value("sma(200) 1D"));
  expect(value("rsi(14) 1D")).toBeGreaterThan(50);

  const download = page.waitForEvent("download");
  await results.getByRole("button", { name: "CSV" }).click();
  expect((await download).suggestedFilename()).toBe("legion-scan.csv");

  // Edit a rule in the builder: an impossible threshold must produce an honest empty result.
  await page.getByLabel("Rule 3 right number").fill("100");
  await expect(preview).toContainText("rsi(14) 1D > 100");
  await page.getByRole("button", { name: "Run scan" }).click();
  await expect(page.getByTestId("scan-summary")).toHaveText("0 of 70 matched");
  await expect(results).toContainText("No symbols match");

  await page.getByLabel("Universe").selectOption({ label: "Leaders (2)" });
  await page.getByLabel("Rule 3 right number").fill("0");
  await page.getByRole("button", { name: "Remove rule 1" }).click();
  await page.getByRole("button", { name: "Remove rule 1" }).click();
  await page.getByRole("button", { name: "Run scan" }).click();
  await expect(page.getByTestId("scan-summary")).toHaveText("2 of 2 matched");
  await page.getByLabel("Saved scan name").fill("Leaders RSI");
  await page.getByRole("button", { name: "Save scan" }).click();
  await page.reload();
  const saved = page.getByRole("region", { name: "Saved scans" });
  await saved.getByRole("button", { name: "Leaders RSI", exact: true }).click();
  await expect(page.getByLabel("Universe")).toHaveValue(/^watchlist:/);
  await expect(page.getByTestId("conditions-preview")).toContainText("rsi(14) 1D > 0");
});

test("signing out ends the session", async () => {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto("/watchlists");
  await expect(page).toHaveURL(/\/login\?next=%2Fwatchlists/);
  // Wrong password is rejected with a clear message; the right one restores the saved workspace.
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("not-the-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Incorrect" })).toHaveText("Incorrect email or password");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/watchlists$/);
  await expect(page.getByTestId("watchlist")).toContainText("Leaders");
});
