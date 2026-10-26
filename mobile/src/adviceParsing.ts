/** Pure text parsing, no React Native/UI imports, so it can be unit tested
 *  without pulling in ScanTab's whole component tree (which drags in
 *  lucide-react-native, an ESM-only package Jest can't parse by default).
 *
 *  The server sends one English paragraph: what to do, then optionally
 *  "Other possibilities: ..." and "Note: ...". Split it so each part gets
 *  its own place on screen. */
export function splitAdvice(raw: string): { steps: string[]; others: string[]; note: string } {
  const steps: string[] = [];
  let others: string[] = [];
  let note = '';
  for (const part of raw.split(/\.\s+/)) {
    const s = part.trim().replace(/\.$/, '');
    if (!s) continue;
    // When the source text is already a numbered list ("1. Prune... 2.
    // Apply..."), splitting on ". " also breaks right after each step's own
    // "1", "2", "3" -- leaving orphan steps that are nothing but a bare
    // digit. Drop those, and strip a leading "1. "/"1) " a real step may
    // still carry if its own numbering survived the split intact.
    if (/^\d{1,2}$/.test(s)) continue;
    const clean = s.replace(/^\d{1,2}[.)]\s*/, '');
    if (!clean) continue;
    if (note || clean.startsWith('Note:')) note = `${note ? `${note}. ` : ''}${clean.replace(/^Note:\s*/, '')}`;
    else if (clean.startsWith('Other possibilities:')) others = clean.replace('Other possibilities:', '').split(';').map((x) => x.trim()).filter(Boolean);
    else clean.split(';').forEach((x) => { const y = x.trim(); if (y) steps.push(y.charAt(0).toUpperCase() + y.slice(1)); });
  }
  return { steps, others, note };
}
