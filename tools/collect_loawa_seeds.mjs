import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import readline from "node:readline/promises";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");

function parseArgs(argv) {
  const args = {
    config: path.join(ROOT, "config", "loawa_seed_queries.example.json"),
    source: null,
    maxPages: 20,
    maxPagesExplicit: false,
    visible: true,
    interactive: true,
    pagePauseMs: 1500,
    scrollPauseMs: 1200,
    scrollRounds: 30,
    stableRounds: 3,
    scrollMode: "end",
    dataDir: process.env.DATA_DIR ? path.resolve(process.env.DATA_DIR) : path.join(ROOT, "data"),
    chromePath: null,
    userDataDir: path.join(ROOT, ".tmp", "loawa-chrome-profile"),
    rawOnly: false,
    help: false,
    manualPagination: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    const next = argv[i + 1];

    if (key === "--config" && next) {
      args.config = path.resolve(next);
      i += 1;
    } else if (key === "--source" && next) {
      args.source = next;
      i += 1;
    } else if (key === "--max-pages" && next) {
      args.maxPages = Math.max(1, Number(next) || args.maxPages);
      args.maxPagesExplicit = true;
      i += 1;
    } else if (key === "--chrome-path" && next) {
      args.chromePath = path.resolve(next);
      i += 1;
    } else if (key === "--data-dir" && next) {
      args.dataDir = path.resolve(next);
      i += 1;
    } else if (key === "--user-data-dir" && next) {
      args.userDataDir = path.resolve(next);
      i += 1;
    } else if (key === "--page-pause-ms" && next) {
      args.pagePauseMs = Math.max(0, Number(next) || args.pagePauseMs);
      i += 1;
    } else if (key === "--scroll-pause-ms" && next) {
      args.scrollPauseMs = Math.max(0, Number(next) || args.scrollPauseMs);
      i += 1;
    } else if (key === "--scroll-rounds" && next) {
      args.scrollRounds = Math.max(1, Number(next) || args.scrollRounds);
      i += 1;
    } else if (key === "--stable-rounds" && next) {
      args.stableRounds = Math.max(1, Number(next) || args.stableRounds);
      i += 1;
    } else if (key === "--scroll-mode" && next) {
      args.scrollMode = ["end", "pagedown"].includes(String(next).toLowerCase())
        ? String(next).toLowerCase()
        : args.scrollMode;
      i += 1;
    } else if (key === "--headless") {
      args.visible = false;
      args.interactive = false;
    } else if (key === "--non-interactive") {
      args.interactive = false;
    } else if (key === "--raw-only") {
      args.rawOnly = true;
    } else if (key === "--manual-pagination") {
      args.manualPagination = true;
    } else if (key === "--help" || key === "-h") {
      args.help = true;
    }
  }

  return args;
}

function printHelp() {
  console.log(`LOA browser seed collector

Usage:
  node collect_loawa_seeds.mjs [options]

Options:
  --config <path>           Query config JSON path
  --source <sourceType>     One source only, e.g. kloa_combat_power
  --max-pages <n>           Max page/batch count in this run
  --chrome-path <path>      Explicit Chrome/Edge executable path
  --data-dir <path>         Output data root. Default: DATA_DIR or ./data
  --user-data-dir <path>    Persistent browser profile directory
  --page-pause-ms <n>       Delay between page operations
  --scroll-pause-ms <n>     Delay between scroll steps
  --scroll-rounds <n>       Max scroll rounds per source page
  --stable-rounds <n>       Stop after N rounds with no new names
  --scroll-mode <mode>      Scroll trigger: end or pagedown. Default: end
  --headless                Run headless and disable interactive pause
  --non-interactive         Skip Enter prompt after page opens
  --manual-pagination       Ask for manual next-page navigation between pages
  --raw-only                Save raw HTML only, skip seed index updates
  --help, -h                Show this help
`);
}

function nowParts() {
  const now = new Date();
  const iso = now.toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
  return {
    stamp: iso,
    date: now.toISOString().slice(0, 10),
    hour: now.toISOString().slice(11, 13),
  };
}

