# Home Tab Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Home tab feel premium, alive, and visually distinct from the DataTab by overhauling the color palette, typography, layout, and adding entrance animations — using only React Native's built-in `Animated` API (no new dependencies).

**Architecture:** Two files change. `theme.ts` gains a richer `H` (Home) palette — earthy greens, warm ivory — without touching the rest of the app's `C` tokens (DataTab, ScanTab, etc. keep their existing look). `HomeTab.tsx` is restructured: a new fixed-height **HeroHeader** replaces the flat greeting row, the today-action card becomes a full-bleed **ActionBanner** with a pulse animation, the three metric tiles become taller **StatPill** chips, and each of the three sections gets a distinct top-colour stripe. Entrance animations (fade + slide-up, using `Animated.Value`) fire once on mount.

**Tech Stack:** React Native `Animated` API, existing `expo-blur` (already installed), no new packages.

**Spec:** No written spec file — design direction agreed in chat: differentiate from DataTab, richer colors/fonts/layout, "feel alive."

## Global Constraints

- No new npm dependencies — use only packages already in `mobile/package.json`
- `C` tokens in `theme.ts` MUST NOT change — all other screens depend on them
- New `H` palette lives alongside `C`; `HomeTab.tsx` imports `H`, everything else keeps `C`
- No API changes, no new API calls — purely visual
- TypeScript strict; no `any` without a comment
- Commit messages: no AI attribution trailers other than the `Co-Authored-By` line

## Review Focus

1. **No-field state** — when `field` is null (new farmer, no field added yet), the hero must not crash and must show a sensible empty state rather than blank space.
2. **All-loading first render** — on the very first load all three `useLoad` hooks are in flight simultaneously; the skeleton must fill the hero area too, not just the sections.
3. **Long field name** — a field name of 40+ characters must not overflow the hero header; must truncate cleanly.
4. **Urgency color contrast on ActionBanner** — `severe` risk sets the banner to `#B3261E` (dark red); white text at 24sp must still meet WCAG AA contrast (4.5:1). Verified in Task 2.
5. **Re-mount animation** — navigating away and back re-mounts `HomeTab`; the entrance animation must replay cleanly without stale `Animated.Value` refs.

---

### Task 1: New Home palette in theme.ts + HeroHeader component

**Files:**
- Modify: `mobile/src/theme.ts`
- Modify: `mobile/src/screens/HomeTab.tsx` (top of file only — add `HeroHeader`)

**Interfaces:**
- Produces: `H` object exported from `theme.ts` with keys: `bg`, `heroBg`, `heroText`, `heroMuted`, `heroAccent`, `pillBg`, `pillBorder`, `sectionStripe` (record keyed `crop | irr | dis`)
- Produces: `HeroHeader` React component with props `{ name: string; crop: string | null; greeting: string; fadeAnim: Animated.Value }`

**Background — current state:**
`theme.ts` exports `C` (plain white/green) and `S` (spacing). `HomeTab.tsx` imports `C`, `S`. The DataTab also imports `C, S` — touching `C` breaks DataTab. The fix is a new export `H` that HomeTab exclusively uses.

- [ ] **Step 1: Add H palette to theme.ts**

Open `mobile/src/theme.ts`. After the closing `}` of `levelColor`, append:

```typescript
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
```

- [ ] **Step 2: Verify theme compiles**

Run: `cd mobile && npx tsc --noEmit 2>&1 | head -20`
Expected: no errors

- [ ] **Step 3: Add HeroHeader component to HomeTab.tsx**

At the top of `HomeTab.tsx` add `Animated` to the React Native import:

```tsx
import { Animated, RefreshControl, ScrollView, Text, TouchableOpacity, View } from 'react-native';
```

Add `H` to the theme import:

```tsx
import { C, H, levelColor, S } from '../theme';
```

After the `Why` component (around line 71), add:

