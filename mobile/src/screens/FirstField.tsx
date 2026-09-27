import React from 'react';
import { ImageBackground, ScrollView, Text, TouchableOpacity, View, useWindowDimensions } from 'react-native';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';
import { Icon, IconName } from '../../icons';
import { feedback } from '../feedback';
import { C, S } from '../theme';

/** Shown once a farmer has signed in but has no field yet. Full-screen: a sharp paddy-field photo with the
 *  greeting on it, and a white sheet rising from the bottom that says what they get and asks for one thing
 *  (add the field). Photo credit: assets/lang/CREDITS.md. */
export function FirstField({ name, t, onAdd, onSignOut }: {
  name: string; t: (k: any) => string; onAdd: () => void; onSignOut: () => void;
}) {
  const { width: w, height: h } = useWindowDimensions();
  const first = (name || '').split(' ')[0];
  const benefits: { icon: IconName; key: string; bg: string }[] = [
    { icon: 'drop', key: 'benefitWater', bg: '#E3F1FA' },
    { icon: 'sprout', key: 'benefitCrop', bg: '#E8F3E8' },
    { icon: 'blight', key: 'benefitDisease', bg: '#FDF0DC' },
  ];

  return (
    <View style={{ flex: 1, backgroundColor: '#1F3A1F' }}>
      <ImageBackground source={require('../../assets/field-hero.jpg')} resizeMode="cover" style={{ position: 'absolute', left: 0, top: 0, width: w, height: h * 0.62 }}>
        {/* darken the top for the greeting, fade the bottom into the sheet */}
        <Svg width={w} height={h * 0.62}>
          <Defs>
            <LinearGradient id="shade" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor="#0E240E" stopOpacity="0.72" />
              <Stop offset="0.5" stopColor="#0E240E" stopOpacity="0.25" />
              <Stop offset="1" stopColor="#0E240E" stopOpacity="0.1" />
            </LinearGradient>
          </Defs>
          <Rect x="0" y="0" width={w} height={h * 0.62} fill="url(#shade)" />
        </Svg>
      </ImageBackground>

      <View style={{ paddingHorizontal: S.xl, paddingTop: 72 }}>
        <Text style={{ fontSize: 16, color: 'rgba(255,255,255,0.85)', fontWeight: '600', letterSpacing: 0.4 }}>
          {t('welcomeName').replace('{name}', first)}
        </Text>
        <Text style={{ fontSize: 32, lineHeight: 39, color: '#fff', fontWeight: '800', marginTop: S.sm }}>{t('firstFieldHeadline')}</Text>
      </View>

      <View style={{ flex: 1 }} />

      <View style={{ backgroundColor: C.bg, borderTopLeftRadius: 30, borderTopRightRadius: 30, paddingHorizontal: S.xl, paddingTop: S.xl, paddingBottom: S.xl, maxHeight: h * 0.6 }}>
        <ScrollView bounces={false} showsVerticalScrollIndicator={false}>
          <Text style={{ fontSize: 17, lineHeight: 25, color: C.muted }}>{t('firstFieldSub')}</Text>

          <View style={{ marginTop: S.lg }}>
            {benefits.map((b) => (
              <View key={b.key} style={{ flexDirection: 'row', alignItems: 'center', marginBottom: S.md }}>
                <View style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: b.bg, alignItems: 'center', justifyContent: 'center', marginRight: S.md }}>
                  <Icon name={b.icon} size={24} color={C.accent} />
                </View>
                <Text style={{ flex: 1, fontSize: 17, lineHeight: 23, fontWeight: '600', color: C.text }}>{t(b.key)}</Text>
              </View>
            ))}
          </View>

          <TouchableOpacity
            onPress={() => { feedback.tap(); onAdd(); }}
            activeOpacity={0.85}
            style={{ minHeight: 58, borderRadius: 16, backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center', marginTop: S.md }}
          >
            <Text style={{ fontSize: 19, fontWeight: '800', color: '#fff' }}>{t('addMyField')}</Text>
          </TouchableOpacity>
          <Text style={{ fontSize: 14, color: C.muted, textAlign: 'center', marginTop: S.md }}>{t('firstFieldNote')}</Text>

          <TouchableOpacity onPress={onSignOut} style={{ alignItems: 'center', minHeight: 44, justifyContent: 'center', marginTop: S.xs }}>
            <Text style={{ fontSize: 15, color: C.muted, textDecorationLine: 'underline' }}>{t('signOut')}</Text>
          </TouchableOpacity>
        </ScrollView>
      </View>
    </View>
  );
}
