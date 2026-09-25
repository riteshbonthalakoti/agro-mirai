import React from 'react';
import { feedback } from './feedback';
import { ActivityIndicator, StyleSheet, Text, TextInput, TextInputProps, TouchableOpacity, View, ViewStyle } from 'react-native';
import { C, S } from './theme';

export function Btn({ label, onPress, kind = 'primary', disabled, busy, style }: {
  label: string; onPress: () => void; kind?: 'primary' | 'secondary' | 'danger'; disabled?: boolean; busy?: boolean; style?: ViewStyle;
}) {
  const bg = kind === 'primary' ? C.accent : 'transparent';
  const fg = kind === 'primary' ? C.accentText : kind === 'danger' ? C.danger : C.accent;
  return (
    <TouchableOpacity
      onPress={() => { feedback.tap(); onPress(); }}
      disabled={disabled || busy}
      style={[st.btn, { backgroundColor: bg, borderColor: kind === 'primary' ? C.accent : C.border, opacity: disabled ? 0.5 : 1 }, style]}
    >
      {busy ? <ActivityIndicator color={fg} /> : <Text style={[st.btnText, { color: fg }]}>{label}</Text>}
    </TouchableOpacity>
  );
}

export function Card({ title, children, right }: { title?: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <View style={st.card}>
      {title ? (
        <View style={st.cardHead}>
          <Text style={st.cardTitle}>{title}</Text>
          {right}
        </View>
      ) : null}
      {children}
    </View>
  );
}

export function KV({ k, v, color }: { k: string; v: string | number | null | undefined; color?: string }) {
  return (
    <View style={st.kv}>
      <Text style={st.k}>{k}</Text>
      <Text style={[st.v, color ? { color } : null]}>{v === null || v === undefined || v === '' ? '—' : String(v)}</Text>
    </View>
  );
}

export function Label({ children }: { children: React.ReactNode }) {
  return <Text style={st.label}>{children}</Text>;
}

export function Input(props: TextInputProps) {
  return <TextInput placeholderTextColor={C.muted} {...props} style={[st.input, props.style]} />;
}

export function Muted({ children, style }: { children: React.ReactNode; style?: any }) {
  return <Text style={[st.muted, style]}>{children}</Text>;
}

export function Banner({ text, kind = 'info' }: { text: string; kind?: 'info' | 'error' | 'ok' }) {
  const color = kind === 'error' ? C.danger : kind === 'ok' ? C.accent : C.warn;
  return (
    <View style={[st.banner, { borderColor: color }]}>
      <Text style={{ color, fontSize: 13 }}>{text}</Text>
    </View>
  );
}

export function Chip({ label, selected, onPress }: { label: string; selected?: boolean; onPress: () => void }) {
  return (
    <TouchableOpacity onPress={() => { feedback.select(); onPress(); }} style={[st.chip, selected && { backgroundColor: C.accent, borderColor: C.accent }]}>
      <Text style={{ color: selected ? C.accentText : C.text, fontSize: 13 }}>{label}</Text>
    </TouchableOpacity>
  );
}

export function Badge({ label, color }: { label: string; color: string }) {
  return (
    <View style={[st.badge, { borderColor: color }]}>
      <Text style={{ color, fontSize: 12, fontWeight: '600' }}>{label}</Text>
    </View>
  );
}

export const st = StyleSheet.create({
  btn: { borderWidth: 1, borderRadius: 8, paddingVertical: 12, paddingHorizontal: S.lg, alignItems: 'center', justifyContent: 'center', minHeight: 44 },
  btnText: { fontSize: 15, fontWeight: '600' },
  card: { borderWidth: 1, borderColor: C.border, borderRadius: 10, padding: S.lg, marginBottom: S.md, backgroundColor: C.bg },
  cardHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: S.sm },
  cardTitle: { fontSize: 16, fontWeight: '700', color: C.text },
  kv: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4, gap: S.md },
  k: { color: C.muted, fontSize: 14, flexShrink: 1 },
  v: { color: C.text, fontSize: 14, fontWeight: '600', flexShrink: 1, textAlign: 'right' },
  label: { color: C.muted, fontSize: 13, marginTop: S.md, marginBottom: 4 },
  input: { borderWidth: 1, borderColor: C.border, borderRadius: 8, paddingHorizontal: S.md, paddingVertical: 10, fontSize: 16, color: C.text, backgroundColor: C.bg },
  muted: { color: C.muted, fontSize: 13 },
  banner: { borderWidth: 1, borderRadius: 8, padding: S.md, marginBottom: S.md, backgroundColor: C.surface },
  chip: { borderWidth: 1, borderColor: C.border, borderRadius: 16, paddingHorizontal: S.md, paddingVertical: 6, marginRight: S.sm, marginBottom: S.sm },
  badge: { borderWidth: 1, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2 },
  h1: { fontSize: 22, fontWeight: '700', color: C.text, marginBottom: S.sm },
  body: { fontSize: 14, color: C.text, lineHeight: 20 },
});
