import { cacheGet, cacheSet } from './storage';

/** "Ask AI" (voice) conversations, saved locally per field so the farmer can
 *  find them again on the Advice tab's "My questions" list. There is no
 *  server-side conversation history yet (Module 48 note: add a backend
 *  table if this needs to survive a reinstall or sync across devices) --
 *  this is deliberately local-only for now, fast to ship and enough to fix
 *  the "my questions just vanish" complaint. */
export type Conversation = { id: string; question: string; answer: string; lang: string; ts: number };

const key = (fieldId: string) => `askHistory:${fieldId}`;
const MAX_SAVED = 50;

export async function getConversations(fieldId: string): Promise<Conversation[]> {
  return (await cacheGet<Conversation[]>(key(fieldId))) || [];
}

export async function saveConversation(fieldId: string, entry: { question: string; answer: string; lang: string }): Promise<void> {
  const list = await getConversations(fieldId);
  list.unshift({ id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, ts: Date.now(), ...entry });
  await cacheSet(key(fieldId), list.slice(0, MAX_SAVED));
}
