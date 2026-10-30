import React, { useRef, useState } from 'react';
import {
  ActivityIndicator,
  Animated,
  Easing,
  KeyboardAvoidingView,
  Modal,
  Platform,
  ScrollView,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { ChatHistoryItem, sendChatMessage } from '../api';
import { useApp } from '../ctx';
import { Icon } from '../../icons';
import { C, S } from '../theme';
import { ChatChart } from './ChatChart';

type Msg = ChatHistoryItem & { id: string; chart?: import('../api').ChatChart | null };

/** Full-screen chat overlay opened from the floating round button. Text-only
 * Q&A against the /v2/chat assistant, grounded in the farmer's own field
 * data server-side; renders any structured chart block the model returns. */
function ChatPanel({ onClose }: { onClose: () => void }) {
  const { t, lang } = useApp();
  const tt = (k: string) => (t as any)(k) as string;
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState('');
  const scrollRef = useRef<ScrollView>(null);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    setErr('');
    const userMsg: Msg = { id: `u-${Date.now()}`, role: 'user', content: text };
    const history: ChatHistoryItem[] = messages.map(({ role, content }) => ({ role, content }));
    setMessages((prev) => [...prev, userMsg]);
    setSending(true);
    try {
      const res = await sendChatMessage(text, history, lang);
      setMessages((prev) => [...prev, { id: `a-${Date.now()}`, role: 'assistant', content: res.reply, chart: res.chart }]);
    } catch {
      setErr(tt('chatUnavailable'));
    } finally {
      setSending(false);
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 50);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <View style={{ paddingTop: 52, paddingHorizontal: S.lg, paddingBottom: S.sm, flexDirection: 'row', alignItems: 'center', borderBottomWidth: 1, borderBottomColor: C.border }}>
        <TouchableOpacity onPress={onClose} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }} accessibilityLabel={tt('close')} style={{ width: 40, height: 40, alignItems: 'center', justifyContent: 'center' }}>
          <Icon name="close" size={20} color={C.text} />
        </TouchableOpacity>
        <Text style={{ flex: 1, textAlign: 'center', fontSize: 16, fontWeight: '800', color: C.text }}>{tt('chatTitle')}</Text>
        <View style={{ width: 40 }} />
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          ref={scrollRef}
          style={{ flex: 1 }}
          contentContainerStyle={{ padding: S.lg, paddingBottom: S.xl }}
          onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
        >
          {messages.length === 0 ? (
            <Text style={{ fontSize: 14, color: C.muted, textAlign: 'center', marginTop: S.xl }}>{tt('chatEmptyHint')}</Text>
          ) : null}
          {messages.map((m) => (
            <View
              key={m.id}
              style={{
                alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '85%',
                backgroundColor: m.role === 'user' ? C.accent : C.surface,
                borderRadius: 16,
                paddingVertical: 10,
                paddingHorizontal: 14,
                marginBottom: S.sm,
              }}
            >
              <Text style={{ fontSize: 15, lineHeight: 21, color: m.role === 'user' ? C.accentText : C.text }}>{m.content}</Text>
              {m.chart ? <ChatChart chart={m.chart} /> : null}
            </View>
          ))}
          {sending ? (
            <View style={{ alignSelf: 'flex-start', marginBottom: S.sm }}>
              <ActivityIndicator size="small" color={C.accent} />
            </View>
          ) : null}
          {err ? <Text style={{ fontSize: 13, color: C.danger, marginTop: S.xs }}>{err}</Text> : null}
        </ScrollView>

        <View style={{ flexDirection: 'row', alignItems: 'flex-end', padding: S.md, borderTopWidth: 1, borderTopColor: C.border, gap: S.sm }}>
          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder={tt('chatPlaceholder')}
            placeholderTextColor={C.muted}
            multiline
            style={{
              flex: 1,
              maxHeight: 100,
              borderWidth: 1,
              borderColor: C.border,
              borderRadius: 20,
              paddingHorizontal: S.md,
              paddingVertical: 10,
              fontSize: 15,
              color: C.text,
            }}
          />
          <TouchableOpacity
            onPress={send}
            disabled={!input.trim() || sending}
            accessibilityLabel={tt('chatTitle')}
            style={{
              width: 44,
              height: 44,
              borderRadius: 22,
              backgroundColor: C.accent,
              alignItems: 'center',
              justifyContent: 'center',
              opacity: !input.trim() || sending ? 0.5 : 1,
            }}
          >
            <Icon name="send" size={20} color="#fff" />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

/** Round floating chat button (bottom-right): same visual treatment and
 * position as AdviceTab's AskFab mic button, mounted once at the app root
 * so it floats over every tab. Tapping opens a full-screen chat overlay. */
export function ChatAssistant() {
  const { t } = useApp();
  const [open, setOpen] = useState(false);
  const ring = useRef(new Animated.Value(0)).current;
  React.useEffect(() => {
    const l = Animated.loop(Animated.timing(ring, { toValue: 1, duration: 2600, easing: Easing.out(Easing.quad), useNativeDriver: true }));
    l.start();
    return () => l.stop();
  }, [ring]);

  return (
    <>
      <View pointerEvents="box-none" style={{ position: 'absolute', right: S.lg, bottom: 76, width: 60, height: 60, alignItems: 'center', justifyContent: 'center' }}>
        <Animated.View pointerEvents="none" style={{ position: 'absolute', width: 54, height: 54, borderRadius: 27, backgroundColor: C.accent, opacity: ring.interpolate({ inputRange: [0, 1], outputRange: [0.3, 0] }), transform: [{ scale: ring.interpolate({ inputRange: [0, 1], outputRange: [1, 1.4] }) }] }} />
        <TouchableOpacity
          onPress={() => setOpen(true)}
          activeOpacity={0.85}
          accessibilityLabel={(t as any)('chatTitle')}
          style={{ width: 54, height: 54, borderRadius: 27, backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center', shadowColor: '#0B3D24', shadowOpacity: 0.4, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 10 }}
        >
          <Icon name="chat" size={26} color="#fff" />
        </TouchableOpacity>
      </View>
      <Modal visible={open} animationType="slide" statusBarTranslucent onRequestClose={() => setOpen(false)}>
        <ChatPanel onClose={() => setOpen(false)} />
      </Modal>
    </>
  );
}
