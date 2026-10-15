import { cacheGet, cacheSet } from './storage';
import { ConversationItem, fetchConversationsApi, saveConversationApi } from './api';

export type Conversation = ConversationItem;

const key = (fieldId: string) => `askHistory:${fieldId}`;
const MAX_SAVED = 50;

export async function getConversations(fieldId: string): Promise<Conversation[]> {
  const local = (await cacheGet<Conversation[]>(key(fieldId))) || [];
  try {
    const remote = await fetchConversationsApi(fieldId);
    if (remote && Array.isArray(remote)) {
      // Merge remote and local by id, newest first
      const map = new Map<string, Conversation>();
      remote.forEach((c) => map.set(c.id, c));
      local.forEach((c) => {
        if (!map.has(c.id)) map.set(c.id, c);
      });
      const merged = Array.from(map.values()).sort((a, b) => b.ts - a.ts).slice(0, MAX_SAVED);
      await cacheSet(key(fieldId), merged);
      return merged;
    }
  } catch {
    // Offline or network error: return cached local conversations
  }
  return local;
}

export async function saveConversation(fieldId: string, entry: { question: string; answer: string; lang: string }): Promise<void> {
  const local = await getConversations(fieldId);
  const tempId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const item: Conversation = { id: tempId, field_id: fieldId, ts: Date.now(), ...entry };
  local.unshift(item);
  await cacheSet(key(fieldId), local.slice(0, MAX_SAVED));

  // Sync to database in background
  saveConversationApi({ field_id: fieldId, ...entry })
    .then((saved) => {
      if (saved && saved.id) {
        // Update local item with real DB id
        item.id = saved.id;
        cacheSet(key(fieldId), local.slice(0, MAX_SAVED));
      }
    })
    .catch(() => {});
}
