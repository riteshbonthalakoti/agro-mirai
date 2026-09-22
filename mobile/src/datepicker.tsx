import React, { useState } from 'react';
import { Modal, Text, TouchableOpacity, View } from 'react-native';
import { Icon } from '../icons';
import { C, S } from './theme';
import { Btn } from './ui';

const toIso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const parseIso = (s: string) => {
  const d = /^\d{4}-\d{2}-\d{2}$/.test(s) ? new Date(s + 'T00:00:00') : new Date();
  return isNaN(d.getTime()) ? new Date() : d;
};
const sameDay = (a: Date, b: Date) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const WEEKDAY_LETTERS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

/** Own-themed calendar, not the OS default: a month grid you tap through,
 *  matching the app's plain visual language instead of the native Android
 *  Material dialog / iOS spinner. */
function CalendarGrid({ value, maxDate, onPick }: { value: Date; maxDate?: Date; onPick: (d: Date) => void }) {
  const [cursor, setCursor] = useState(new Date(value.getFullYear(), value.getMonth(), 1));
  const today = new Date();

  const daysInMonth = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();
  const firstWeekday = new Date(cursor.getFullYear(), cursor.getMonth(), 1).getDay();
  const cells: (number | null)[] = [...Array(firstWeekday).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)];

  const atMax = maxDate && cursor.getFullYear() === maxDate.getFullYear() && cursor.getMonth() === maxDate.getMonth();
  const canGoNext = !maxDate || cursor.getFullYear() < maxDate.getFullYear() || (cursor.getFullYear() === maxDate.getFullYear() && cursor.getMonth() < maxDate.getMonth());

  return (
    <View>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: S.md }}>
        <TouchableOpacity onPress={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }} style={{ padding: 6 }}>
          <Icon name="chevron-back" size={20} color={C.text} />
        </TouchableOpacity>
        <Text style={{ fontSize: 16, fontWeight: '700', color: C.text }}>{MONTH_NAMES[cursor.getMonth()]} {cursor.getFullYear()}</Text>
        <TouchableOpacity
          onPress={() => canGoNext && setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}
          disabled={!canGoNext}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          style={{ padding: 6, opacity: canGoNext ? 1 : 0.25 }}
        >
          <Icon name="chevron-right" size={20} color={C.text} />
        </TouchableOpacity>
      </View>
      <View style={{ flexDirection: 'row' }}>
        {WEEKDAY_LETTERS.map((d, i) => (
          <Text key={i} style={{ flex: 1, textAlign: 'center', fontSize: 12, fontWeight: '700', color: C.muted, marginBottom: S.sm }}>{d}</Text>
        ))}
      </View>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
        {cells.map((day, i) => {
          if (day === null) return <View key={i} style={{ width: `${100 / 7}%`, aspectRatio: 1 }} />;
          const cellDate = new Date(cursor.getFullYear(), cursor.getMonth(), day);
          const disabled = !!maxDate && cellDate > maxDate;
          const isSelected = sameDay(cellDate, value);
          const isToday = sameDay(cellDate, today);
          return (
            <View key={i} style={{ width: `${100 / 7}%`, aspectRatio: 1, alignItems: 'center', justifyContent: 'center' }}>
              <TouchableOpacity
                onPress={() => !disabled && onPick(cellDate)}
                disabled={disabled}
                style={{
                  width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center',
                  backgroundColor: isSelected ? C.accent : 'transparent',
                  borderWidth: isToday && !isSelected ? 1.5 : 0, borderColor: C.accent,
                }}
              >
                <Text style={{ fontSize: 14, color: isSelected ? C.accentText : disabled ? C.border : C.text, fontWeight: isSelected || isToday ? '700' : '400' }}>{day}</Text>
              </TouchableOpacity>
            </View>
          );
        })}
      </View>
    </View>
  );
}

/** App-themed tappable date field: shows the date like a normal form row,
 *  opens our own calendar sheet (not the OS picker) on tap. */
export function DateField({ value, onChange, maxDate, locale, doneLabel = 'Done', todayLabel = 'Today' }: {
  value: string; onChange: (iso: string) => void; maxDate?: Date; locale: string; doneLabel?: string; todayLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(parseIso(value));

  const openSheet = () => { setDraft(parseIso(value)); setOpen(true); };
  const confirm = () => { onChange(toIso(draft)); setOpen(false); };

  const fmtNice = (s: string) => parseIso(s).toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric' });

  return (
    <>
      <TouchableOpacity
        onPress={openSheet}
        style={{
          flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
          borderWidth: 1, borderColor: C.border, borderRadius: 10,
          paddingHorizontal: S.md, paddingVertical: 12, backgroundColor: C.bg,
        }}
      >
        <Text style={{ fontSize: 16, color: C.text, fontWeight: '600' }}>{fmtNice(value)}</Text>
        <Icon name="chevron-down" size={18} color={C.muted} />
      </TouchableOpacity>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <TouchableOpacity activeOpacity={1} onPress={() => setOpen(false)} style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', padding: S.xl }}>
          <TouchableOpacity activeOpacity={1} onPress={() => {}} style={{ backgroundColor: C.bg, borderRadius: 18, padding: S.lg }}>
            <CalendarGrid value={draft} maxDate={maxDate} onPick={setDraft} />
            <View style={{ flexDirection: 'row', gap: S.sm, marginTop: S.md }}>
              <Btn label={todayLabel} kind="secondary" onPress={() => setDraft(maxDate && maxDate < new Date() ? maxDate : new Date())} style={{ flex: 1 }} />
              <Btn label={doneLabel} onPress={confirm} style={{ flex: 1 }} />
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>
    </>
  );
}