async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, { recursive: true });
}

async function readJson(filePath) {
  return JSON.parse(await fs.readFile(filePath, "utf-8"));
}

function sha1(value) {
  return crypto.createHash("sha1").update(value).digest("hex");
}

async function pathExists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function detectChromeExecutable(explicitPath) {
  const candidates = [
    explicitPath,
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (await pathExists(candidate)) return candidate;
  }

  return null;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function defaultStartUrl(source) {
  if (source.path?.startsWith("http")) return source.path;
  if (source.baseUrl && source.path) return `${source.baseUrl}${source.path}`;
  return `https://loawa.com${source.path || ""}`;
}

function buildTargets(config, args) {
  const sources = Array.isArray(config.sources) ? config.sources : [];
  const filtered = args.source
    ? sources.filter((source) => source.sourceType === args.source)
    : sources.filter(
        (source) =>
          source.enabled !== false &&
          (source.path || (Array.isArray(source.startUrls) && source.startUrls.length > 0))
      );

  return filtered.map((source) => {
    const configuredMaxPages = Number(source.maxPagesPerRun || source.filters?.pagesPerQuery || 0) || null;
    const effectiveMaxPages = args.maxPagesExplicit
      ? args.maxPages
      : (configuredMaxPages || args.maxPages);

    return {
    sourceType: source.sourceType,
    startUrl: Array.isArray(source.startUrls) && source.startUrls.length
      ? source.startUrls[0]
      : defaultStartUrl(source),
    actionMode: source.actionMode || "scroll",
    maxPages: effectiveMaxPages,
    nextPageSelectors: source.nextPageSelectors || [
      "a[rel='next']",
      "button[rel='next']",
      "a:has-text('다음')",
      "button:has-text('다음')",
      "a:has-text('Next')",
      "button:has-text('Next')",
    ],
    loadMoreSelectors: source.loadMoreSelectors || [
      "button:has-text('더 보기')",
      "text=더 보기",
    ],
    nameSelectors: source.nameSelectors || [],
    representativeOnly: source.filters?.representativeOnly || [],
    };
  });
}

async function launchBrowser(args) {
  let playwright;
  try {
    playwright = await import("playwright-core");
  } catch {
    throw new Error("playwright-core is not installed. Run `npm.cmd install` in D:\\LOA-HSI\\tools first.");
  }

  const executablePath = await detectChromeExecutable(args.chromePath);
  if (!executablePath) {
    throw new Error("Could not find Chrome or Edge executable. Pass --chrome-path explicitly.");
  }

  await ensureDir(args.userDataDir);

  const context = await playwright.chromium.launchPersistentContext(args.userDataDir, {
    executablePath,
    headless: !args.visible,
    viewport: { width: 1600, height: 1200 },
    ignoreDefaultArgs: ["--enable-automation"],
    args: [
      "--disable-blink-features=AutomationControlled",
      "--disable-dev-shm-usage",
      "--no-first-run",
      "--no-default-browser-check",
    ],
  });

  await context.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => undefined });
  });

  const page = context.pages()[0] || await context.newPage();
  return { context, page, executablePath };
}

async function waitForUserReady(page, target) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log("");
  console.log(`[LOAWA] Opened ${target.startUrl}`);
  console.log("[LOAWA] If login/Cloudflare appears, solve it in the browser.");
  console.log("[LOAWA] Adjust page filters manually if needed, then press Enter here.");
  await rl.question("Press Enter when the list page is ready: ");
  rl.close();

  const title = await page.title().catch(() => "");
  console.log(`[LOAWA] Current page title: ${title}`);
}

async function getPageSignature(page) {
  return page.evaluate(() => {
    const anchors = Array.from(document.querySelectorAll("a[href]"))
      .slice(0, 30)
      .map((node) => `${node.getAttribute("href") || ""}|${(node.textContent || "").trim().replace(/\s+/g, "")}`);

    return JSON.stringify({
      url: window.location.href,
      title: document.title,
      anchors,
      bodyPrefix: (document.body?.innerText || "").replace(/\s+/g, " ").slice(0, 400),
    });
  }).catch(() => "");
}

