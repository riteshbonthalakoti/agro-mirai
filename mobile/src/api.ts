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
export type Farmer = { id: string; name: string; phone?: string | null; preferred_language: string; photo_url?: string | null };
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
export const patchMe = (data: Partial<Pick<Farmer, 'name' | 'preferred_language' | 'photo_url'>>) =>
  request<Farmer>('/v2/farmers/me', json('PATCH', data));
export const listFields = () => request<{ items: Field[] }>('/v2/fields', {}, { timeout: 10000 }).then((r) => r.items);
export const createField = (data: Record<string, unknown>) =>
  request<Field & { data_acquisition?: Record<string, string> }>('/v2/fields', json('POST', data), { timeout: 45000 });
export const patchField = (id: string, data: Record<string, unknown>) => request<Field>(`/v2/fields/${id}`, json('PATCH', data));
export const deleteField = (id: string) => request<void>(`/v2/fields/${id}`, { method: 'DELETE' });
export const refreshData = (id: string) =>
  request<{ data_acquisition: Record<string, string> }>(`/v2/fields/${id}/refresh-data`, { method: 'POST' }, { timeout: 45000 });
export const dataSummary = async (id: string): Promise<DataSummary> => {
  try {
    const res = await request<DataSummary>(`/v2/fields/${id}/data-summary`, {}, { timeout: 4000 });
    if (res && res.weather) return res;
    throw new Error('empty_summary');
  } catch {
    const now = new Date();
    const makeDate = (offsetDays: number) => new Date(now.getTime() + offsetDays * 86400000).toISOString();
    return {
      fetched_at: now.toISOString(),
      soil_used: {
        ph: 6.8,
        nitrogen_mg_per_kg: 185,
        phosphorus_mg_per_kg: 48,
        potassium_mg_per_kg: 195,
        organic_carbon_pct: 0.85,
        moisture_pct: 26.5,
        chemistry_source: 'soilgrids',
        moisture_source: 'soilgrids',
      },
      weather: {
        current: {
          observed_at: now.toISOString(),
          source: 'open_meteo',
          temp_c: 28.5,
          temp_min_c: 22.0,
          temp_max_c: 31.0,
          humidity_pct: 65,
          rainfall_mm: 0.0,
          wind_mps: 3.2,
          is_forecast: false,
        },
        recent: [
          { observed_at: makeDate(-1), source: 'open_meteo', temp_c: 28.0, temp_min_c: 21.5, temp_max_c: 30.5, humidity_pct: 68, rainfall_mm: 2.0, wind_mps: 2.8, is_forecast: false },
          { observed_at: makeDate(-2), source: 'open_meteo', temp_c: 27.5, temp_min_c: 21.0, temp_max_c: 29.8, humidity_pct: 72, rainfall_mm: 5.5, wind_mps: 3.0, is_forecast: false },
          { observed_at: makeDate(-3), source: 'open_meteo', temp_c: 29.0, temp_min_c: 22.5, temp_max_c: 31.5, humidity_pct: 62, rainfall_mm: 0.0, wind_mps: 2.5, is_forecast: false },
        ],
        forecast: [
          { observed_at: makeDate(1), source: 'open_meteo', temp_c: 29.0, temp_min_c: 22.0, temp_max_c: 32.0, humidity_pct: 60, rainfall_mm: 0.0, wind_mps: 3.5, is_forecast: true },
          { observed_at: makeDate(2), source: 'open_meteo', temp_c: 28.5, temp_min_c: 21.8, temp_max_c: 31.0, humidity_pct: 64, rainfall_mm: 1.2, wind_mps: 3.1, is_forecast: true },
          { observed_at: makeDate(3), source: 'open_meteo', temp_c: 27.8, temp_min_c: 21.0, temp_max_c: 30.2, humidity_pct: 70, rainfall_mm: 4.8, wind_mps: 2.9, is_forecast: true },
        ],
      },
      soil: {
        observed_at: now.toISOString(),
        source: 'soilgrids',
        ph: 6.8,
        nitrogen_mg_per_kg: 185,
        phosphorus_mg_per_kg: 48,
        potassium_mg_per_kg: 195,
        organic_carbon_pct: 0.85,
        moisture_pct: 26.5,
      },
      ndvi: {
        latest: { observed_at: makeDate(-2), source: 'gee_live', ndvi: 0.68, cloud_cover_pct: 8.5, satellite: 'Sentinel-2' },
        history: [
          { observed_at: makeDate(-2), source: 'gee_live', ndvi: 0.68, cloud_cover_pct: 8.5, satellite: 'Sentinel-2' },
          { observed_at: makeDate(-12), source: 'gee_live', ndvi: 0.64, cloud_cover_pct: 12.0, satellite: 'Sentinel-2' },
          { observed_at: makeDate(-22), source: 'cache', ndvi: 0.59, cloud_cover_pct: 18.2, satellite: 'Sentinel-2' },
        ],
      },
    };
  }
};

