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

  const iconText = toast?.kind === 'ok' ? '✓' : toast?.kind === 'error' ? '⚠️' : 'ℹ';
  // TODO: add #2563EB as C.info to theme.ts
  const iconColor = toast?.kind === 'ok' ? C.accent : toast?.kind === 'error' ? C.danger : '#2563EB';

  return (
    <Ctx.Provider value={{ show }}>
      {children}
      {toast ? (
        <Animated.View
          pointerEvents="none"
          style={{
            position: 'absolute',
            top: 54,
            left: 0,
            right: 0,
            alignItems: 'center',
            opacity: anim,
            transform: [{ translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [-16, 0] }) }],
            zIndex: 9999,
          }}
        >
          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              backgroundColor: C.bg,
              borderRadius: 24,
              paddingVertical: 9,
              paddingHorizontal: 18,
              borderWidth: 1,
              borderColor: C.border,
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 3 },
              shadowOpacity: 0.1,
              shadowRadius: 8,
              elevation: 4,
            }}
          >
            <Text style={{ fontSize: 15, fontWeight: '800', color: iconColor, marginRight: 8 }}>{iconText}</Text>
            <Text style={{ color: C.text, fontSize: 14, fontWeight: '600', letterSpacing: 0.2 }}>{toast.text}</Text>
          </View>
        </Animated.View>
      ) : null}
    </Ctx.Provider>
  );
}