async function promptManualNextPage(page, pageIndex) {
  const beforeSignature = await getPageSignature(page);
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log("");
  console.log(`[LOAWA] Automatic next-page detection stopped after page ${pageIndex}.`);
  console.log("[LOAWA] Move to the next page manually in the browser, then press Enter.");
  console.log("[LOAWA] Type `stop` and press Enter to finish this source.");
  const answer = (await rl.question("Next page ready? ")).trim().toLowerCase();
  rl.close();

  if (answer === "stop" || answer === "q" || answer === "quit") {
    return false;
  }

  await sleep(800);
  const afterSignature = await getPageSignature(page);
  if (afterSignature === beforeSignature) {
    console.log("[LOAWA] Visible page signature did not change. Saving again would likely create duplicates.");
    console.log("[LOAWA] Navigate first, then press Enter. Finishing this source.");
    return false;
  }

  return true;
}

async function saveRawPage(rawRoot, target, pageIndex, page) {
  const parts = nowParts();
  const dir = path.join(rawRoot, "loawa", target.sourceType, `date=${parts.date}`, `hour=${parts.hour}`);
  await ensureDir(dir);

  const url = page.url();
  const html = await page.content();
  const snapshot = {
    collectedAt: new Date().toISOString(),
    sourceType: target.sourceType,
    pageIndex,
    url,
    title: await page.title().catch(() => ""),
    htmlPath: null,
  };

  const key = `${parts.stamp}_${target.sourceType}_page-${String(pageIndex).padStart(4, "0")}_${sha1(url).slice(0, 10)}`;
  const htmlPath = path.join(dir, `${key}.html`);
  const jsonPath = path.join(dir, `${key}.json`);
  await fs.writeFile(htmlPath, html, "utf-8");
  snapshot.htmlPath = htmlPath;
  await fs.writeFile(jsonPath, JSON.stringify(snapshot, null, 2), "utf-8");
  return { htmlPath, jsonPath, snapshot };
}

async function extractNameCandidates(page, target, pageIndex) {
  return page.evaluate(({ sourceType, selectors, pageIndex }) => {
    const blocked = new Set([
      "랭킹",
      "거래소",
      "계산기",
      "멀티서치",
      "게시판",
      "더보기",
      "더 보기",
      "다음",
      "이전",
      "검색",
      "로그인",
      "회원가입",
      "상세",
      "전체",
      "서버",
      "역할",
      "클래스",
      "순위",
      "캐릭터명",
      "아이템레벨",
      "아이템 레벨",
      "전투력",
      "장비",
      "깨달음",
      "중앙값",
      "페이지",
      "공유",
      "TOP",
      "Top",
    ]);

    function visible(el) {
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    }

    function nameLike(text) {
      if (!text) return false;
      const compact = text.replace(/\s+/g, "");
      if (compact.length < 2 || compact.length > 16) return false;
      if (blocked.has(compact)) return false;
      if (/^\d+$/.test(compact)) return false;
      if (!/^[0-9A-Za-z가-힣]+$/.test(compact)) return false;
      return true;
    }

    function scoreNode(anchor) {
      let score = 0;
      const href = anchor.href || "";
      if (anchor.closest("tr, tbody, table, li, ul, ol")) score += 2;
      if (href && href !== window.location.href) score += 1;
      if (/character|characters|profile|search|rank|combatpower|combat-power/i.test(href)) score += 3;
      if (visible(anchor)) score += 1;
      return score;
    }

    const nodes = selectors.length
      ? selectors.flatMap((selector) => Array.from(document.querySelectorAll(selector)))
      : Array.from(document.querySelectorAll("a[href]"));

    const seen = new Map();
    for (const node of nodes) {
      const text = (node.textContent || "").trim().replace(/\s+/g, "");
      if (!nameLike(text)) continue;

      const score = scoreNode(node);
      if (score < 2) continue;

      const href = node.href || "";
      const rowText = (
        node.closest("tr, li, .card, .list, .row, [role='row']")?.textContent || ""
      ).trim().replace(/\s+/g, " ").slice(0, 250);

      const key = `${text}@@${href}`;
      const prev = seen.get(key);
      const row = {
        sourceType,
        pageIndex,
        characterName: text,
        href,
        score,
        rowText,
      };

      if (!prev || prev.score < score) {
        seen.set(key, row);
      }
    }

    const items = Array.from(seen.values()).sort(
      (a, b) => b.score - a.score || a.characterName.localeCompare(b.characterName)
    );

    return {
      title: document.title,
      url: window.location.href,
      count: items.length,
      names: items,
    };
  }, { sourceType: target.sourceType, selectors: target.nameSelectors, pageIndex });
}

