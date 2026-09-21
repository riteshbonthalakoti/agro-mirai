import { File as ExpoFile } from 'expo-file-system';
import { API_BASE_URL } from './config';

// One thin wrapper over the backend's /v2 API (specs/core/openapi.yaml).
// Auth is the backend's signed session cookie, which React Native's native
// networking layer stores and resends by itself -- no token handling here.

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

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
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
  opts: { timeout?: number; auth?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', ...((init.headers as any) || {}) };
  if (init.body && typeof init.body === 'string') headers['Content-Type'] = 'application/json';
  const res = await fetchWithTimeout(`${API_BASE_URL}${path}`, { ...init, headers }, opts.timeout ?? 20000);
  setOnline(true);
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = new ApiError(res.status, body?.error?.message || `HTTP ${res.status}`, body?.error?.code);
    if (res.status === 401 && opts.auth !== false && onUnauthorized) onUnauthorized();
    throw err;
  }
  return body as T;
}

const json = (method: string, data: unknown): RequestInit => ({ method, body: JSON.stringify(data) });

// ---- types (mirror specs/core/openapi.yaml) --------------------------------
export type Farmer = { id: string; name: string; phone?: string | null; preferred_language: string; photo_url?: string | null };
export type Field = {
  id: string; name: string; latitude: number; longitude: number; area_ha: number;
  soil_type?: string | null; current_crop?: string | null; sown_on?: string | null;
};
export type CropRec = {
  id: string; recommended_crop: string; confidence: number; alternatives?: string[] | null;
  rationale?: string | null; season?: string | null; out_of_region?: boolean | null;
  regional_alternative?: string | null; rationale_plain?: string | null; created_at: string;
};
export type Irrigation = {
  id: string; recommended_depth_mm: number; window_start_at: string; window_end_at: string;
  urgency: string; rationale?: string | null; rationale_plain?: string | null; created_at: string;
};
export type DiseaseAlert = {
  id: string; disease: string; disease_translated?: string; risk_level: string; confidence: number;
  recommended_action?: string | null; source?: string | null; created_at: string;
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
    '/v2/auth/request-otp', json('POST', { phone, name, preferred_language }), { auth: false, timeout: 12000 });
export const verifyOtp = (phone: string, otp: string) =>
  request<Farmer>('/v2/auth/verify-otp', json('POST', { phone, otp }), { auth: false, timeout: 12000 });
export const logout = () => request<void>('/v2/auth/logout', { method: 'POST' }, { auth: false, timeout: 6000 }).catch(() => undefined);

// ---- farmer / fields ---------------------------------------------------------
export const getMe = () => request<Farmer>('/v2/farmers/me', {}, { timeout: 8000 });
export const patchMe = (data: Partial<Pick<Farmer, 'name' | 'preferred_language' | 'photo_url'>>) =>
  request<Farmer>('/v2/farmers/me', json('PATCH', data));
export const listFields = () => request<{ items: Field[] }>('/v2/fields', {}, { timeout: 10000 }).then((r) => r.items);
export const createField = (data: Record<string, unknown>) =>
  request<Field & { data_acquisition?: Record<string, string> }>('/v2/fields', json('POST', data), { timeout: 45000 });
export const patchField = (id: string, data: Record<string, unknown>) => request<Field>(`/v2/fields/${id}`, json('PATCH', data));
export const deleteField = (id: string) => request<void>(`/v2/fields/${id}`, { method: 'DELETE' });
export const refreshData = (id: string) =>
  request<{ data_acquisition: Record<string, string> }>(`/v2/fields/${id}/refresh-data`, { method: 'POST' }, { timeout: 45000 });
export const dataSummary = (id: string) => request<DataSummary>(`/v2/fields/${id}/data-summary`, {}, { timeout: 15000 });

// ---- the three models + advisory ---------------------------------------------
export const getRecommendation = (id: string) => request<CropRec>(`/v2/fields/${id}/recommendation`, {}, { timeout: 30000 });
export const getIrrigation = (id: string) => request<Irrigation>(`/v2/fields/${id}/irrigation`, {}, { timeout: 30000 });
export const getDiseaseRisk = (id: string, lang: string) =>
  request<{ items: DiseaseAlert[] }>(`/v2/fields/${id}/disease-risk?language=${lang}`, {}, { timeout: 30000 }).then((r) => r.items);
// generate=false only lists stored advisories (opening the tab); generate=true
// computes and stores a new one (the "Get today's advice" button).
export const getAdvisories = (id: string, generate = false) =>
  request<{ items: Advisory[] }>(`/v2/fields/${id}/advisories?generate=${generate}`, {}, { timeout: 60000 }).then((r) => r.items);

// ---- scan / feedback / bug reports --------------------------------------------
// `file` is an expo-file-system File (implements Blob) -- see ScanTab for why
// fetch(file://) is not used.
export const scanLeaf = (id: string, file: Blob, lang: string) => {
  const form = new FormData();
  form.append('image', file as any, 'leaf.jpg');
  return request<DiseaseAlert>(`/v2/fields/${id}/disease-risk/image?language=${lang}`, { method: 'POST', body: form }, { timeout: 60000 });
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
export const askByVoice = (audioUri: string, mime: string, expectedLang: string) => {
  // Same approach as scanLeaf: an expo-file-system File is a real Blob. The
  // {uri,name,type} shortcut made Android fail the upload before sending
  // anything, which the app then misreported as "can't reach the server".
  const f = new ExpoFile(audioUri);
  if (!f.exists || !f.size) return Promise.reject(new ApiError(-1, 'no recording'));
  const form = new FormData();
  form.append('audio', f as unknown as Blob, 'question.m4a');
  form.append('expected_lang', expectedLang);
  return request<AskResult>('/v2/voice/ask', { method: 'POST', body: form }, { timeout: 90000 });
};

export { API_BASE_URL };
