import React, { useRef, useState } from 'react';
import { Animated, Dimensions, Image, Modal, PanResponder, StatusBar, Text, TouchableOpacity, View } from 'react-native';
import { S } from './theme';

/** Full-screen pinch-to-zoom / pan / double-tap image viewer, built on
 *  PanResponder + Animated only (both are core React Native, not extra
 *  native modules) so it needs no new dependency or native rebuild. */
export function ZoomModal({ uri, visible, onClose, caption }: { uri: string | null; visible: boolean; onClose: () => void; caption?: string }) {
  const scale = useRef(new Animated.Value(1)).current;
  const translate = useRef(new Animated.ValueXY({ x: 0, y: 0 })).current;
  const scaleRef = useRef(1);
  const translateRef = useRef({ x: 0, y: 0 });
  const pinchStart = useRef({ dist: 0, scale: 1 });
  const panStart = useRef({ x: 0, y: 0 });
  const lastTap = useRef(0);
  const win = Dimensions.get('window');

  const clampAndSet = (nextScale: number, nx: number, ny: number) => {
    const s = Math.max(1, Math.min(4, nextScale));
    const maxX = ((s - 1) * win.width) / 2;
    const maxY = ((s - 1) * win.height) / 2;
    const cx = Math.max(-maxX, Math.min(maxX, nx));
    const cy = Math.max(-maxY, Math.min(maxY, ny));
    scaleRef.current = s;
    translateRef.current = { x: cx, y: cy };
    scale.setValue(s);
    translate.setValue({ x: cx, y: cy });
  };

  const reset = () => clampAndSet(1, 0, 0);

  const dist = (touches: { pageX: number; pageY: number }[]) => {
    const [a, b] = touches;
    return Math.hypot(a.pageX - b.pageX, a.pageY - b.pageY);
  };

  const responder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (e) => {
        const touches = e.nativeEvent.touches;
        if (touches.length === 2) {
          pinchStart.current = { dist: dist(touches as any), scale: scaleRef.current };
        } else {
          panStart.current = { ...translateRef.current };
        }
      },
      onPanResponderMove: (e, gesture) => {
        const touches = e.nativeEvent.touches;
        if (touches.length === 2) {
          const d = dist(touches as any);
          if (pinchStart.current.dist > 0) {
            const factor = d / pinchStart.current.dist;
            clampAndSet(pinchStart.current.scale * factor, translateRef.current.x, translateRef.current.y);
          }
        } else if (scaleRef.current > 1) {
          clampAndSet(scaleRef.current, panStart.current.x + gesture.dx, panStart.current.y + gesture.dy);
        }
      },
      onPanResponderRelease: () => {
        const now = Date.now();
        if (now - lastTap.current < 280) {
          scaleRef.current > 1 ? reset() : clampAndSet(2.5, 0, 0);
        }
        lastTap.current = now;
      },
    })
  ).current;

  if (!uri) return null;
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={() => { reset(); onClose(); }}>
      <StatusBar barStyle="light-content" backgroundColor="#000" />
      <View style={{ flex: 1, backgroundColor: '#000' }}>
        <View {...responder.panHandlers} style={{ flex: 1, overflow: 'hidden' }}>
          <Animated.Image
            source={{ uri }}
            resizeMode="contain"
            style={{ width: win.width, height: win.height, transform: [{ translateX: translate.x }, { translateY: translate.y }, { scale }] }}
          />
        </View>
        <TouchableOpacity
          onPress={() => { reset(); onClose(); }}
          hitSlop={{ top: 16, bottom: 16, left: 16, right: 16 }}
          style={{ position: 'absolute', top: 48, right: 20, width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(0,0,0,0.5)', alignItems: 'center', justifyContent: 'center' }}
        >
          <Text style={{ color: '#fff', fontSize: 20 }}>✕</Text>
        </TouchableOpacity>
        {caption ? (
          <View style={{ position: 'absolute', bottom: 40, left: 0, right: 0, alignItems: 'center' }}>
            <Text style={{ color: '#fff', backgroundColor: 'rgba(0,0,0,0.5)', paddingHorizontal: S.md, paddingVertical: 6, borderRadius: 8, fontSize: 13 }}>{caption}</Text>
          </View>
        ) : null}
      </View>
    </Modal>
  );
}
