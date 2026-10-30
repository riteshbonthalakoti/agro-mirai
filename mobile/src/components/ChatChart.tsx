import React, { useState } from 'react';
import { LayoutChangeEvent, Text, View, useWindowDimensions } from 'react-native';
import Svg, { Circle, Line, Polyline, Rect } from 'react-native-svg';
import { ChatChart as ChatChartData } from '../api';
import { C, S } from '../theme';

const CHART_H = 140;
const PAD = 24;

/** Plain bar/line chart rendered client-side from the model's structured
 * chart block (Module 58) -- the free-tier text models can't generate
 * images, so the system prompt asks for {type, labels, values} JSON and
 * this renders it, same custom-SVG approach as Charts.tsx's meters. Width
 * tracks the chat bubble's own layout (via onLayout) rather than a fixed
 * px value, so it fits any phone or tablet width without overflowing or
 * looking stranded on a wide screen. */
export function ChatChart({ chart }: { chart: ChatChartData }) {
  const { width: winW } = useWindowDimensions();
  const [chartW, setChartW] = useState(() => Math.round(Math.min(winW * 0.78, 320)));
  const onLayout = (e: LayoutChangeEvent) => {
    // layout.width is the View's border-box; subtract its own horizontal
    // padding so the Svg matches the actual content width, not the padded box.
    const w = Math.round(e.nativeEvent.layout.width) - S.sm * 2;
    if (w > 0 && w !== chartW) setChartW(w);
  };

  const values = chart.values;
  if (!values.length) return null;
  const max = Math.max(...values, 0);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const innerW = chartW - PAD * 2;
  const innerH = CHART_H - PAD * 2;
  const n = values.length;
  const x = (i: number) => PAD + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW);
  const y = (v: number) => PAD + innerH - ((v - min) / range) * innerH;

  return (
    <View onLayout={onLayout} style={{ backgroundColor: '#fff', borderRadius: 16, padding: S.sm, marginTop: S.sm, borderWidth: 1, borderColor: C.border }}>
      {chart.title ? <Text style={{ fontSize: 12.5, fontWeight: '700', color: C.text, marginBottom: 4 }}>{chart.title}</Text> : null}
      <Svg width={chartW} height={CHART_H}>
        <Line x1={PAD} y1={CHART_H - PAD} x2={chartW - PAD} y2={CHART_H - PAD} stroke={C.border} strokeWidth={1} />
        {chart.type === 'line' ? (
          <>
            <Polyline
              points={values.map((v, i) => `${x(i)},${y(v)}`).join(' ')}
              fill="none"
              stroke={C.accent}
              strokeWidth={2.5}
            />
            {values.map((v, i) => (
              <Circle key={i} cx={x(i)} cy={y(v)} r={3.5} fill={C.accent} />
            ))}
          </>
        ) : (
          values.map((v, i) => {
            const barW = Math.max(8, innerW / n - 10);
            const barX = x(i) - barW / 2;
            const barY = Math.min(y(v), y(0));
            const barH = Math.max(1, Math.abs(y(v) - y(0)));
            return <Rect key={i} x={barX} y={barY} width={barW} height={barH} rx={3} fill={C.accent} />;
          })
        )}
      </Svg>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 2, paddingHorizontal: PAD - 8 }}>
        {chart.labels.map((l, i) => (
          <Text key={i} numberOfLines={1} style={{ fontSize: 10, color: C.muted, maxWidth: chartW / n }}>{l}</Text>
        ))}
      </View>
    </View>
  );
}
