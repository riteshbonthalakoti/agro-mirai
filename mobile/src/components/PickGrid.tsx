import React from 'react';
import { Image, Text, TouchableOpacity, View, useWindowDimensions } from 'react-native';
import { Icon, IconName } from '../../icons';
import { feedback } from '../feedback';
import { PICK_IMAGES } from '../pickImages';
import { C, S } from '../theme';

export type PickItem = { key: string; label: string; desc?: string; icon?: IconName; tint?: string };

/** A grid of big picture cards (soil / crop). Uses the generated picture when assets/pick has one,
 *  otherwise a tinted tile with an icon, so the screen looks finished before every image exists. */
export function PickGrid({ prefix, items, selected, onSelect, columns = 2 }: {
  prefix: 'soil' | 'crop'; items: PickItem[]; selected: string | null; onSelect: (key: string | null) => void; columns?: number;
}) {
  const { width } = useWindowDimensions();
  const gap = S.sm;
  const cardW = Math.floor((width - S.lg * 2 - gap * (columns - 1)) / columns);
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap }}>
      {items.map((it) => {
        const on = selected === it.key;
        const img = PICK_IMAGES[`${prefix}_${it.key}`];
        return (
          <TouchableOpacity
            key={it.key}
            activeOpacity={0.85}
            onPress={() => { feedback.select(); onSelect(on ? null : it.key); }}
            accessibilityRole="button"
            accessibilityState={{ selected: on }}
            style={{
              width: cardW, borderRadius: 14, overflow: 'hidden', backgroundColor: '#FFFFFF',
              borderWidth: on ? 1.5 : 1, borderColor: on ? '#2D6A4F' : '#E5E7EB',
              shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: on ? 0.08 : 0.03, shadowRadius: 3, elevation: on ? 2 : 1,
            }}
          >
            <View style={{ width: '100%', height: cardW * (columns > 2 ? 0.85 : 0.7), backgroundColor: it.tint || '#F9FAFB', alignItems: 'center', justifyContent: 'center' }}>
              {img ? (
                <Image source={img} style={{ width: '100%', height: '100%' }} resizeMode="cover" />
              ) : (
                <Icon name={it.icon || 'leaf'} size={columns > 2 ? 26 : 32} color="#2D6A4F" />
              )}
              {on ? (
                <View style={{ position: 'absolute', top: 6, right: 6, width: 22, height: 22, borderRadius: 11, backgroundColor: '#2D6A4F', alignItems: 'center', justifyContent: 'center' }}>
                  <Icon name="check" size={13} color="#fff" />
                </View>
              ) : null}
            </View>
            <View style={{ padding: S.sm, minHeight: it.desc ? 60 : 38 }}>
              <Text style={{ fontSize: columns > 2 ? 13 : 15, fontWeight: on ? '700' : '600', color: on ? '#1B4332' : '#1F2937' }} numberOfLines={2}>{it.label}</Text>
              {it.desc ? <Text style={{ fontSize: 11.5, lineHeight: 16, color: '#6B7280', marginTop: 2 }} numberOfLines={3}>{it.desc}</Text> : null}
            </View>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}
