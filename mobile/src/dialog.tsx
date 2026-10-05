import React, { useEffect, useState } from 'react';
import { Modal, Text, View } from 'react-native';
import { C, S } from './theme';
import { Btn } from './ui';

type ConfirmOpts = { title: string; body: string; confirmLabel?: string; cancelLabel?: string; destructive?: boolean };
type InfoOpts = { title: string; body: string; closeLabel?: string };
type DialogState =
  | { kind: 'confirm'; opts: ConfirmOpts; resolve: (v: boolean) => void }
  | { kind: 'info'; opts: InfoOpts; resolve: () => void }
  | null;

let show: ((s: Exclude<DialogState, null>) => void) | null = null;

export const dialog = {
  confirm(opts: ConfirmOpts): Promise<boolean> {
    return new Promise((resolve) => {
      if (!show) { resolve(false); return; }
      show({ kind: 'confirm', opts, resolve });
    });
  },
  info(opts: InfoOpts): Promise<void> {
    return new Promise((resolve) => {
      if (!show) { resolve(); return; }
      show({ kind: 'info', opts, resolve });
    });
  },
};

/** Themed replacement for Alert.alert, built from the app's own theme
 *  tokens. Mount once near the app root (App.tsx); call dialog.confirm/
 *  dialog.info from anywhere below it. */
export function DialogHost() {
  const [state, setState] = useState<DialogState>(null);

  useEffect(() => {
    show = setState;
    return () => { show = null; };
  }, []);

  if (!state) return null;

  const closeConfirm = (result: boolean) => {
    if (state.kind === 'confirm') state.resolve(result);
    setState(null);
  };
  const closeInfo = () => {
    if (state.kind === 'info') state.resolve();
    setState(null);
  };

  return (
    <Modal visible transparent animationType="fade" onRequestClose={() => (state.kind === 'confirm' ? closeConfirm(false) : closeInfo())}>
      <View style={{ flex: 1, backgroundColor: 'rgba(16,24,16,0.5)', alignItems: 'center', justifyContent: 'center', padding: S.xl }}>
        <View style={{ backgroundColor: C.bg, borderRadius: 18, padding: S.lg, width: '100%', maxWidth: 360 }}>
          <Text style={{ fontSize: 18, fontWeight: '800', color: C.text }}>{state.opts.title}</Text>
          <Text style={{ fontSize: 14, color: C.muted, marginTop: S.sm, lineHeight: 20 }}>{state.opts.body}</Text>
          {state.kind === 'confirm' ? (
            <View style={{ flexDirection: 'row', gap: S.sm, marginTop: S.lg }}>
              <Btn label={state.opts.cancelLabel ?? 'Cancel'} kind="secondary" onPress={() => closeConfirm(false)} style={{ flex: 1 }} />
              <Btn label={state.opts.confirmLabel ?? 'OK'} kind={state.opts.destructive ? 'danger' : 'primary'} onPress={() => closeConfirm(true)} style={{ flex: 1 }} />
            </View>
          ) : (
            <Btn label={state.opts.closeLabel ?? 'OK'} onPress={closeInfo} style={{ marginTop: S.lg }} />
          )}
        </View>
      </View>
    </Modal>
  );
}
