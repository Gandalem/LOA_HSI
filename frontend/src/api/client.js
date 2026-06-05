const API_BASE = import.meta.env.VITE_API_BASE || '/api';

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function request(path, options = {}, attempt = 0) {
  const maxRetries = options.retry ?? 5;
  const fetchOptions = { ...options };
  delete fetchOptions.retry;

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(fetchOptions.headers || {})
      },
      ...fetchOptions
    });
  } catch (e) {
    if (attempt < maxRetries) {
      await sleep(700 + attempt * 500);
      return request(path, options, attempt + 1);
    }
    throw e;
  }

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (_e) {
    data = text;
  }

  if (!res.ok) {
    if ([502, 503, 504].includes(res.status) && attempt < maxRetries) {
      await sleep(700 + attempt * 500);
      return request(path, options, attempt + 1);
    }
    const detail = data?.detail || data || `HTTP ${res.status}`;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data;
}

export function getCharacterSummary(characterName, useCache = true) {
  return request(`/characters/${encodeURIComponent(characterName)}/summary?use_cache=${useCache}`);
}

export function compareCharacter(payload) {
  return request('/simulations/compare-character', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}


export function getLatestMaterialPrices() {
  return request('/material-prices/latest');
}

export function ensureMaterialPrices() {
  return request('/material-prices/ensure', {
    method: 'POST',
    body: JSON.stringify({ useConfigFile: true, forceRefresh: false })
  });
}

export function collectMaterialPrices(forceRefresh = true) {
  return request('/material-prices/collect', {
    method: 'POST',
    body: JSON.stringify({ useConfigFile: true, forceRefresh })
  });
}

export function getMaterialPriceAutoStatus() {
  return request('/material-prices/auto-status');
}

export function getHoningTable() {
  return request('/honing/table');
}
