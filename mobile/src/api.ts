import { File as ExpoFile } from 'expo-file-system';
import { API_BASE_URL } from './config';
import { getActiveAccountId, getActiveToken } from './accounts';

// One thin wrapper over the backend's /v2 API (specs/core/openapi.yaml).
// Auth is the active saved account's bearer token (accounts.ts), with the
// session cookie as a fallback for a farmer who never saved an account.

export class ApiError extends Error {
  status: number; // 0 = network failure / timeout
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
  get isNetwork() {
    return this.status === 0;
  }
}

// Reachability, derived from real request outcomes (no separate ping): a
// network failure flips it offline, any HTTP response flips it back online.
let online = true;
const netListeners = new Set<(o: boolean) => void>();
export const isOnline = () => online;
export function subscribeNet(fn: (o: boolean) => void) {
  netListeners.add(fn);
  return () => {
    netListeners.delete(fn);
  };
}
function setOnline(o: boolean) {
  if (o === online) return;
  online = o;
  netListeners.forEach((f) => f(o));
}

/** Render's free tier sleeps after ~15 idle minutes and takes up to a minute to
 *  wake. Pings /health (patiently, several times) so the first real request
 *  doesn't time out and get misreported as "can't reach the server". Never
 *  throws; resolves when the server answered or the attempts ran out.
 *  `onSlow` fires if the first answer takes more than a few seconds. */
export async function wakeServer(onSlow?: () => void): Promise<void> {
  const slowTimer = onSlow ? setTimeout(onSlow, 4000) : null;
  try {
    for (let i = 0; i < 4; i++) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 30000);
      try {
        const res = await fetch(`${API_BASE_URL}/health`, { signal: controller.signal });
        if (res.ok) {
          // This bypasses request()/fetchWithTimeout (its own retry loop needs
          // to swallow failures silently), so it must flip `online` back on
          // success itself -- otherwise a stale `online = false` from an
          // earlier failed request (e.g. one aborted by a force-stop, or a
          // timeout during a free-tier cold start) never clears, and the app
          // keeps reporting "offline" forever even once the server answers.
          setOnline(true);
          return;
        }
      } catch {
        // asleep / unreachable: try again
      } finally {
        clearTimeout(timer);
      }
    }
  } finally {
    if (slowTimer) clearTimeout(slowTimer);
  }
}

let onUnauthorized: ((accountId: string | null) => void) | null = null;
export function setUnauthorizedHandler(fn: ((accountId: string | null) => void) | null) {
  onUnauthorized = fn;
}

async function fetchWithTimeout(url: string, init: RequestInit, ms: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (e: any) {
    setOnline(false);
    throw new ApiError(0, e?.name === 'AbortError' ? 'timeout' : e?.message || 'network');
  } finally {
    clearTimeout(timer);
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  opts: { timeout?: number; auth?: boolean; tokenOverride?: string } = {},
): Promise<T> {
  const accountIdAtCallTime = getActiveAccountId();
  const token = opts.tokenOverride ?? getActiveToken();
  const headers: Record<string, string> = { Accept: 'application/json', ...((init.headers as any) || {}) };
  if (init.body && typeof init.body === 'string') headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetchWithTimeout(`${API_BASE_URL}${path}`, { ...init, headers }, opts.timeout ?? 20000);
  setOnline(true);
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = new ApiError(res.status, body?.error?.message || `HTTP ${res.status}`, body?.error?.code);
    if (res.status === 401 && opts.auth !== false && onUnauthorized) onUnauthorized(accountIdAtCallTime);
    throw err;
  }
  return body as T;
}

const json = (method: string, data: unknown): RequestInit => ({ method, body: JSON.stringify(data) });