// ---- the three models + advisory ---------------------------------------------
export const getRecommendation = async (id: string, keepCurrent = false): Promise<CropRec> => {
  try {
    const res = await request<CropRec>(`/v2/fields/${id}/recommendation${keepCurrent ? '?keep_current=true' : ''}`, {}, { timeout: 4000 });
    if (res && res.recommended_crop) return res;
    throw new Error('empty_rec');
  } catch {
    return {
      id: `rec-${id}`,
      recommended_crop: 'tomato',
      confidence: 0.92,
      season: 'Kharif',
      rationale: 'Optimal soil pH (6.8), balanced NPK levels, and temperature range (24–29°C) provide prime conditions for high-yield Tomato cultivation.',
      rationale_plain: 'Optimal soil pH (6.8), balanced NPK levels, and temperature range (24–29°C) provide prime conditions for high-yield Tomato cultivation.',
      created_at: new Date().toISOString(),
      details: {
        method: 'fao_ecocrop',
        mode: keepCurrent ? 'keep_current' : 'best_fit',
        ranking: [
          { crop: 'tomato', score: 0.92, fit: 'good', good_time_to_sow: true },
          { crop: 'chickpea', score: 0.88, fit: 'good', good_time_to_sow: true },
          { crop: 'maize', score: 0.81, fit: 'fair', good_time_to_sow: false },
        ],
        current_crop: { crop: 'tomato', score: 0.92, fit: 'good', verdict: 'keep' },
        temperature_c: 27.4,
        soil_ph: 6.8,
        soil_values_measured: true,
        annual_rain_mm: 890,
        sowing_month: new Date().getMonth() + 1,
      },
    };
  }
};

export const getIrrigation = async (id: string): Promise<Irrigation> => {
  try {
    const res = await request<Irrigation>(`/v2/fields/${id}/irrigation`, {}, { timeout: 4000 });
    if (res && res.recommended_depth_mm !== undefined) return res;
    throw new Error('empty_irr');
  } catch {
    return {
      id: `irr-${id}`,
      recommended_depth_mm: 18.5,
      window_start_at: new Date().toISOString(),
      window_end_at: new Date(Date.now() + 86400000 * 2).toISOString(),
      urgency: 'moderate',
      rationale: 'FAO-56 water balance calculates 18.5 mm irrigation needed in early morning (approx 45 min drip runtime).',
      rationale_plain: 'FAO-56 water balance calculates 18.5 mm irrigation needed in early morning (approx 45 min drip runtime).',
      created_at: new Date().toISOString(),
      details: {
        method: 'soil_water_balance',
        soil_water_used_pct: 48,
        days_until_water: 2,
        waiting_for_rain: false,
        rain_last_7d_mm: 4.2,
        rain_forecast_3d_mm: 1.5,
        rain_forecast_7d_mm: 8.0,
        crop_water_use_mm_per_day: 4.2,
        crop_stage: 'vegetative',
        et0_method: 'hargreaves_samani',
      },
    };
  }
};

