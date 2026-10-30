import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Animated,
  Easing,
  KeyboardAvoidingView,
  Modal,
  PanResponder,
  Platform,
  ScrollView,
  Text,
  TextInput,
  TouchableOpacity,
  TouchableWithoutFeedback,
  useWindowDimensions,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  ChatMessageItem,
  ChatSessionSummary,
  listChatSessionMessages,
  listChatSessions,
  sendChatMessage,
} from '../api';
import { useApp } from '../ctx';
import { formatTime } from '../storage';
import { Icon } from '../../icons';
import { C, S } from '../theme';
import { ChatChart } from './ChatChart';
import { ChatCardView } from './ChatCards';

type Msg = { id: string; role: 'user' | 'assistant'; content: string; chart?: import('../api').ChatChart | null; cards?: import('../api').ChatCard[] };

function fromServer(m: ChatMessageItem): Msg {
  return { id: m.id, role: m.role, content: m.content, chart: m.chart, cards: m.cards };
}

/** Past-sessions list -- lets the farmer pick up an earlier conversation
 * instead of only ever starting fresh (Module 58, user-directed: chat
 * history now persists server-side across app restarts/devices). */
function HistoryList({ sessions, loading, onPick, onBack }: {
  sessions: ChatSessionSummary[]; loading: boolean; onPick: (s: ChatSessionSummary) => void; onBack: () => void;
}) {
  const { t } = useApp();
  const tt = (k: string) => (t as any)(k) as string;
  return (
    <View style={{ flex: 1 }}>
      <View style={{ paddingHorizontal: S.lg, paddingBottom: S.sm, flexDirection: 'row', alignItems: 'center' }}>
        <TouchableOpacity onPress={onBack} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }} style={{ marginRight: S.sm }}>
          <Icon name="chevron-back" size={20} color={C.text} />
        </TouchableOpacity>
        <Text style={{ fontSize: 14, fontWeight: '800', color: C.text }}>{tt('chatHistoryTitle')}</Text>
      </View>
      {loading ? (
        <ActivityIndicator style={{ marginTop: S.lg }} color={C.accent} />
      ) : sessions.length === 0 ? (
        <Text style={{ fontSize: 13, color: C.muted, textAlign: 'center', marginTop: S.lg }}>{tt('chatHistoryEmpty')}</Text>
      ) : (
        <ScrollView contentContainerStyle={{ paddingHorizontal: S.lg, paddingBottom: S.lg }}>
          {sessions.map((s) => (
            <TouchableOpacity
              key={s.id}
              onPress={() => onPick(s)}
              style={{ paddingVertical: S.sm, borderBottomWidth: 1, borderBottomColor: C.border }}
            >
              <Text numberOfLines={1} style={{ fontSize: 14, color: C.text, fontWeight: '600' }}>{s.title || tt('chatTitle')}</Text>
              <Text style={{ fontSize: 11.5, color: C.muted, marginTop: 2 }}>{formatTime(s.updated_at)}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

/** Chat thread + input, filling whatever height the sheet gives it. Sized
 * entirely in relative/flex terms (no fixed px) so it adapts to any phone
 * or tablet width/height via the sheet's own useWindowDimensions sizing. */
function ChatPanel({ onClose, sheetHeight }: { onClose: () => void; sheetHeight: number }) {
  const { t, lang } = useApp();
  const tt = (k: string) => (t as any)(k) as string;
  const insets = useSafeAreaInsets();
  const [view, setView] = useState<'chat' | 'history'>('chat');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [loadingThread, setLoadingThread] = useState(true);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState('');
  const scrollRef = useRef<ScrollView>(null);

  // On open, resume the farmer's most recent thread rather than always
  // starting blank -- the whole point of persisting sessions server-side.
  useEffect(() => {
    (async () => {
      try {
        const list = await listChatSessions();
        if (list.length > 0) {
          const msgs = await listChatSessionMessages(list[0].id);
          setSessionId(list[0].id);
          setMessages(msgs.map(fromServer));
        }
      } catch {
        // offline or first-ever open: fine to start with a blank thread
      } finally {
        setLoadingThread(false);
      }
    })();
  }, []);

  const openHistory = async () => {
    setView('history');
    setLoadingSessions(true);
    try {
      setSessions(await listChatSessions());
    } catch {
      setSessions([]);
    } finally {
      setLoadingSessions(false);
    }
  };

  const pickSession = async (s: ChatSessionSummary) => {
    setView('chat');
    setLoadingThread(true);
    try {
      const msgs = await listChatSessionMessages(s.id);
      setSessionId(s.id);
      setMessages(msgs.map(fromServer));
    } catch {
      setErr(tt('chatUnavailable'));
    } finally {
      setLoadingThread(false);
    }
  };

  const startNewChat = () => {
    setSessionId(null);
    setMessages([]);
    setErr('');
  };

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    setErr('');
    const userMsg: Msg = { id: `u-${Date.now()}`, role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setSending(true);
    try {
      const res = await sendChatMessage(text, sessionId, lang);
      setSessionId(res.session_id);
      setMessages((prev) => [...prev, { id: `a-${Date.now()}`, role: 'assistant', content: res.reply, chart: res.chart, cards: res.cards }]);
    } catch {
      setErr(tt('chatUnavailable'));
    } finally {
      setSending(false);
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 50);
    }
  };

  return (
    <View style={{ height: sheetHeight, backgroundColor: C.bg, borderTopLeftRadius: 22, borderTopRightRadius: 22, overflow: 'hidden' }}>
      {/* drag handle doubles as the close affordance -- no back-button chrome, reads as a panel not a screen */}
      <TouchableOpacity onPress={onClose} accessibilityLabel={tt('close')} style={{ alignItems: 'center', paddingTop: S.sm, paddingBottom: S.xs }}>
        <View style={{ width: 40, height: 5, borderRadius: 3, backgroundColor: C.border }} />
      </TouchableOpacity>

      {view === 'history' ? (
        <HistoryList sessions={sessions} loading={loadingSessions} onPick={pickSession} onBack={() => setView('chat')} />
      ) : (
        <>
          <View style={{ paddingHorizontal: S.lg, paddingBottom: S.sm, flexDirection: 'row', alignItems: 'center' }}>
            <View style={{ width: 20, height: 20, borderRadius: 10, backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center', marginRight: S.xs }}>
              <Icon name="chat" size={12} color="#fff" />
            </View>
            <Text style={{ fontSize: 15, fontWeight: '800', color: C.text, flex: 1 }}>{tt('chatTitle')}</Text>
            <TouchableOpacity onPress={openHistory} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }} style={{ marginRight: S.md }} accessibilityLabel={tt('chatHistoryTitle')}>
              <Icon name="history" size={18} color={C.muted} />
            </TouchableOpacity>
            <TouchableOpacity onPress={startNewChat} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }} accessibilityLabel={tt('chatNew')}>
              <Icon name="plus" size={20} color={C.muted} />
            </TouchableOpacity>
          </View>

          <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
            {loadingThread ? (
              <ActivityIndicator style={{ marginTop: S.lg }} color={C.accent} />
            ) : (
              <ScrollView
                ref={scrollRef}
                style={{ flex: 1 }}
                contentContainerStyle={{ padding: S.lg, paddingBottom: S.xl }}
                onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
              >
                {messages.length === 0 ? (
                  <Text style={{ fontSize: 14, color: C.muted, textAlign: 'center', marginTop: S.lg }}>{tt('chatEmptyHint')}</Text>
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
                    {m.cards?.map((c, i) => <ChatCardView key={i} card={c} />)}
                  </View>
                ))}
                {sending ? (
                  <View style={{ alignSelf: 'flex-start', marginBottom: S.sm }}>
                    <ActivityIndicator size="small" color={C.accent} />
                  </View>
                ) : null}
                {err ? <Text style={{ fontSize: 13, color: C.danger, marginTop: S.xs }}>{err}</Text> : null}
              </ScrollView>
            )}

            <View style={{ flexDirection: 'row', alignItems: 'flex-end', paddingHorizontal: S.md, paddingTop: S.sm, paddingBottom: Math.max(S.sm, insets.bottom), borderTopWidth: 1, borderTopColor: C.border, gap: S.sm }}>
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
        </>
      )}
    </View>
  );
}

/** Slide-up bottom-sheet overlay (not a full-screen takeover): backdrop tap,
 * swipe-down, or the drag handle all dismiss it. Sized as a fraction of the
 * live window height/width via useWindowDimensions, so it scales correctly
 * on any phone or tablet instead of assuming one screen size. */
function ChatSheet({ visible, onRequestClose }: { visible: boolean; onRequestClose: () => void }) {
  const { height: winH, width: winW } = useWindowDimensions();
  const sheetHeight = Math.round(winH * (winW > 700 ? 0.7 : 0.86));
  const translateY = useRef(new Animated.Value(sheetHeight)).current;
  const backdropOpacity = useRef(new Animated.Value(0)).current;

  const animateIn = () => {
    translateY.setValue(sheetHeight);
    Animated.parallel([
      Animated.timing(backdropOpacity, { toValue: 1, duration: 200, useNativeDriver: true }),
      Animated.spring(translateY, { toValue: 0, friction: 9, tension: 65, useNativeDriver: true }),
    ]).start();
  };

  const animateOutThenClose = () => {
    Animated.parallel([
      Animated.timing(backdropOpacity, { toValue: 0, duration: 180, useNativeDriver: true }),
      Animated.timing(translateY, { toValue: sheetHeight, duration: 220, easing: Easing.in(Easing.cubic), useNativeDriver: true }),
    ]).start(() => onRequestClose());
  };

  React.useEffect(() => {
    if (visible) animateIn();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, sheetHeight]);

  const pan = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, g) => g.dy > 6 && Math.abs(g.dy) > Math.abs(g.dx),
      onPanResponderMove: (_, g) => {
        if (g.dy > 0) translateY.setValue(g.dy);
      },
      onPanResponderRelease: (_, g) => {
        if (g.dy > sheetHeight * 0.22 || g.vy > 1.2) {
          animateOutThenClose();
        } else {
          Animated.spring(translateY, { toValue: 0, friction: 9, tension: 65, useNativeDriver: true }).start();
        }
      },
    })
  ).current;

  if (!visible) return null;

  return (
    <Modal visible transparent animationType="none" statusBarTranslucent onRequestClose={animateOutThenClose}>
      <View style={{ flex: 1, justifyContent: 'flex-end' }}>
        <TouchableWithoutFeedback onPress={animateOutThenClose}>
          <Animated.View style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(10,18,10,0.45)', opacity: backdropOpacity }} />
        </TouchableWithoutFeedback>
        <Animated.View {...pan.panHandlers} style={{ transform: [{ translateY }] }}>
          <ChatPanel onClose={animateOutThenClose} sheetHeight={sheetHeight} />
        </Animated.View>
      </View>
    </Modal>
  );
}

/** Round floating chat button (bottom-right): same visual treatment and
 * position as AdviceTab's AskFab mic button, mounted once at the app root
 * so it floats over every tab. Tapping opens a lightweight bottom-sheet
 * chat panel -- deliberately not a full-screen takeover. */
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
      <ChatSheet visible={open} onRequestClose={() => setOpen(false)} />
    </>
  );
}
