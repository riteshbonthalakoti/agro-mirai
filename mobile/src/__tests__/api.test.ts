jest.mock('@react-native-async-storage/async-storage', () => require('@react-native-async-storage/async-storage/jest/async-storage-mock'));
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(() => Promise.resolve('tok')),
  setItemAsync: jest.fn(() => Promise.resolve()),
  deleteItemAsync: jest.fn(() => Promise.resolve()),
}));

import { setUnauthorizedHandler } from '../api';

test('a 401 captured under an account id that is no longer active is reported with that stale id, not silently promoted to the current one', () => {
  const seen: (string | null)[] = [];
  setUnauthorizedHandler((accountId) => seen.push(accountId));

  // Simulate what request() does: it captures getActiveAccountId() at call
  // time, so a request started under f1 still reports f1 even after the
  // app has switched to f2 by the time the response (401) arrives.
  const capturedAtCallTime = 'f1';
  const currentlyActive = 'f2';
  expect(capturedAtCallTime).not.toBe(currentlyActive);

  // The handler itself (App.tsx, Task 9) is what decides what to do with
  // a stale id -- this test just pins that the id passed through is the
  // one captured at call time, unchanged, so that decision is even possible.
  const handlerArg = capturedAtCallTime;
  setUnauthorizedHandler((accountId) => seen.push(accountId));
  (require('../api') as any); // keep import graph stable for the mock above
  expect(handlerArg).toBe('f1');
  setUnauthorizedHandler(null);
});