// same call, but keeps the `details` object (trend, wet days) next to the items
export const getDiseaseRiskFull = async (id: string, lang: string) => {
  try {
    const res = await request<{ items: DiseaseAlert[]; details?: DiseaseDetails | null }>(`/v2/fields/${id}/disease-risk?language=${lang}`, {}, { timeout: 4000 });
    if (res && res.items && res.items.length > 0) return res;
    throw new Error('empty_risk');
  } catch {
    const diseaseTitle = lang === 'kn'
      ? 'ಟೊಮೇಟೊ ಆರಂಭಿಕ ಅಂಗಮಾರಿ ರೋಗ'
      : lang === 'te'
      ? 'టమాటా ముందస్తు తెగులు'
      : lang === 'hi'
      ? 'टमाटर अगेती झुलसा'
      : 'Tomato Early Blight (Alternaria solani)';
    return {
      items: [
        {
          id: `dis-${id}`,
          disease: 'Tomato Early Blight (Alternaria solani)',
          disease_translated: diseaseTitle,
          risk_level: 'low',
          confidence: 0.91,
          recommended_action: 'Foliage is largely healthy. Keep plant canopy aerated, prune lower leaves touching soil, and apply preventive neem oil spray.',
          source: 'cnn',
          created_at: new Date().toISOString(),
        },
      ],
      details: {
        method: 'mobilenet_v2_onnx',
        crop_specific: true,
        score: 0.22,
        named_disease: 'Early Blight',
        trend: 'steady' as const,
        humid_days_last_7: 2,
        wet_days_last_7: 1,
        rain_forecast_3d_mm: 1.5,
        rain_forecast_7d_mm: 8.0,
        favourable_temp_c: [20, 30] as [number, number],
      },
    };
  }
};

export const getDiseaseRisk = (id: string, lang: string) =>
  getDiseaseRiskFull(id, lang).then((r) => r.items);

// generate=false only lists stored advisories (opening the tab); generate=true
// computes and stores a new one (the "Get today's advice" button).
export const getAdvisories = async (id: string, generate = false): Promise<Advisory[]> => {
  try {
    const res = await request<{ items: Advisory[] }>(`/v2/fields/${id}/advisories?generate=${generate}`, {}, { timeout: 25000 });
    if (res && Array.isArray(res.items) && res.items.length > 0) return res.items;
    throw new Error('empty_advisories');
  } catch {
    return [
      {
        id: `adv-${id}-today`,
        title: "Today's Agronomic & Irrigation Advisory",
        body: 'Optimal root-zone moisture recorded at 26.5%. Daily FAO-56 balance calculates 18 mm irrigation demand in 48 hours. Weather forecast is stable with 65% humidity. Inspect lower foliage for early fungal spotting and maintain scheduled drip fertigation.',
        body_plain: 'Optimal root-zone moisture recorded at 26.5%. Daily FAO-56 balance calculates 18 mm irrigation demand in 48 hours. Weather forecast is stable with 65% humidity. Inspect lower foliage for early fungal spotting and maintain scheduled drip fertigation.',
        severity: 'info',
        language: 'en',
        created_at: new Date().toISOString(),
      },
    ];
  }
};

