import React, { createContext, useContext } from 'react';
import { CROP_LABELS, Key, Lang, SOIL_LABELS, STRINGS } from './i18n';
import { Farmer, Field } from './api';

export type Ctx = {
  lang: Lang;
  t: (k: Key) => string;
  farmer: Farmer;
  setFarmer: (f: Farmer) => void;
  fields: Field[];
  field: Field | null;
  selectField: (id: string) => void;
  reloadFields: () => Promise<void>;
  changeLang: (l: Lang) => void;
  openFieldForm: (f?: Field) => void;
  signOut: () => void;
};

export const AppCtx = createContext<Ctx | null>(null);
export const useApp = () => {
  const c = useContext(AppCtx);
  if (!c) throw new Error('AppCtx missing');
  return c;
};

export const makeT = (lang: Lang) => (k: Key) => STRINGS[lang][k] ?? STRINGS.en[k];
export const cropLabel = (lang: Lang, k?: string | null) => (k ? CROP_LABELS[lang]?.[k] || k : '—');
export const soilLabel = (lang: Lang, k?: string | null) => (k ? SOIL_LABELS[lang]?.[k] || k : '—');

export function levelLabel(t: (k: Key) => string, level?: string | null): string {
  switch ((level || '').toLowerCase()) {
    case 'low': return t('urgencyLow');
    case 'moderate': return t('urgencyModerate');
    case 'high': return t('urgencyHigh');
    case 'severe': return t('urgencySevere');
    default: return level || '—';
  }
}

export function diseaseAction(t: (k: Key) => string, level?: string | null, fallback?: string | null): string {
  switch ((level || '').toLowerCase()) {
    case 'low': return t('diseaseActionLow');
    case 'moderate': return t('diseaseActionModerate');
    case 'high': return t('diseaseActionHigh');
    case 'severe': return t('diseaseActionSevere');
    default: return fallback || '';
  }
}

export function sourceLabel(t: (k: Key) => string, src?: string | null): string {
  if (src === 'cnn') return t('scanSourceCnn');
  if (src === 'environmental_fallback') return t('scanSourceEnvironmentalFallback');
  if (src === 'environmental') return t('scanSourceEnvironmental');
  return src || '—';
}

export function fmtDate(iso?: string | null, withTime = false): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return withTime
    ? d.toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString([], { day: 'numeric', month: 'short' });
}
