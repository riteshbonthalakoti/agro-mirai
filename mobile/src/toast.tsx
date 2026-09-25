import React, { createContext, useCallback, useContext, useRef, useState } from 'react';
import { Animated, Text, View } from 'react-native';
import { feedback } from './feedback';
import { C, S } from './theme';

type Toast = { id: number; text: string; kind: 'info' | 'ok' | 'error' };
type ToastCtx = { show: (text: string, kind?: Toast['kind']) => void };

const Ctx = createContext<ToastCtx>({ show: () => {} });
export const useToast = () => useContext(Ctx);

let nextId = 1;

/** Simple in-app notification banner -- appears at the top, auto-dismisses.
 *  Wrap the app root once; call useToast().show(...) from anywhere below it. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const anim = useRef(new Animated.Value(0)).current;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback((text: string, kind: Toast['kind'] = 'info') => {
    if (timer.current) clearTimeout(timer.current);
    if (kind === 'ok') feedback.success();
    else if (kind === 'error') feedback.error();
    setToast({ id: nextId++, text, kind });
    anim.setValue(0);
    Animated.timing(anim, { toValue: 1, duration: 200, useNativeDriver: true }).start();
    timer.current = setTimeout(() => {
      Animated.timing(anim, { toValue: 0, duration: 200, useNativeDriver: true }).start(() => setToast(null));
    }, 3000);
  }, [anim]);

  const color = toast?.kind === 'error' ? C.danger : toast?.kind === 'ok' ? C.accent : C.text;

  return (
    <Ctx.Provider value={{ show }}>
      {children}
      {toast ? (
        <Animated.View
          pointerEvents="none"
          style={{
            position: 'absolute', top: 56, left: S.lg, right: S.lg,
            opacity: anim, transform: [{ translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [-12, 0] }) }],
          }}
        >
          <View style={{ backgroundColor: '#1A1D19', borderRadius: 10, paddingVertical: S.sm, paddingHorizontal: S.md, borderLeftWidth: 4, borderLeftColor: color }}>
            <Text style={{ color: '#fff', fontSize: 14 }}>{toast.text}</Text>
          </View>
        </Animated.View>
      ) : null}
    </Ctx.Provider>
  );
}
