import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");

function parseArgs(argv) {
  const args = {
    dataDir: process.env.DATA_DIR ? path.resolve(process.env.DATA_DIR) : path.join(ROOT, "data"),
    input: null,
    outputDir: null,
    limit: 100,
    sleepMs: 800,
    force: false,
    useCache: true,
    statuses: ["discovered", "queued_for_api", "api_failed_retryable"],
    help: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    const next = argv[i + 1];
    if (key === "--data-dir" && next) {
      args.dataDir = path.resolve(next);
      i += 1;
    } else if (key === "--input" && next) {
      args.input = path.resolve(next);
      i += 1;
    } else if (key === "--output-dir" && next) {
      args.outputDir = path.resolve(next);
      i += 1;
    } else if (key === "--limit" && next) {
      args.limit = Math.max(1, Number(next) || args.limit);
      i += 1;
    } else if (key === "--sleep-ms" && next) {
      args.sleepMs = Math.max(0, Number(next) || args.sleepMs);
      i += 1;
    } else if (key === "--status" && next) {
      args.statuses = next.split(",").map((value) => value.trim()).filter(Boolean);
      i += 1;
    } else if (key === "--force") {
      args.force = true;
    } else if (key === "--no-cache") {
      args.useCache = false;
    } else if (key === "--help" || key === "-h") {
      args.help = true;
    }
  }

  return args;
}

function printHelp() {
  console.log(`LOAWA seed -> Lost Ark API verifier

Usage:
  node verify_loawa_seeds_api.mjs [options]

Options:
  --data-dir <path>         Data root. Default: DATA_DIR or ./data
  --input <path>            Canonical seed NDJSON path
  --output-dir <path>       Processed LOAWA output dir
  --limit <n>               Max seeds to verify in this run
  --sleep-ms <n>            Delay between official API requests
  --status <csv>            Target statuses. Default: discovered,queued_for_api,api_failed_retryable
  --force                   Verify rows regardless of current apiStatus
  --no-cache                Ignore local API cache files
  --help, -h                Show this help
`);
}

async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, { recursive: true });
}

async function readFileIfExists(filePath) {
  try {
    return await fs.readFile(filePath, "utf-8");
  } catch {
    return null;
  }
}