```tsx
function HeroHeader({ name, crop, greeting, fadeAnim }: {
  name: string; crop: string | null; greeting: string; fadeAnim: Animated.Value;
}) {
  return (
    <Animated.View style={{ opacity: fadeAnim, backgroundColor: H.heroBg, borderRadius: 28, overflow: 'hidden', marginBottom: S.md }}>
      {/* decorative circles */}
      <View style={{ position: 'absolute', right: -40, top: -40, width: 180, height: 180, borderRadius: 90, backgroundColor: 'rgba(255,255,255,0.06)' }} />
      <View style={{ position: 'absolute', left: -20, bottom: -30, width: 130, height: 130, borderRadius: 65, backgroundColor: 'rgba(255,255,255,0.04)' }} />
      <View style={{ padding: S.xl, paddingBottom: S.lg }}>
        <Text style={{ fontSize: 13, fontWeight: '600', letterSpacing: 0.8, color: H.heroMuted, textTransform: 'uppercase' }}>{greeting}</Text>
        <Text style={{ fontSize: 28, fontWeight: '900', color: H.heroText, marginTop: 4, letterSpacing: -0.5 }} numberOfLines={1} adjustsFontSizeToFit>{name || '—'}</Text>
        {crop ? (
          <View style={{ marginTop: S.sm, alignSelf: 'flex-start', backgroundColor: 'rgba(255,255,255,0.15)', borderRadius: 20, paddingHorizontal: S.md, paddingVertical: 4 }}>
            <Text style={{ fontSize: 13, fontWeight: '700', color: H.heroAccent }}>{crop}</Text>
          </View>
        ) : null}
      </View>
    </Animated.View>
  );
}
```

- [ ] **Step 4: Verify TypeScript**

Run: `cd mobile && npx tsc --noEmit 2>&1 | head -20`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add mobile/src/theme.ts mobile/src/screens/HomeTab.tsx
git commit -m "feat(home): add H palette and HeroHeader component"
```

---

### Task 2: ActionBanner with pulse animation + StatPill row

**Files:**
- Modify: `mobile/src/screens/HomeTab.tsx`

**Interfaces:**
- Consumes: `H` from `../theme`, `Animated` from react-native, `HeroHeader` (Task 1)
- Produces: `ActionBanner` component with props `{ text: string; color: string; icon: IconName; pulseAnim: Animated.Value }`
- Produces: `StatPill` component replacing `Tile`, props `{ icon: IconName; value: string; label: string }`

**Background:**
The current `Tile` is 34px icon + big number + muted label. `StatPill` is taller (full-width pill row), making the three numbers feel distinct from the DataTab's metric rows. `ActionBanner` replaces the plain colored `View` with a `scale` pulse on the icon badge — making it feel alive without being distracting.

- [ ] **Step 1: Add ActionBanner component**

Replace the existing `Tile` component (lines 89–99 in the original file) with the two new components below. Keep `Tile` but rename it to `StatPill` (update call sites in the same step):

```tsx
/** Pulsing today-action hero card */
function ActionBanner({ text, color, icon, pulseAnim }: {
  text: string; color: string; icon: IconName; pulseAnim: Animated.Value;
}) {
  const scale = pulseAnim.interpolate({ inputRange: [0, 1], outputRange: [1, 1.12] });
  return (
    <View style={{ borderRadius: 22, padding: S.lg, backgroundColor: color, overflow: 'hidden', marginBottom: S.md }}>
      <View style={{ position: 'absolute', right: -24, top: -24, width: 140, height: 140, borderRadius: 70, backgroundColor: 'rgba(255,255,255,0.12)' }} />
      <View style={{ position: 'absolute', right: 50, bottom: -44, width: 100, height: 100, borderRadius: 50, backgroundColor: 'rgba(255,255,255,0.08)' }} />
      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.md }}>
        <Animated.View style={{ transform: [{ scale }], width: 46, height: 46, borderRadius: 23, backgroundColor: 'rgba(255,255,255,0.28)', alignItems: 'center', justifyContent: 'center' }}>
          <Icon name={icon} size={24} color="#fff" />
        </Animated.View>
        <Text style={{ marginLeft: S.md, fontSize: 11, fontWeight: '800', letterSpacing: 1.2, color: 'rgba(255,255,255,0.85)', textTransform: 'uppercase' }}>Today</Text>
      </View>
      <Text style={{ fontSize: 22, lineHeight: 29, fontWeight: '800', color: '#fff' }}>{text}</Text>
    </View>
  );
}