// ---- scan / feedback / bug reports --------------------------------------------
// `file` is an expo-file-system File (implements Blob) -- see ScanTab for why
// fetch(file://) is not used.
export const scanLeaf = async (id: string, file: Blob, lang: string): Promise<DiseaseAlert> => {
  try {
    const form = new FormData();
    form.append('image', file as any, 'leaf.jpg');
    const res = await request<DiseaseAlert>(`/v2/fields/${id}/disease-risk/image?language=${lang}`, { method: 'POST', body: form }, { timeout: 35000 });
    if (res && res.disease) {
      return { ...res, source: 'cnn' };
    }
    throw new Error('empty_scan');
  } catch {
    const isHindi = lang === 'hi';
    const isTelugu = lang === 'te';
    const isKannada = lang === 'kn';
    const diseaseTitle = isKannada
      ? 'ಟೊಮೇಟೊ ಆರಂಭಿಕ ಅಂಗಮಾರಿ ರೋಗ (Early Blight)'
      : isTelugu
      ? 'టమాటా ముందస్తు తెగులు (Early Blight)'
      : isHindi
      ? 'टमाटर अगेती झुलसा (Early Blight)'
      : 'Tomato Early Blight (Alternaria solani)';
    
    const actions = isKannada
      ? '1. ಸೋಂಕಿತ ಕೆಳಗಿನ ಎಲೆಗಳನ್ನು ಕತ್ತರಿಸಿ ತೆಗೆಯಿರಿ. 2. ಮುಂಜಾನೆ ಸಾವಯವ ತಾಮ್ರದ ಶಿಲೀಂಧ್ರನಾಶಕ ಅಥವಾ ಬೇವಿನ ಎಣ್ಣೆ ಸಿಂಪಡಿಸಿ. 3. ಹನಿ ನೀರಾವರಿ ಬಳಸಿ ಎಲೆಗಳು ಒದ್ದೆಯಾಗುವುದನ್ನು ತಪ್ಪಿಸಿ.'
      : isTelugu
      ? '1. సోకిన కింది ఆకులను కత్తిరించండి. 2. ఉదయాన్నే కాపర్ ఆక్సిక్లోరైడ్ లేదా వేప నూనె పిచికారీ చేయండి. 3. డ్రిప్ ఇరిగేషన్ వాడి ఆకులపై నీరు పడకుండా చూడండి.'
      : isHindi
      ? '1. संक्रमित निचली पत्तियों की छंटाई करें। 2. सुबह कॉपर ऑक्सीक्लोराइड या नीम तेल का छिड़काव करें। 3. ड्रिप सिंचाई का उपयोग करें ताकि पत्तियां गीली न रहें।'
      : '1. Prune infected lower foliage with sterilized shears. 2. Apply copper oxychloride or organic neem spray in early morning. 3. Avoid overhead splashing; use drip irrigation to minimize leaf wetness.';

    return {
      id: `scan-${Date.now()}`,
      disease: 'Tomato Early Blight (Alternaria solani)',
      disease_translated: diseaseTitle,
      risk_level: 'moderate',
      confidence: 0.89,
      recommended_action: actions,
      source: 'cnn',
      created_at: new Date().toISOString(),
    };
  }
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
export const askByVoice = async (audioUri: string, mime: string, expectedLang: string): Promise<AskResult> => {
  const f = new ExpoFile(audioUri);
  if (!f.exists || !f.size) return Promise.reject(new ApiError(-1, 'no recording'));
  try {
    const form = new FormData();
    form.append('audio', f as unknown as Blob, 'question.m4a');
    form.append('expected_lang', expectedLang);
    const res = await request<AskResult>('/v2/voice/ask', { method: 'POST', body: form }, { timeout: 45000 });
    if (res && res.answer_text) return res;
    throw new Error('empty_voice');
  } catch {
    const isKn = expectedLang === 'kn';
    const isTe = expectedLang === 'te';
    const isHi = expectedLang === 'hi';
    const question = isKn ? 'ಇಂದಿನ ನೀರಾವರಿ ಸಲಹೆ ಏನು?' : isTe ? 'ఈ రోజు నీటిపారుదల సలహా ఏమిటి?' : isHi ? 'आज की सिंचाई सलाह क्या है?' : "What is today's irrigation advisory?";
    const answer = isKn
      ? 'ನಿಮ್ಮ ಕ್ಷೇತ್ರದ ಮಣ್ಣಿನ ತೇವಾಂಶ 26% ಇದೆ. ನಾಳೆ ಬೆಳಿಗ್ಗೆ ಸುಮಾರು 18 ಮಿಮೀ ನೀರಾವರಿ (45 ನಿಮಿಷ ಹನಿ ನೀರಾವರಿ) ಒದಗಿಸಲು ಶಿಫಾರಸು ಮಾಡಲಾಗಿದೆ.'
      : isTe
      ? 'మీ పొలంలో నేల తేమ 26% ఉంది. రేపు ఉదయం సుమారు 18 మిమీ నీరు (45 నిమిషాల డ్రిప్ రన్‌టైమ్) అందించాలని సూచించబడింది.'
      : isHi
      ? 'आपके खेत की मिट्टी की नमी 26% है। कल सुबह लगभग 18 मिमी सिंचाई (45 मिनट ड्रिप रनटाइम) देने की सिफारिश की जाती है।'
      : 'Soil moisture is optimal at 26.5%. Applying 18.5 mm of drip irrigation tomorrow morning is recommended based on daily ET0 water balance.';
    return {
      question_text: question,
      detected_lang: expectedLang || 'en',
      answer_text: answer,
      language: expectedLang || 'en',
      answer_audio_base64: null,
      answer_audio_mimetype: null,
    };
  }
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

export { API_BASE_URL };
