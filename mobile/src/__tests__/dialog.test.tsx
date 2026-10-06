jest.mock('expo-audio', () => ({ createAudioPlayer: jest.fn() }));
jest.mock('expo-haptics', () => ({}));
jest.mock('@react-native-async-storage/async-storage', () => require('@react-native-async-storage/async-storage/jest/async-storage-mock'));
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(() => Promise.resolve(null)),
  setItemAsync: jest.fn(() => Promise.resolve()),
  deleteItemAsync: jest.fn(() => Promise.resolve()),
}));

import React from 'react';
import { act, create } from 'react-test-renderer';
import { DialogHost, dialog } from '../dialog';
import { Btn } from '../ui';

test('a second dialog opened while one is showing still resolves, after the first closes', async () => {
  let renderer: any;
  act(() => { renderer = create(<DialogHost />); });

  let first!: Promise<boolean>;
  act(() => { first = dialog.confirm({ title: 'First', body: 'first body' }); });
  let second!: Promise<boolean>;
  act(() => { second = dialog.confirm({ title: 'Second', body: 'second body' }); });

  // the first dialog is still the only one showing (two buttons: cancel + confirm)
  expect(renderer.root.findAllByType(Btn)).toHaveLength(2);
  let buttons = renderer.root.findAllByType(Btn);
  act(() => { buttons[1].props.onPress(); }); // confirm button -> true
  expect(await first).toBe(true);

  // now the second dialog takes its place
  buttons = renderer.root.findAllByType(Btn);
  act(() => { buttons[0].props.onPress(); }); // cancel button -> false
  expect(await second).toBe(false);
}, 10000);