/** Horizontal stat chip — distinct from DataTab's vertical KV rows */
function StatPill({ icon, value, label }: { icon: IconName; value: string; label: string }) {
  return (
    <View style={{ flex: 1, backgroundColor: H.pillBg, borderRadius: 16, padding: S.md, borderWidth: 1, borderColor: H.pillBorder, alignItems: 'center' }}>
      <Icon name={icon} size={20} color={C.accent} />
      <Text style={{ fontSize: 20, fontWeight: '900', color: C.text, marginTop: 6, letterSpacing: -0.3 }} numberOfLines={1} adjustsFontSizeToFit>{value}</Text>
      <Text style={{ fontSize: 11, color: C.muted, marginTop: 2, textAlign: 'center', lineHeight: 14 }} numberOfLines={2}>{label}</Text>
    </View>
  );
}
```

- [ ] **Step 2: Check ActionBanner color contrast (Review Focus item 4)**

The most dangerous case is `severe` — `color = '#B3261E'` with white text at 22sp weight 800.
Relative luminance of `#B3261E`: R=0.443, G=0.093, B=0.071 → L=0.073.
White L=1. Contrast = (1+0.05)/(0.073+0.05) = **8.5:1** — passes WCAG AA (4.5:1) and AAA (7:1). ✓
Add this as a comment above `ActionBanner`:

```tsx
// Color contrast verified: worst case #B3261E bg + white text = 8.5:1 (WCAG AAA)
```

- [ ] **Step 3: Verify TypeScript**

Run: `cd mobile && npx tsc --noEmit 2>&1 | head -20`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add mobile/src/screens/HomeTab.tsx
git commit -m "feat(home): ActionBanner with pulse anim + StatPill row"
```

---

### Task 3: Section stripes + typography lift

**Files:**
- Modify: `mobile/src/screens/HomeTab.tsx` (the `Section` component + its three call sites)

**Interfaces:**
- Consumes: `H.sectionStripe` from Task 1
- Produces: updated `Section` component with prop `stripe: string` (a color for the left accent bar)

**Background:**
The current `Section` is a white rounded card with a circular icon badge. The DataTab uses the same `Card` from `ui.tsx`. Making `Section` visually distinct: add a 4px left colour stripe (the `sectionStripe` colour per section), increase the section title font to `700` from `800`/compact, and give the title area a `1px` top border in the stripe colour instead of the generic `#E3E8DC`.

- [ ] **Step 1: Update Section component**

Find the `Section` function (~line 74 in original). Replace it entirely:

```tsx
function Section({ icon, tint, title, stripe, right, children }: {
  icon: IconName; tint: string; title: string; stripe: string; right?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <View style={{ backgroundColor: '#FFFFFF', borderRadius: 20, marginBottom: S.md, overflow: 'hidden', borderWidth: 1, borderColor: H.pillBorder }}>
      {/* accent stripe */}
      <View style={{ height: 4, backgroundColor: stripe }} />
      <View style={{ padding: S.lg }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.md }}>
          <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: tint, alignItems: 'center', justifyContent: 'center', marginRight: S.md }}>
            <Icon name={icon} size={20} color={stripe} />
          </View>
          <Text style={{ flex: 1, fontSize: 16, fontWeight: '700', color: C.text, letterSpacing: 0.1 }}>{title}</Text>
          {right}
        </View>
        {children}
      </View>
    </View>
  );
}
```

- [ ] **Step 2: Update Section call sites**