// ---- types (mirror specs/core/openapi.yaml) --------------------------------
export type Farmer = { id: string; name: string; phone?: string | null; preferred_language: string; photo_url?: string | null; district?: string | null; state?: string | null };
export type Field = {
  id: string; name: string; latitude: number; longitude: number; area_ha: number;
  soil_type?: string | null; current_crop?: string | null; sown_on?: string | null;
};
export type CropRec = {
  id: string; recommended_crop: string; confidence: number; alternatives?: string[] | null;
  rationale?: string | null; season?: string | null; out_of_region?: boolean | null;
  regional_alternative?: string | null; rationale_plain?: string | null; created_at: string;
  details?: CropDetails | null;
};
export type CropDetails = {
  method: string; mode: 'best_fit' | 'keep_current';
  ranking: { crop: string; score: number; fit: 'good' | 'fair' | 'weak'; good_time_to_sow: boolean }[];
  current_crop?: { crop: string; score: number; fit: string; verdict: 'keep' | 'switch_next_season' } | null;
  temperature_c?: number; soil_ph?: number | null; soil_values_measured?: boolean; annual_rain_mm?: number | null; sowing_month?: number;
};
export type Irrigation = {
  id: string; recommended_depth_mm: number; window_start_at: string; window_end_at: string;
  urgency: string; rationale?: string | null; rationale_plain?: string | null; created_at: string;
  details?: IrrigationDetails | null;
};
export type IrrigationDetails = {
  method: 'soil_water_balance' | 'weekly_shortcut';
  soil_water_used_pct?: number; days_until_water?: number | null; waiting_for_rain?: boolean;
  rain_last_7d_mm?: number; rain_forecast_3d_mm?: number; rain_forecast_7d_mm?: number;
  crop_water_use_mm_per_day?: number; crop_stage?: string; weather_days_used?: number; weather_days_estimated?: number; et0_method?: string;
};
export type DiseaseDetails = {
  method: string; crop_specific?: boolean; score?: number; named_disease?: string | null;
  trend?: 'rising' | 'steady' | 'easing'; humid_days_last_7?: number; wet_days_last_7?: number;
  rain_forecast_3d_mm?: number | null; rain_forecast_7d_mm?: number | null; favourable_temp_c?: [number, number];
};
export type DiseaseAlert = {
  id: string; disease: string; disease_translated?: string; risk_level: string; confidence: number;
  recommended_action?: string | null; source?: string | null; created_at: string;
  // Server-stored copy of the scanned photo (2026-10-30) -- present once the
  // backend persists it, so history survives a reinstall/new device/
  // re-login instead of relying on savePhotoLocally's on-device-only cache.
  photo_url?: string | null;
};
export type Advisory = { id: string; title: string; body: string; body_plain?: string; severity: string; language: string; created_at: string };
export type Weather = {
  observed_at: string; source: string; temp_c: number; temp_min_c?: number | null; temp_max_c?: number | null;
  humidity_pct?: number | null; rainfall_mm?: number | null; wind_mps?: number | null; is_forecast: boolean;
};
export type Soil = {
  observed_at: string; source: string; ph?: number | null; nitrogen_mg_per_kg?: number | null;
  phosphorus_mg_per_kg?: number | null; potassium_mg_per_kg?: number | null;
  organic_carbon_pct?: number | null; moisture_pct?: number | null;
};
export type Ndvi = { observed_at: string; source: string; ndvi: number; cloud_cover_pct?: number | null; satellite?: string | null };
export type SoilUsed = {
  ph?: number | null; nitrogen_mg_per_kg?: number | null; phosphorus_mg_per_kg?: number | null;
  potassium_mg_per_kg?: number | null; organic_carbon_pct?: number | null; moisture_pct?: number | null;
  chemistry_source?: string | null; moisture_source?: string | null;
};
export type DataSummary = {
  fetched_at?: string;
  soil_used?: SoilUsed | null;
  weather: { current: Weather | null; recent: Weather[]; forecast: Weather[] };
  soil: Soil | null;
  ndvi: { latest: Ndvi | null; history: Ndvi[] };
};

// ---- auth --------------------------------------------------------------------
export const requestOtp = (phone: string, name: string, preferred_language: string) =>
  request<{ phone: string; otp_sent: boolean; is_new_farmer: boolean }>(
    '/v2/auth/request-otp', json('POST', { phone, name, preferred_language }), { auth: false, timeout: 40000 });
export const verifyOtp = (phone: string, otp: string) =>
  request<Farmer & { session_token: string }>('/v2/auth/verify-otp', json('POST', { phone, otp }), { auth: false, timeout: 40000 });
export const logout = () => request<void>('/v2/auth/logout', { method: 'POST' }, { auth: false, timeout: 6000 }).catch(() => undefined);
// Signs out a specific account, not whatever is active right now.
export const logoutWithToken = (token: string) =>
  request<void>('/v2/auth/logout', { method: 'POST' }, { auth: false, timeout: 6000, tokenOverride: token }).catch(() => undefined);

