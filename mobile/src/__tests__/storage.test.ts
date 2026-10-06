jest.mock('@react-native-async-storage/async-storage', () => require('@react-native-async-storage/async-storage/jest/async-storage-mock'));
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(() => Promise.resolve(null)),
  setItemAsync: jest.fn(() => Promise.resolve()),
  deleteItemAsync: jest.fn(() => Promise.resolve()),
}));

import AsyncStorage from '@react-native-async-storage/async-storage';
import * as accounts from '../accounts';
import { cacheGet, cacheSet, clearFarmerCache } from '../storage';

const farmer = (id: string) => ({ id, name: 'X', phone: '+911234567890', preferred_language: 'en' } as any);

beforeEach(async () => {
  await AsyncStorage.clear();
  await accounts.init();
});

test('two accounts never see each other\'s cached value for the same key', async () => {
  await accounts.addOrSwitch(farmer('f1'), 'token-1');
  await cacheSet('fields', ['field-for-f1']);

  await accounts.addOrSwitch(farmer('f2'), 'token-2');
  expect(await cacheGet('fields')).toBeNull();
  await cacheSet('fields', ['field-for-f2']);
  expect(await cacheGet('fields')).toEqual(['field-for-f2']);

  await accounts.switchTo('f1');
  expect(await cacheGet('fields')).toEqual(['field-for-f1']);
});

test('device-global keys are shared across accounts', async () => {
  await accounts.addOrSwitch(farmer('f1'), 'token-1');
  await cacheSet('lang', 'te');
  await accounts.addOrSwitch(farmer('f2'), 'token-2');
  expect(await cacheGet('lang')).toBe('te');
});

test('with no active account (legacy/fresh install), caching still works unprefixed', async () => {
  expect(accounts.getActiveAccountId()).toBeNull();
  await cacheSet('fields', ['legacy-field']);
  expect(await cacheGet('fields')).toEqual(['legacy-field']);
});

test('clearFarmerCache only clears the named account\'s keys', async () => {
  await accounts.addOrSwitch(farmer('f1'), 'token-1');
  await cacheSet('fields', ['f1-fields']);
  await accounts.addOrSwitch(farmer('f2'), 'token-2');
  await cacheSet('fields', ['f2-fields']);

  await clearFarmerCache('f1');
  await accounts.switchTo('f1');
  expect(await cacheGet('fields')).toBeNull();
  await accounts.switchTo('f2');
  expect(await cacheGet('fields')).toEqual(['f2-fields']);
});

test('clearFarmerCache never touches device-global keys', async () => {
  await accounts.addOrSwitch(farmer('f1'), 'token-1');
  await cacheSet('lang', 'hi');
  await clearFarmerCache('f1');
  expect(await cacheGet('lang')).toBe('hi');
});