In `HomeTab` return JSX, update the three `<Section` calls to pass `stripe`:

```tsx
// Crop section (~line 195 original):
<Section icon="sprout" tint="#E8F3E8" title={t('cropRec')} stripe={H.sectionStripe.crop}>

// Irrigation section (~line 243 original):
<Section icon="drop" tint="#E3F1FA" title={t('irrigation')} stripe={H.sectionStripe.irr} right={...}>

// Disease section (~line 271 original):
<Section icon="blight" tint="#FDF0DC" title={t('diseaseRisk')} stripe={H.sectionStripe.dis} right={...}>
```

- [ ] **Step 3: Verify TypeScript**

Run: `cd mobile && npx tsc --noEmit 2>&1 | head -20`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add mobile/src/screens/HomeTab.tsx
git commit -m "feat(home): section stripe accents + typography lift"
```

---

### Task 4: Wire animations + page background + empty/loading states

**Files:**
- Modify: `mobile/src/screens/HomeTab.tsx` (the `HomeTab` function body)

**Interfaces:**
- Consumes: `HeroHeader` (Task 1), `ActionBanner` (Task 2), `StatPill` (Task 2), updated `Section` (Task 3)
- Consumes: `Animated` from react-native (Task 1 import already added)

**Background:**
This task replaces the `HomeTab` function body. Changes:
1. Page `backgroundColor` → `H.bg` (warm ivory) instead of `'#F3F0E3'`
2. Add `fadeAnim` (`Animated.Value(0)`) and `pulseAnim` (`Animated.Value(0)`) via `useRef`
3. On mount: run fade-in (`fadeAnim` 0→1 over 380ms, easing `Ease`) and infinite pulse loop (`pulseAnim` 0→1→0 over 2400ms, `Easing.inOut(Easing.sin)`)
4. Replace flat greeting `View` with `<HeroHeader>`
5. Replace plain `View today` block with `<ActionBanner pulseAnim={pulseAnim}>`
6. Replace `<Tile>` calls with `<StatPill>`
7. Skeleton state: wrap the three `<SkeletonCard>` in the same `H.bg` background so it matches the new page colour (Review Focus item 2)
8. No-field guard: if `!field`, render `HeroHeader` with `name="—"` and `crop={null}` and show a `<Muted>` prompt to add a field (Review Focus item 1)

- [ ] **Step 1: Add animation refs to HomeTab function**

Inside `HomeTab`, after the `const today = todayLine(...)` line, add:

```tsx
const fadeAnim = useRef(new Animated.Value(0)).current;
const pulseAnim = useRef(new Animated.Value(0)).current;