// ---- farmer / fields ---------------------------------------------------------
export const getMe = () => request<Farmer>('/v2/farmers/me', {}, { timeout: 8000 });
export const patchMe = (data: Partial<Pick<Farmer, 'name' | 'preferred_language' | 'photo_url' | 'district' | 'state'>>) =>
  request<Farmer>('/v2/farmers/me', json('PATCH', data));
export const listFields = () => request<{ items: Field[] }>('/v2/fields', {}, { timeout: 10000 }).then((r) => r.items);
export const createField = (data: Record<string, unknown>) =>
  request<Field & { data_acquisition?: Record<string, string> }>('/v2/fields', json('POST', data), { timeout: 45000 });
export const patchField = (id: string, data: Record<string, unknown>) => request<Field>(`/v2/fields/${id}`, json('PATCH', data));
export const deleteField = (id: string) => request<void>(`/v2/fields/${id}`, { method: 'DELETE' });
export const refreshData = (id: string) =>
  request<{ data_acquisition: Record<string, string> }>(`/v2/fields/${id}/refresh-data`, { method: 'POST' }, { timeout: 45000 });
export const dataSummary = (id: string): Promise<DataSummary> =>
  // Field finding (2026-10-30, audit): this used to catch any failure --
  // including a request that simply hadn't finished acquiring data yet --
  // and silently substitute fully-fabricated weather/soil/NDVI readings
  // (specific fake numbers: 28.5°C, pH 6.8, NDVI 0.68...) presented as if
  // they were real sensor/satellite data, indistinguishable from the real
  // thing. Same bug class as the disease-risk fake fallback already fixed;
  // let the real request (or a real error) through.
  request<DataSummary>(`/v2/fields/${id}/data-summary`, {}, { timeout: 8000 });

// ---- the three models + advisory ---------------------------------------------
// Field finding (2026-10-30, audit): getRecommendation/getIrrigation used
// to catch any failure or empty result and substitute a hardcoded fake
// answer (always "tomato, 92% confidence" / always "18.5mm, moderate") --
// a farmer whose request failed once got a confident, specific, entirely
// fabricated recommendation with no indication it wasn't real. Same bug
// class as the disease-risk and data-summary fake fallbacks.
export const getRecommendation = (id: string, keepCurrent = false): Promise<CropRec> =>
  request<CropRec>(`/v2/fields/${id}/recommendation${keepCurrent ? '?keep_current=true' : ''}`, {}, { timeout: 8000 });

export const getIrrigation = (id: string): Promise<Irrigation> =>
  request<Irrigation>(`/v2/fields/${id}/irrigation`, {}, { timeout: 8000 });

// same call, but keeps the `details` object (trend, wet days) next to the items
export const getDiseaseRiskFull = async (id: string, lang: string) => {
  // Field finding (2026-10-30): this used to catch BOTH a real network/
  // server failure AND a genuinely empty result (a field with no scans
  // yet -- a completely normal, honest state) and paper over either one
  // with the exact same hardcoded fake "Tomato Early Blight" entry. Home
  // tab showed that fake diagnosis as if it were real, with zero
  // connection to what was actually in the Scan tab's real history --
  // the "not syncing" symptom was this literally being fabricated data,
  // not a sync bug. Empty is now a real, valid result (HomeTab already
  // has a proper "not computed yet" empty state for it); only a genuine
  // request failure throws, and it throws the real error instead of
  // masking it.
  return request<{ items: DiseaseAlert[]; details?: DiseaseDetails | null }>(
    `/v2/fields/${id}/disease-risk?language=${lang}`, {}, { timeout: 8000 },
  );
};

export const getDiseaseRisk = (id: string, lang: string) =>
  getDiseaseRiskFull(id, lang).then((r) => r.items);

// generate=false only lists stored advisories (opening the tab); generate=true
// computes and stores a new one (the "Get today's advice" button).
// Field finding (2026-10-30, audit): used to catch any failure or a
// genuinely-empty-but-valid "no advisories yet" result and substitute a
// single fully-written fake advisory ("Optimal root-zone moisture recorded
// at 26.5%...") presented as real, specific agronomic guidance. Same bug
// class as the other fake fallbacks found and removed this session.
export const getAdvisories = async (id: string, generate = false): Promise<Advisory[]> => {
  const res = await request<{ items: Advisory[] }>(`/v2/fields/${id}/advisories?generate=${generate}`, {}, { timeout: 25000 });
  return res?.items ?? [];
};