function mergeExtractedRows(existingMap, extracted) {
  let added = 0;

  for (const item of extracted.names) {
    const key = `${item.characterName}@@${item.href || ""}`;
    const prev = existingMap.get(key);
    if (!prev) {
      existingMap.set(key, item);
      added += 1;
      continue;
    }
    if ((item.score || 0) > (prev.score || 0)) {
      existingMap.set(key, item);
    }
  }

  return added;
}

async function getScrollState(page) {
  return page.evaluate(() => {
    const root = document.scrollingElement || document.documentElement || document.body;
    return {
      top: root.scrollTop,
      height: root.scrollHeight,
    };
  });
}

async function triggerScroll(page, mode) {
  const before = await getScrollState(page).catch(() => ({ top: 0, height: 0 }));
  await page.locator("body").click({ force: true, position: { x: 40, y: 40 } }).catch(() => null);

  if (mode === "pagedown") {
    await page.keyboard.press("PageDown").catch(() => null);
  } else {
    await page.keyboard.press("End").catch(() => null);
  }

  return before;
}

async function collectByScrolling(page, target, pageIndex, args) {
  const merged = new Map();
  let stable = 0;

  for (let round = 1; round <= args.scrollRounds; round += 1) {
    const extracted = await extractNameCandidates(page, target, pageIndex);
    const added = mergeExtractedRows(merged, extracted);
    console.log(`[LOAWA] ${target.sourceType} page ${pageIndex} scroll ${round}: +${added}, total ${merged.size}`);

    if (added === 0) {
      stable += 1;
    } else {
      stable = 0;
    }

    if (stable >= args.stableRounds) {
      return {
        title: extracted.title,
        url: extracted.url,
        count: merged.size,
        names: Array.from(merged.values()).sort(
          (a, b) => b.score - a.score || a.characterName.localeCompare(b.characterName)
        ),
        scrollRoundsUsed: round,
        stableRoundsReached: stable,
      };
    }

    const before = await triggerScroll(page, args.scrollMode);
    await sleep(args.scrollPauseMs);
    const after = await getScrollState(page).catch(() => ({ top: 0, height: 0 }));

    if (after.top === before.top && after.height === before.height && stable >= 1) {
      return {
        title: extracted.title,
        url: extracted.url,
        count: merged.size,
        names: Array.from(merged.values()).sort(
          (a, b) => b.score - a.score || a.characterName.localeCompare(b.characterName)
        ),
        scrollRoundsUsed: round,
        stableRoundsReached: stable,
      };
    }
  }

  const extracted = await extractNameCandidates(page, target, pageIndex);
  mergeExtractedRows(merged, extracted);
  return {
    title: extracted.title,
    url: extracted.url,
    count: merged.size,
    names: Array.from(merged.values()).sort(
      (a, b) => b.score - a.score || a.characterName.localeCompare(b.characterName)
    ),
    scrollRoundsUsed: args.scrollRounds,
    stableRoundsReached: stable,
  };
}