async function readNdjson(filePath) {
  const raw = await readFileIfExists(filePath);
  if (!raw) return [];
  return raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

async function writeNdjson(filePath, rows) {
  const payload = rows.map((row) => JSON.stringify(row)).join("\n");
  await fs.writeFile(filePath, payload ? `${payload}\n` : "", "utf-8");
}

async function appendNdjson(filePath, rows) {
  if (!rows.length) return;
  const payload = rows.map((row) => JSON.stringify(row)).join("\n") + "\n";
  await fs.appendFile(filePath, payload, "utf-8");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function nowIso() {
  return new Date().toISOString();
}

function loadDotEnv(content) {
  const env = {};
  for (const line of content.split(/\r?\n/)) {
    if (!line || /^\s*#/.test(line)) continue;
    const idx = line.indexOf("=");
    if (idx < 0) continue;
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

async function resolveApiConfig() {
  const envPath = path.join(ROOT, ".env");
  const envFile = await readFileIfExists(envPath);
  const parsed = envFile ? loadDotEnv(envFile) : {};
  const apiKey = process.env.LOSTARK_API_KEY || parsed.LOSTARK_API_KEY || "";
  const baseUrl = (process.env.LOSTARK_API_BASE || parsed.LOSTARK_API_BASE || "https://developer-lostark.game.onstove.com").replace(/\/+$/, "");

  if (!apiKey) {
    throw new Error("LOSTARK_API_KEY is not set. Add it to D:\\LOA-HSI\\.env or the environment.");
  }
  return { apiKey, baseUrl };
}

function safeName(name) {
  return encodeURIComponent(String(name || "").trim());
}

function parseItemAvgLevel(value) {
  if (value === null || value === undefined) return null;
  const text = String(value).replace(/,/g, "");
  const match = text.match(/\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}

function buildCachePath(dataDir, characterName) {
  return path.join(dataDir, "cache", `character_${safeName(characterName)}_seed_verify_v1.json`);
}

function buildRawPath(dataDir, characterName) {
  const stamp = nowIso().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
  return path.join(dataDir, "raw", "characters", `${safeName(characterName)}_${stamp}_seed_verify_v1.json`);
}

async function fetchJson(url, headers, optional = false) {
  const response = await fetch(url, { headers });
  const text = await response.text();

  if ((response.status === 204 || response.status === 404) && optional) {
    return null;
  }
  if (!response.ok) {
    const error = new Error(text || `HTTP ${response.status}`);
    error.status = response.status;
    error.body = text;
    throw error;
  }
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch (error) {
    error.status = 502;
    throw error;
  }
}

async function fetchCharacterProfile(characterName, apiConfig, args) {
  const cachePath = buildCachePath(args.dataDir, characterName);
  if (args.useCache) {
    const cached = await readFileIfExists(cachePath);
    if (cached) {
      return {
        profile: JSON.parse(cached),
        rawPath: cachePath,
        cacheUsed: true,
      };
    }
  }

  const encoded = safeName(characterName);
  const headers = {
    accept: "application/json",
    Authorization: `bearer ${apiConfig.apiKey}`,
  };

  const profile = await fetchJson(`${apiConfig.baseUrl}/armories/characters/${encoded}/profiles`, headers);
  const payload = {
    profile,
    fetchedAt: nowIso(),
    _source: "seed_verify_profiles_only",
  };

  await ensureDir(path.dirname(cachePath));
  await fs.writeFile(cachePath, JSON.stringify(payload, null, 2), "utf-8");

  const rawPath = buildRawPath(args.dataDir, characterName);
  await ensureDir(path.dirname(rawPath));
  await fs.writeFile(rawPath, JSON.stringify(payload, null, 2), "utf-8");

  return {
    profile,
    rawPath,
    cacheUsed: false,
  };
}

function classifyApiFailure(error) {
  const status = Number(error?.status || 0);
  if (status === 404) {
    return { apiStatus: "api_not_found", retryable: false };
  }
  if (status === 429) {
    return { apiStatus: "api_failed_retryable", retryable: true };
  }
  if (status === 401 || status === 403) {
    return { apiStatus: "api_failed_terminal", retryable: false };
  }
  if (status >= 500 || status === 502 || status === 503 || status === 504) {
    return { apiStatus: "api_failed_retryable", retryable: true };
  }
  return { apiStatus: "api_failed_retryable", retryable: true };
}

function shouldProcessRow(row, args) {
  if (args.force) return true;
  const status = row.apiStatus || "discovered";
  return args.statuses.includes(status);
}

function selectRows(rows, args) {
  return rows.filter((row) => shouldProcessRow(row, args)).slice(0, args.limit);
}

function mergeCanonicalRow(row, result) {
  const next = { ...row };
  next.apiStatus = result.apiStatus;
  next.apiLastCheckedAt = result.checkedAt;
  next.apiRawPath = result.rawPath || null;
  next.apiCacheUsed = Boolean(result.cacheUsed);
  next.apiError = result.apiError || null;
  next.apiHttpStatus = result.apiHttpStatus || null;

  if (result.profile) {
    next.latestServerName = result.profile.ServerName || next.latestServerName || null;
    next.latestClassName = result.profile.CharacterClassName || next.latestClassName || null;
    next.latestItemAvgLevel = parseItemAvgLevel(result.profile.ItemAvgLevel);
    next.latestCharacterLevel = result.profile.CharacterLevel ?? next.latestCharacterLevel ?? null;
  }

  if (!next.firstSeenAt) next.firstSeenAt = result.checkedAt;
  next.lastSeenAt = next.lastSeenAt || result.checkedAt;
  return next;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return;
  }

  const apiConfig = await resolveApiConfig();
  const outputDir = args.outputDir || path.join(args.dataDir, "processed", "loawa");
  const inputPath = args.input || path.join(outputDir, "loawa_seed_canonical.ndjson");
  const checksPath = path.join(outputDir, "seed_api_checks.ndjson");
  const summaryPath = path.join(outputDir, "seed_api_last_batch_summary.json");

  await ensureDir(outputDir);
  await ensureDir(path.join(args.dataDir, "raw", "characters"));
  await ensureDir(path.join(args.dataDir, "cache"));

  const canonicalRows = await readNdjson(inputPath);
  if (!canonicalRows.length) {
    throw new Error(`No canonical seed rows found in ${inputPath}`);
  }

  const targets = selectRows(canonicalRows, args);
  if (!targets.length) {
    console.log("[SEED-API] No rows matched the requested status filter.");
    return;
  }

  const updates = new Map(canonicalRows.map((row) => [`${row.characterName}@@${row.serverName || ""}`, row]));
  const checkRows = [];
  const startedAt = nowIso();

  console.log(`[SEED-API] verifying ${targets.length} seeds`);

  for (let i = 0; i < targets.length; i += 1) {
    const row = targets[i];
    const checkedAt = nowIso();
    console.log(`[SEED-API] ${i + 1}/${targets.length} ${row.characterName}`);

    try {
      const fetched = await fetchCharacterProfile(row.characterName, apiConfig, args);
      const profile = fetched.profile || {};
      const result = {
        checkedAt,
        apiStatus: "api_ok",
        rawPath: fetched.rawPath,
        cacheUsed: fetched.cacheUsed,
        profile,
        apiHttpStatus: 200,
      };

      const updateKey = `${row.characterName}@@${row.serverName || ""}`;
      updates.set(updateKey, mergeCanonicalRow(row, result));
      checkRows.push({
        characterName: row.characterName,
        serverName: row.serverName || null,
        checkedAt,
        apiStatus: result.apiStatus,
        apiHttpStatus: 200,
        apiRawPath: fetched.rawPath,
        cacheUsed: fetched.cacheUsed,
        latestServerName: profile.ServerName || null,
        latestClassName: profile.CharacterClassName || null,
        latestItemAvgLevel: parseItemAvgLevel(profile.ItemAvgLevel),
      });
    } catch (error) {
      const classified = classifyApiFailure(error);
      const result = {
        checkedAt,
        apiStatus: classified.apiStatus,
        rawPath: null,
        cacheUsed: false,
        profile: null,
        apiHttpStatus: Number(error?.status || 0) || null,
        apiError: String(error?.body || error?.message || error),
      };
      const updateKey = `${row.characterName}@@${row.serverName || ""}`;
      updates.set(updateKey, mergeCanonicalRow(row, result));
      checkRows.push({
        characterName: row.characterName,
        serverName: row.serverName || null,
        checkedAt,
        apiStatus: result.apiStatus,
        apiHttpStatus: result.apiHttpStatus,
        apiRawPath: null,
        cacheUsed: false,
        apiError: result.apiError,
      });
    }

    if (i < targets.length - 1 && args.sleepMs > 0) {
      await sleep(args.sleepMs);
    }
  }

  const mergedRows = Array.from(updates.values()).sort((a, b) => String(a.characterName).localeCompare(String(b.characterName)));
  await writeNdjson(inputPath, mergedRows);
  await appendNdjson(checksPath, checkRows);

  const counts = checkRows.reduce((acc, row) => {
    acc[row.apiStatus] = (acc[row.apiStatus] || 0) + 1;
    return acc;
  }, {});

  const summary = {
    startedAt,
    finishedAt: nowIso(),
    inputPath,
    processed: checkRows.length,
    counts,
  };
  await fs.writeFile(summaryPath, JSON.stringify(summary, null, 2), "utf-8");

  console.log("[SEED-API] done");
  console.log(JSON.stringify(summary, null, 2));
}

main().catch((error) => {
  console.error("[SEED-API] verifier failed");
  console.error(error?.stack || String(error));
  process.exitCode = 1;
});