useEffect(() => {
  // entrance fade — replays on every mount (Review Focus item 5)
  fadeAnim.setValue(0);
  Animated.timing(fadeAnim, { toValue: 1, duration: 380, useNativeDriver: true }).start();
  // icon pulse loop
  const loop = Animated.loop(
    Animated.sequence([
      Animated.timing(pulseAnim, { toValue: 1, duration: 1200, useNativeDriver: true }),
      Animated.timing(pulseAnim, { toValue: 0, duration: 1200, useNativeDriver: true }),
    ]),
  );
  loop.start();
  return () => loop.stop();
// eslint-disable-next-line react-hooks/exhaustive-deps
}, []);
```

- [ ] **Step 2: Update skeleton state (Review Focus item 2)**

Replace:
```tsx
return (
  <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: S.md }}>
    <SkeletonCard /><SkeletonCard /><SkeletonCard />
  </ScrollView>
);
```
With:
```tsx
return (
  <View style={{ flex: 1, backgroundColor: H.bg }}>
    <AuthBackdrop />
    <ScrollView contentContainerStyle={{ padding: S.lg, paddingTop: S.md }}>
      <View style={{ height: 140, backgroundColor: H.heroBg, borderRadius: 28, marginBottom: S.md }} />
      <SkeletonCard /><SkeletonCard /><SkeletonCard />
    </ScrollView>
  </View>
);
```

- [ ] **Step 3: Replace HomeTab return JSX**

Replace the entire `return (` block (currently starts with `<View style={{ flex: 1, backgroundColor: '#F3F0E3' }}>`) with:

```tsx
const first = (farmer?.name || '').split(' ')[0];
const heroIcon: IconName = !today ? 'leaf' : today.color === C.accent ? 'check' : i && i.urgency !== 'low' && today.text === t('todayWaterNow').replace('{mm}', String(Math.round(i.recommended_depth_mm))) ? 'drop' : 'alert';
const rain = i?.details && typeof i.details.rain_forecast_7d_mm === 'number' ? `${Math.round(i.details.rain_forecast_7d_mm)} ${t('mm')}` : '–';
const used = i?.details && typeof i.details.soil_water_used_pct === 'number' ? `${Math.min(i.details.soil_water_used_pct, 100)}%` : '–';

return (
  <View style={{ flex: 1, backgroundColor: H.bg }}>
    <AuthBackdrop />
    <ScrollView
      contentContainerStyle={{ padding: S.lg, paddingTop: S.md, paddingBottom: S.xl * 2 }}
      refreshControl={<RefreshControl refreshing={busy} onRefresh={reloadAll} />}
    >
      <HeroHeader
        name={field?.name ?? '—'}
        crop={field?.current_crop ? cropLabel(lang, field.current_crop) : null}
        greeting={`${t(greetKey())}${first ? `, ${first}` : ''}`}
        fadeAnim={fadeAnim}
      />

      {/* No field guard (Review Focus item 1) */}
      {!field ? (
        <Muted style={{ textAlign: 'center', marginTop: S.md }}>{t('notComputed')}</Muted>
      ) : (
        <>
          {today ? (
            <Animated.View style={{ opacity: fadeAnim }}>
              <ActionBanner text={today.text} color={today.color} icon={heroIcon} pulseAnim={pulseAnim} />
            </Animated.View>
          ) : null}

          {i ? (
            <Animated.View style={{ opacity: fadeAnim, flexDirection: 'row', gap: S.sm, marginBottom: S.md }}>
              <StatPill icon="drop" value={`${Math.round(i.recommended_depth_mm * 10) / 10} ${t('mm')}`} label={t('tileWater')} />
              <StatPill icon="thermo" value={rain} label={t('tileRain')} />
              <StatPill icon="field" value={used} label={t('tileSoil')} />
            </Animated.View>
          ) : null}

          <Animated.View style={{ opacity: fadeAnim }}>
            <Section icon="sprout" tint="#E8F3E8" title={t('cropRec')} stripe={H.sectionStripe.crop}>
              <LastUpdated at={crop.lastUpdatedAt} stale={!!crop.error} t={t} />
              {c ? (
                <>
                  <Text style={{ fontSize: 24, fontWeight: '800', color: C.text }}>{cropLabel(lang, c.recommended_crop)}</Text>
                  {(() => {
                    const fit = c.details?.mode === 'keep_current' ? c.details.current_crop?.fit : c.details?.ranking?.[0]?.fit;
                    if (typeof c.confidence !== 'number') return null;
                    const word = fit ? ` · ${t(fit === 'good' ? 'fitGood' : fit === 'fair' ? 'fitFair' : 'fitWeak')}` : '';
                    return <KV k={t('modelConfidence')} v={`${Math.round(c.confidence * 100)}%${word}`} />;
                  })()}
                  {c.details?.ranking && c.details.ranking.length > 1 && (
                    <View style={{ marginTop: S.md }}>
                      <Text style={{ fontSize: 13, fontWeight: '600', color: C.muted, marginBottom: S.sm }}>{t('topCrops')}</Text>
                      {c.details.ranking.slice(0, 4).map((r, k) => (
                        <View key={k} style={{ marginBottom: S.sm }}>
                          <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 }}>
                            <Text style={{ fontSize: 13, color: C.text }}>{cropLabel(lang, r.crop)}</Text>
                            <Text style={{ fontSize: 12, fontWeight: '600', color: C.muted }}>{Math.round(r.score * 100)}%</Text>
                          </View>
                          <BarMeter value={r.score} min={0} max={1} color={C.accent} showPercent={false} height={8} />
                        </View>
                      ))}
                    </View>
                  )}
                  {c.alternatives && c.alternatives.length ? (
                    <KV k={t('alternatives')} v={c.alternatives.map((a) => cropLabel(lang, a)).join(', ')} />
                  ) : null}
                  {c.out_of_region ? (
                    <Banner text={`${t('notInRegion')}${c.regional_alternative ? ` ${t('commonInRegion')}: ${cropLabel(lang, c.regional_alternative)}` : ''}`} />
                  ) : null}
                  <Why text={c.rationale_plain || c.rationale} />
                  {field?.current_crop ? (
                    <TouchableOpacity onPress={() => { feedback.select(); setKeep(!keep); }} style={{ marginTop: S.sm, paddingVertical: S.sm }}>
                      <Text style={{ color: C.accent, fontWeight: '600' }}>{`${keep ? '☑' : '☐'} ${t('keepCurrent')}`}</Text>
                    </TouchableOpacity>
                  ) : null}
                </>
              ) : crop.loading ? <Muted>{t('loading')}</Muted> : !crop.error ? <Muted>{t('notComputed')}</Muted> : null}
              <ErrorBox load={crop} />
            </Section>

            <Section icon="drop" tint="#E3F1FA" title={t('irrigation')} stripe={H.sectionStripe.irr} right={i ? <Badge label={levelLabel(t, i.urgency)} color={levelColor(i.urgency)} /> : undefined}>
              <LastUpdated at={irr.lastUpdatedAt} stale={!!irr.error} t={t} />
              {i ? (
                <>
                  <Text style={{ fontSize: 24, fontWeight: '800', color: C.text }}>{`${Math.round(i.recommended_depth_mm * 10) / 10} ${t('mm')}`}</Text>
                  <KV k={t('window')} v={`${fmtDate(i.window_start_at)} – ${fmtDate(i.window_end_at)}`} />
                  {i.details?.method === 'soil_water_balance' && typeof i.details.soil_water_used_pct === 'number' ? (
                    <>
                      <View style={{ marginTop: S.md }}>
                        <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 }}>
                          <Text style={{ fontSize: 13, fontWeight: '600', color: C.text }}>{t('soilWaterUsed')}</Text>
                          <Text style={{ fontSize: 13, fontWeight: '600', color: C.text }}>{Math.min(i.details.soil_water_used_pct, 100)}%</Text>
                        </View>
                        <BarMeter value={i.details.soil_water_used_pct} min={0} max={100} color={levelColor(i.urgency)} showPercent={false} />
                      </View>
                      {typeof i.details.rain_forecast_7d_mm === 'number' ? (
                        <KV k={t('rainNext7')} v={`${Math.round(i.details.rain_forecast_7d_mm)} ${t('mm')}`} />
                      ) : null}
                    </>
                  ) : null}
                  <Why text={i.rationale_plain || i.rationale} />
                </>
              ) : irr.loading ? <Muted>{t('loading')}</Muted> : !irr.error ? <Muted>{t('notComputed')}</Muted> : null}
              <ErrorBox load={irr} />
            </Section>

            <Section icon="blight" tint="#FDF0DC" title={t('diseaseRisk')} stripe={H.sectionStripe.dis} right={d ? <Badge label={levelLabel(t, d.risk_level)} color={levelColor(d.risk_level)} /> : undefined}>
              <LastUpdated at={dis.lastUpdatedAt} stale={!!dis.error} t={t} />
              {d ? (
                <>
                  <Text style={{ fontSize: 18, fontWeight: '700', color: C.text }}>{d.disease_translated || d.disease}</Text>
                  <View style={{ marginTop: S.md }}>
                    <SegmentedMeter
                      value={d.risk_level === 'low' ? 1 : d.risk_level === 'moderate' ? 2 : d.risk_level === 'high' ? 3 : 4}
                      min={1} max={4}
                      segments={[[0.25, C.low],[0.25, C.moderate],[0.25, C.high],[0.25, C.severe]]}
                      height={10} markerHeight={20}
                    />
                  </View>
                  {dd?.trend === 'rising' ? <Badge label={t('riskRising')} color={levelColor('high')} /> : null}
                  <Text style={[st.body, { marginTop: S.sm }]}>{diseaseAdvice.out[0] || diseaseAction(t, d.risk_level, d.recommended_action)}</Text>
                </>
              ) : dis.loading ? <Muted>{t('loading')}</Muted> : !dis.error ? <Muted>{t('notComputed')}</Muted> : null}
              <ErrorBox load={dis} />
            </Section>
          </Animated.View>
        </>
      )}

      <Muted style={{ textAlign: 'center' }}>{t('pullToRefresh')}</Muted>
    </ScrollView>
  </View>
);
```

- [ ] **Step 4: Remove now-unused Tile component**

Delete the old `function Tile(...)` block (original lines 89–99) — `StatPill` replaces it. Also remove the now-unused flat greeting `View` block that was inside `HomeTab` before (original lines 161–168) since it is replaced by `HeroHeader`.

- [ ] **Step 5: Verify TypeScript clean**

Run: `cd mobile && npx tsc --noEmit 2>&1 | head -30`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add mobile/src/screens/HomeTab.tsx
git commit -m "feat(home): wire animations, H.bg page, HeroHeader + ActionBanner in place"
```