async function tryNextPage(page, selectors, currentUrl) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    const count = await locator.count().catch(() => 0);
    if (!count) continue;

    const visible = await locator.isVisible().catch(() => false);
    if (!visible) continue;

    await Promise.all([
      page.waitForLoadState("domcontentloaded").catch(() => null),
      locator.click({ timeout: 5000 }).catch(() => null),
    ]);
    await sleep(1200);

    if (page.url() !== currentUrl) return true;
  }

  const advanced = await page.evaluate(() => {
    const labels = ["다음", "Next", ">"];
    const nodes = Array.from(document.querySelectorAll("a[href], button"));
    const hit = nodes.find((node) => labels.includes((node.textContent || "").trim()));
    if (!hit) return null;
    if (hit.tagName === "A") return { type: "goto", href: hit.href || null };
    return null;
  }).catch(() => null);

  if (advanced?.type === "goto" && advanced.href && advanced.href !== currentUrl) {
    await page.goto(advanced.href, { waitUntil: "domcontentloaded" });
    await sleep(1200);
    return true;
  }

  return false;
}

async function clickLoadMore(page, selectors) {
  for (const selector of selectors) {
    try {
      const locator = page.locator(selector).first();
      const count = await locator.count().catch(() => 0);
      if (!count) continue;

      const visible = await locator.isVisible().catch(() => false);
      if (!visible) continue;

      await locator.scrollIntoViewIfNeeded().catch(() => null);
      await locator.click({ timeout: 5000 }).catch(() => null);
      return true;
    } catch {
      // continue
    }
  }

  const advanced = await page.evaluate(() => {
    const nodes = Array.from(document.querySelectorAll("button, a, div"));
    const hit = nodes.find((node) => ((node.textContent || "").trim() === "더 보기"));
    if (!hit) return false;
    hit.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    return true;
  }).catch(() => false);

  return Boolean(advanced);
}

async function appendNdjson(filePath, rows) {
  if (!rows.length) return;
  const payload = rows.map((row) => JSON.stringify(row)).join("\n") + "\n";
  await fs.appendFile(filePath, payload, "utf-8");
}

