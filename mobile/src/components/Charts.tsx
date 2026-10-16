import React from 'react';
import { Text, View } from 'react-native';
import { C, S } from '../theme';

/**
 * Horizontal bar chart for displaying a value between min and max.
 * Supports single color or segmented colors.
 */
export function BarMeter({
  value,
  min = 0,
  max = 100,
  color = C.accent,
  showPercent = true,
  height = 12,
  borderRadius = 6,
}: {
  value: number | null | undefined;
  min?: number;
  max?: number;
  color?: string;
  showPercent?: boolean;
  height?: number;
  borderRadius?: number;
}) {
  if (value == null) {
    return (
      <View style={{ height, borderRadius, backgroundColor: C.border }}>
        <Text style={{ fontSize: 12, color: C.muted }}>—</Text>
      </View>
    );
  }

  const percent = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
  return (
    <View style={{ height, borderRadius, backgroundColor: C.border, overflow: 'hidden' }}>
      <View
        style={{
          width: `${percent}%`,
          height,
          borderRadius,
          backgroundColor: color,
        }}
      />
      {showPercent && (
        <Text
          style={{
            position: 'absolute',
            right: 8,
            top: 0,
            height,
            lineHeight: height,
            fontSize: 11,
            fontWeight: '600',
            color: C.muted,
          }}
        >
          {Math.round(percent)}%
        </Text>
      )}
    </View>
  );
}

/**
 * Segmented gauge with colored bands (like the existing Gauge in DataTab).
 * Shows a marker at the value's position.
 */
export function SegmentedMeter({
  value,
  min,
  max,
  segments,
  height = 12,
  markerHeight = 22,
}: {
  value: number | null;
  min: number;
  max: number;
  segments: [proportion: number, color: string][];
  height?: number;
  markerHeight?: number;
}) {
  const pos = value == null ? null : Math.max(0, Math.min(1, (value - min) / (max - min)));

  return (
    <View style={{ marginTop: S.md, height: markerHeight, justifyContent: 'center' }}>
      <View style={{ flexDirection: 'row', height, borderRadius: height / 2, overflow: 'hidden' }}>
        {segments.map(([f, c], k) => (
          <View key={k} style={{ flex: f, backgroundColor: c }} />
        ))}
      </View>
      {pos != null && (
        <View
          style={{
            position: 'absolute',
            left: `${pos * 100}%`,
            marginLeft: -(markerHeight / 2 - 2),
            width: markerHeight - 4,
            height: markerHeight - 4,
            borderRadius: (markerHeight - 4) / 2,
            backgroundColor: '#fff',
            borderWidth: 3,
            borderColor: C.text,
          }}
        />
      )}
    </View>
  );
}

/**
 * Small horizontal bar with label and optional value.
 * Used for lists of items (e.g., crop scores, soil nutrients).
 */
export function LabeledBar({
  label,
  value,
  min = 0,
  max = 100,
  color = C.accent,
  unit = '',
}: {
  label: string;
  value: number | null | undefined;
  min?: number;
  max?: number;
  color?: string;
  unit?: string;
}) {
  if (value == null) {
    return (
      <View style={{ marginBottom: S.md }}>
        <View style={{ flexDirection: 'row', marginBottom: 6 }}>
          <Text style={{ flex: 1, fontSize: 14, color: C.text }}>{label}</Text>
          <Text style={{ fontSize: 14, fontWeight: '600', color: C.muted }}>—</Text>
        </View>
        <BarMeter value={null} min={min} max={max} color={color} showPercent={false} />
      </View>
    );
  }

  const percent = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
  return (
    <View style={{ marginBottom: S.md }}>
      <View style={{ flexDirection: 'row', marginBottom: 6 }}>
        <Text style={{ flex: 1, fontSize: 14, color: C.text }}>{label}</Text>
        <Text style={{ fontSize: 14, fontWeight: '600', color: C.text }}>
          {Math.round(value * 10) / 10}{unit}
        </Text>
      </View>
      <BarMeter value={value} min={min} max={max} color={color} showPercent={false} height={8} />
    </View>
  );
}

/**
 * Horizontal stacked bar showing the relationship between parts and a whole.
 * Useful for water balance, soil composition, etc.
 */
export function StackedBar({
  segments,
  height = 12,
  label,
}: {
  segments: { value: number; color: string; label?: string }[];
  height?: number;
  label?: string;
}) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  if (total === 0 || segments.length === 0) {
    return (
      <View>
        {label && <Text style={{ fontSize: 13, fontWeight: '600', color: C.muted, marginBottom: 6 }}>{label}</Text>}
        <View style={{ height, borderRadius: height / 2, backgroundColor: C.border }} />
      </View>
    );
  }

  return (
    <View>
      {label && (
        <Text style={{ fontSize: 13, fontWeight: '600', color: C.muted, marginBottom: 6 }}>
          {label}
        </Text>
      )}
      <View style={{ flexDirection: 'row', height, borderRadius: height / 2, overflow: 'hidden' }}>
        {segments.map((seg, k) => (
          <View
            key={k}
            style={{
              flex: seg.value / total,
              backgroundColor: seg.color,
              justifyContent: 'center',
            }}
          />
        ))}
      </View>
      {segments.some(s => s.label) && (
        <View style={{ flexDirection: 'row', marginTop: S.sm, flexWrap: 'wrap' }}>
          {segments.map((seg, k) => seg.label && (
            <View key={k} style={{ flexDirection: 'row', alignItems: 'center', marginRight: S.lg, marginBottom: S.xs }}>
              <View
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: 5,
                  backgroundColor: seg.color,
                  marginRight: S.xs,
                }}
              />
              <Text style={{ fontSize: 12, color: C.muted }}>{seg.label}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}