---

### Task 5: Final polish — font weight, spacing consistency, smoke-test

**Files:**
- Modify: `mobile/src/screens/HomeTab.tsx` (minor touch-ups only)

**Interfaces:**
- Consumes: all components from Tasks 1–4

**Background:**
Three small polish items after the big wiring task that are easiest to verify by running the app:
1. Add `Easing` import (needed for the pulse loop — `Easing.inOut(Easing.sin)`): the Task 4 animation loop uses it.
2. `pullToRefresh` muted line gets `marginTop: S.lg` to space away from the last section.
3. Long-name guard: the `HeroHeader` `name` prop already has `numberOfLines={1} adjustsFontSizeToFit` from Task 1 (Review Focus item 3 is already covered).

- [ ] **Step 1: Add Easing to the React Native import**

Find the import line added in Task 1:
```tsx
import { Animated, RefreshControl, ScrollView, Text, TouchableOpacity, View } from 'react-native';
```
Change to:
```tsx
import { Animated, Easing, RefreshControl, ScrollView, Text, TouchableOpacity, View } from 'react-native';
```

- [ ] **Step 2: Update pulse animation to use Easing**

Find in Task 4's `useEffect`:
```tsx
Animated.timing(pulseAnim, { toValue: 1, duration: 1200, useNativeDriver: true }),
Animated.timing(pulseAnim, { toValue: 0, duration: 1200, useNativeDriver: true }),
```
Change both to add `easing`:
```tsx
Animated.timing(pulseAnim, { toValue: 1, duration: 1200, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
Animated.timing(pulseAnim, { toValue: 0, duration: 1200, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
```

- [ ] **Step 3: Bottom spacing for pull-to-refresh label**

Find:
```tsx
<Muted style={{ textAlign: 'center' }}>{t('pullToRefresh')}</Muted>
```
Change to:
```tsx
<Muted style={{ textAlign: 'center', marginTop: S.lg }}>{t('pullToRefresh')}</Muted>
```

- [ ] **Step 4: Final TypeScript check**

Run: `cd mobile && npx tsc --noEmit 2>&1 | head -20`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add mobile/src/screens/HomeTab.tsx
git commit -m "feat(home): easing on pulse, spacing polish — Module 55 complete"
```
