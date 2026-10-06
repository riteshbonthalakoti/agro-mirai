jest.mock('@react-native-async-storage/async-storage', () => require('@react-native-async-storage/async-storage/jest/async-storage-mock'));
jest.mock('expo-secure-store', () => {
  const store = new Map<string, string>();
  return {
    getItemAsync: jest.fn((k: string) => Promise.resolve(store.get(k) ?? null)),
    setItemAsync: jest.fn((k: string, v: string) => { store.set(k, v); return Promise.resolve(); }),
    deleteItemAsync: jest.fn((k: string) => { store.delete(k); return Promise.resolve(); }),
  };
});

import AsyncStorage from '@react-native-async-storage/async-storage';
import * as accounts from '../accounts';

const farmer = (id: string, name: string, phone: string) => ({ id, name, phone, preferred_language: 'en' } as any);

beforeEach(async () => {
  await AsyncStorage.clear();
  await accounts.init();
});

test('addOrSwitch saves a new account and makes it active', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');
  expect(accounts.getActiveAccountId()).toBe('f1');
  expect(accounts.getActiveToken()).toBe('token-1');
  const list = await accounts.listAccounts();
  expect(list).toHaveLength(1);
  expect(list[0]).toMatchObject({ id: 'f1', name: 'Asha', phone: '+919000000001' });
});

test('addOrSwitch on an already-saved id switches instead of duplicating', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');
  await accounts.addOrSwitch(farmer('f2', 'Bala', '+919000000002'), 'token-2');
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1b');

  const list = await accounts.listAccounts();
  expect(list).toHaveLength(2);
  expect(accounts.getActiveAccountId()).toBe('f1');
  expect(accounts.getActiveToken()).toBe('token-1b');
});

test('adding a 6th genuinely new account throws AccountLimitReached', async () => {
  for (let i = 1; i <= 5; i++) {
    await accounts.addOrSwitch(farmer(`f${i}`, `Farmer ${i}`, `+91900000000${i}`), `token-${i}`);
  }
  await expect(
    accounts.addOrSwitch(farmer('f6', 'Farmer 6', '+919000000006'), 'token-6')
  ).rejects.toBeInstanceOf(accounts.AccountLimitReached);
  expect(await accounts.listAccounts()).toHaveLength(5);
});

test('MAX_ACCOUNTS is exported so the UI can pre-check the limit before opening the add-account flow', () => {
  expect(accounts.MAX_ACCOUNTS).toBe(5);
});

test('switchTo moves the active pointer and token without touching the list length', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');
  await accounts.addOrSwitch(farmer('f2', 'Bala', '+919000000002'), 'token-2');

  await accounts.switchTo('f1');
  expect(accounts.getActiveAccountId()).toBe('f1');
  expect(accounts.getActiveToken()).toBe('token-1');
  expect(await accounts.listAccounts()).toHaveLength(2);
});

test('switchTo an unsaved id throws', async () => {
  await expect(accounts.switchTo('ghost')).rejects.toThrow();
});

test('markSessionExpired flags one account without removing it or others', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');
  await accounts.addOrSwitch(farmer('f2', 'Bala', '+919000000002'), 'token-2');

  await accounts.markSessionExpired('f1');
  const list = await accounts.listAccounts();
  expect(list.find((a) => a.id === 'f1')?.sessionExpired).toBe(true);
  expect(list.find((a) => a.id === 'f2')?.sessionExpired).toBeFalsy();
});

test('remove on a non-active account leaves the active one untouched', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');
  await accounts.addOrSwitch(farmer('f2', 'Bala', '+919000000002'), 'token-2');
  await accounts.switchTo('f1');

  const result = await accounts.remove('f2');
  expect(result).toBe('f1');
  expect(accounts.getActiveAccountId()).toBe('f1');
  expect(await accounts.listAccounts()).toHaveLength(1);
});

test('remove on the active account switches to the most-recently-active remaining one', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');
  await accounts.addOrSwitch(farmer('f2', 'Bala', '+919000000002'), 'token-2');
  // f2 is now active (most recently added/switched)

  const result = await accounts.remove('f2');
  expect(result).toBe('f1');
  expect(accounts.getActiveAccountId()).toBe('f1');
});

test('remove on the only saved account returns null and clears the active pointer', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');

  const result = await accounts.remove('f1');
  expect(result).toBeNull();
  expect(accounts.getActiveAccountId()).toBeNull();
  expect(accounts.getActiveToken()).toBeNull();
  expect(await accounts.listAccounts()).toHaveLength(0);
});

test('getTokenFor returns a saved account\'s own token, not the active one\'s', async () => {
  await accounts.addOrSwitch(farmer('f1', 'Asha', '+919000000001'), 'token-1');
  await accounts.addOrSwitch(farmer('f2', 'Bala', '+919000000002'), 'token-2');
  // f2 is active now, but we want f1's token specifically
  expect(await accounts.getTokenFor('f1')).toBe('token-1');
  expect(await accounts.getTokenFor('f2')).toBe('token-2');
});

test('getTokenFor returns null for an id with no stored token', async () => {
  expect(await accounts.getTokenFor('ghost')).toBeNull();
});

test('init with nothing saved yet leaves no active account (legacy / fresh install)', async () => {
  expect(accounts.getActiveAccountId()).toBeNull();
  expect(accounts.getActiveToken()).toBeNull();
});
