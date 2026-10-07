// Deliberately plain: white background, one green accent, system font, thin
// borders, no gradients/shadows/custom fonts. (Ritesh's Module 39 feedback:
// the old UI was over-designed; this is the minimal replacement.)
export const C = {
  bg: '#FFFFFF',
  surface: '#F5F6F3',
  border: '#DDE1D9',
  text: '#1A1D19',
  muted: '#666D64',
  accent: '#2E7D32',
  accentText: '#FFFFFF',
  danger: '#B3261E',
  warn: '#9A5B00',
  low: '#2E7D32',
  moderate: '#9A5B00',
  high: '#C24E00',
  severe: '#B3261E',
};

export const S = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 };

export function levelColor(level?: string | null): string {
  switch ((level || '').toLowerCase()) {
    case 'low': return C.low;
    case 'moderate': return C.moderate;
    case 'high': return C.high;
    case 'severe': return C.severe;
    default: return C.muted;
  }
}

/** Home-tab-exclusive palette. No other screen should import this. */
export const H = {
  bg:           '#F5F0E8',   // warm ivory page background
  heroBg:       '#1B4332',   // deep forest green hero
  heroText:     '#FFFFFF',
  heroMuted:    'rgba(255,255,255,0.65)',
  heroAccent:   '#74C69D',   // mint highlight inside hero
  pillBg:       '#FFFFFF',
  pillBorder:   '#D8E6D0',
  sectionStripe: {
    crop: '#74C69D',   // mint green
    irr:  '#4FC3F7',   // sky blue
    dis:  '#FFB74D',   // amber
  } as Record<string, string>,
};
