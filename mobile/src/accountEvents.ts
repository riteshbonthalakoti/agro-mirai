type EventMap = {
  accountSignedIn: (id: string) => void;
  accountSwitched: (from: string | null, to: string) => void;
  accountSignedOut: (id: string) => void;
};

const listeners: { [K in keyof EventMap]: Set<EventMap[K]> } = {
  accountSignedIn: new Set(),
  accountSwitched: new Set(),
  accountSignedOut: new Set(),
};

export function onAccountEvent<K extends keyof EventMap>(event: K, fn: EventMap[K]): () => void {
  listeners[event].add(fn as any);
  return () => listeners[event].delete(fn as any);
}

export function emitAccountSignedIn(id: string) {
  listeners.accountSignedIn.forEach((fn) => fn(id));
}
export function emitAccountSwitched(from: string | null, to: string) {
  listeners.accountSwitched.forEach((fn) => fn(from, to));
}
export function emitAccountSignedOut(id: string) {
  listeners.accountSignedOut.forEach((fn) => fn(id));
}