async function mergeCanonical(filePath, rows) {
  const map = new Map();

  try {
    const raw = await fs.readFile(filePath, "utf-8");
    for (const line of raw.split(/\r?\n/)) {
      if (!line.trim()) continue;
      const row = JSON.parse(line);
      map.set(`${row.characterName}@@${row.serverName || ""}`, row);
    }
  } catch {
    // first run
  }

  for (const row of rows) {
    const key = `${row.characterName}@@${row.serverName || ""}`;
    const existing = map.get(key);

    if (!existing) {
      map.set(key, {
        characterName: row.characterName,
        serverName: row.serverName || null,
        firstSeenAt: row.collectedAt,
        lastSeenAt: row.collectedAt,
        seenCount: 1,
        seenSources: [row.sourceType],
        hrefs: row.href ? [row.href] : [],
      });
      continue;
    }

    existing.lastSeenAt = row.collectedAt;
    existing.seenCount += 1;
    if (!existing.seenSources.includes(row.sourceType)) existing.seenSources.push(row.sourceType);
    if (row.href && !existing.hrefs.includes(row.href)) existing.hrefs.push(row.href);
  }

  const out = Array.from(map.values())
    .sort((a, b) => a.characterName.localeCompare(b.characterName))
    .map((row) => JSON.stringify(row))
    .join("\n") + "\n";
  await fs.writeFile(filePath, out, "utf-8");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return;
  }

  const config = await readJson(args.config);
  const targets = buildTargets(config, args);
  if (!targets.length) {
    throw new Error("No enabled seed targets found in config.");
  }

  const rawRoot = path.join(args.dataDir, "raw");
  const processedRoot = path.join(args.dataDir, "processed", "loawa");
  await ensureDir(rawRoot);
  await ensureDir(processedRoot);

  const { context, page, executablePath } = await launchBrowser(args);
  console.log(`[LOAWA] Using browser: ${executablePath}`);

  const batchRows = [];

  try {
    for (const target of targets) {
      console.log(`[LOAWA] Target: ${target.sourceType} -> ${target.startUrl}`);
      await page.goto(target.startUrl, { waitUntil: "domcontentloaded" });
      await sleep(args.pagePauseMs);

      if (args.interactive) {
        await waitForUserReady(page, target);
      }

      const targetSeen = new Set();
      const maxIterations = target.maxPages;

      for (let pageIndex = 1; pageIndex <= maxIterations; pageIndex += 1) {
        const currentUrl = page.url();
        const extracted = target.actionMode === "load_more"
          ? await extractNameCandidates(page, target, pageIndex)
          : await collectByScrolling(page, target, pageIndex, args);
        const raw = await saveRawPage(rawRoot, target, pageIndex, page);

        if (target.actionMode === "load_more") {
          console.log(`[LOAWA] ${target.sourceType} batch ${pageIndex}: ${extracted.count} cumulative candidates`);
        } else {
          console.log(
            `[LOAWA] ${target.sourceType} page ${pageIndex}: ${extracted.count} candidates after ${extracted.scrollRoundsUsed} scrolls`
          );
        }

        const rows = extracted.names
          .filter((item) => {
            const key = `${item.characterName}@@${item.href || ""}`;
            if (target.actionMode !== "load_more") return true;
            if (targetSeen.has(key)) return false;
            targetSeen.add(key);
            return true;
          })
          .map((item) => ({
            collectedAt: new Date().toISOString(),
            sourceType: target.sourceType,
            pageIndex,
            pageUrl: extracted.url,
            pageTitle: extracted.title,
            characterName: item.characterName,
            serverName: null,
            className: null,
            href: item.href || null,
            score: item.score,
            rowText: item.rowText,
            rawHtmlPath: raw.htmlPath,
            rawMetaPath: raw.jsonPath,
          }));

        if (target.actionMode === "load_more") {
          console.log(`[LOAWA] ${target.sourceType} batch ${pageIndex}: +${rows.length} new seeds`);
        }

        batchRows.push(...rows);
        if (!args.rawOnly) {
          await appendNdjson(path.join(processedRoot, "loawa_seed_index.ndjson"), rows);
        }

        if (target.actionMode === "load_more") {
          const loaded = await clickLoadMore(page, target.loadMoreSelectors);
          if (!loaded) {
            console.log(`[LOAWA] No load-more action found after batch ${pageIndex}.`);
            break;
          }
          await sleep(args.pagePauseMs);
          continue;
        }

        const moved = args.manualPagination
          ? false
          : await tryNextPage(page, target.nextPageSelectors, currentUrl);
        if (!moved && args.interactive) {
          const manualMoved = await promptManualNextPage(page, pageIndex);
          if (manualMoved) {
            await sleep(args.pagePauseMs);
            continue;
          }
        }
        if (!moved) {
          console.log(`[LOAWA] No next-page action found after page ${pageIndex}.`);
          break;
        }
        await sleep(args.pagePauseMs);
      }
    }
  } finally {
    await context.close().catch(() => null);
  }

  const uniqueRows = [];
  const seen = new Set();
  for (const row of batchRows) {
    const key = `${row.characterName}@@${row.href || ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    uniqueRows.push(row);
  }

  if (!args.rawOnly) {
    await mergeCanonical(path.join(processedRoot, "loawa_seed_canonical.ndjson"), uniqueRows);
  }

  const summary = {
    collectedAt: new Date().toISOString(),
    totalRows: batchRows.length,
    uniqueRows: uniqueRows.length,
    outputDir: processedRoot,
    rawRoot,
  };
  await fs.writeFile(
    path.join(processedRoot, "last_batch_summary.json"),
    JSON.stringify(summary, null, 2),
    "utf-8"
  );

  console.log("[LOAWA] Done.");
  console.log(JSON.stringify(summary, null, 2));
}

main().catch((error) => {
  console.error("[LOAWA] Collector failed.");
  console.error(error?.stack || String(error));
  process.exitCode = 1;
});