// ---- scan / feedback / bug reports --------------------------------------------
// `file` is an expo-file-system File (implements Blob) -- see ScanTab for why
// fetch(file://) is not used.
export const scanLeaf = async (id: string, file: Blob, lang: string): Promise<DiseaseAlert> => {
  const form = new FormData();
  form.append('image', file as any, 'leaf.jpg');
  // 60s, not 35s: the backend now retries every configured Gemini key on a
  // transient failure (overload/timeout/network error) across two cascading
  // calls (leaf precheck + analysis), which can legitimately take longer
  // than a single quick call -- 35s was cutting that off before the server
  // had exhausted its own retries and could return either a real result or
  // an honest unavailable error.
  const res = await request<DiseaseAlert>(`/v2/fields/${id}/disease-risk/image?language=${lang}`, { method: 'POST', body: form }, { timeout: 60000 });
  return res;
};
export const sendFeedback = (data: { advisory_id: string; rating: number; helpful: boolean; comment?: string }) =>
  request<unknown>('/v2/feedback', json('POST', data));
export const sendBugReport = (data: Record<string, unknown>) => request<unknown>('/v2/bug-reports', json('POST', data));

export const translateTexts = (texts: string[], target_lang: string) =>
  request<{ texts: string[]; translated: boolean }>('/v2/translate', json('POST', { texts, target_lang }), { timeout: 120000 });

// ---- voice ---------------------------------------------------------------------
export const advisoryAudioUrl = (id: string, lang: string) => `${API_BASE_URL}/v2/advisories/${id}/audio?language=${lang}`;
export type AskResult = {
  question_text: string; detected_lang: string; answer_text: string; language: string;
  answer_audio_base64: string | null; answer_audio_mimetype: string | null;
};
// Field finding (2026-10-30, audit): the worst instance of the fake-
// fallback bug found this session -- any failure (including the mic/
// network/server genuinely not understanding the farmer) used to return a
// fake TRANSCRIPTION of a question the farmer never asked ("What is
// today's irrigation advisory?") plus a fake spoken-sounding answer,
// presented as if their actual voice had been heard and answered. Let the
// real result or a real error through.
export const askByVoice = async (audioUri: string, mime: string, expectedLang: string): Promise<AskResult> => {
  const f = new ExpoFile(audioUri);
  if (!f.exists || !f.size) return Promise.reject(new ApiError(-1, 'no recording'));
  const form = new FormData();
  form.append('audio', f as unknown as Blob, 'question.m4a');
  form.append('expected_lang', expectedLang);
  return request<AskResult>('/v2/voice/ask', { method: 'POST', body: form }, { timeout: 45000 });
};

export type ConversationItem = { id: string; field_id?: string; question: string; answer: string; lang: string; ts: number };

export const fetchConversationsApi = async (fieldId?: string): Promise<ConversationItem[]> => {
  const query = fieldId ? `?field_id=${encodeURIComponent(fieldId)}` : '';
  const res = await request<{ conversations: ConversationItem[] }>(`/v2/conversations${query}`, { method: 'GET' });
  return res.conversations || [];
};

export const saveConversationApi = async (entry: { field_id?: string; question: string; answer: string; lang: string; ts?: number }): Promise<ConversationItem> => {
  return request<ConversationItem>('/v2/conversations', {
    method: 'POST',
    body: JSON.stringify(entry),
  });
};

// ---- chat (floating assistant) ---------------------------------------------
export type ChatHistoryItem = { role: 'user' | 'assistant'; content: string };
export type ChatChart = { type: 'bar' | 'line'; title: string; labels: string[]; values: number[] };
export type ChatResult = { reply: string; chart: ChatChart | null };

export const sendChatMessage = (message: string, history: ChatHistoryItem[], language: string): Promise<ChatResult> =>
  request<ChatResult>('/v2/chat', json('POST', { message, history, language }), { timeout: 30000 });

export { API_BASE_URL };
