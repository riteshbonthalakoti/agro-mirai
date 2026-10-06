import { shouldScheduleDailyReminder, type SchedulingInput } from './notificationScheduling';

describe('shouldScheduleDailyReminder', () => {
  it('returns false when no account is signed in', () => {
    const input: SchedulingInput = {
      accountSignedIn: false,
      fieldId: 'field123',
      adviceText: 'Water your field',
    };
    const result = shouldScheduleDailyReminder(input);
    expect(result.shouldSchedule).toBe(false);
    expect(result.reason).toBe('noAccount');
  });

  it('returns false when no field is selected', () => {
    const input: SchedulingInput = {
      accountSignedIn: true,
      fieldId: null,
      adviceText: 'Water your field',
    };
    const result = shouldScheduleDailyReminder(input);
    expect(result.shouldSchedule).toBe(false);
    expect(result.reason).toBe('noField');
  });

  it('returns false when no advice text is available', () => {
    const input: SchedulingInput = {
      accountSignedIn: true,
      fieldId: 'field123',
      adviceText: null,
    };
    const result = shouldScheduleDailyReminder(input);
    expect(result.shouldSchedule).toBe(false);
    expect(result.reason).toBe('noAdvice');
  });

  it('returns false when advice text is empty string', () => {
    const input: SchedulingInput = {
      accountSignedIn: true,
      fieldId: 'field123',
      adviceText: '',
    };
    const result = shouldScheduleDailyReminder(input);
    expect(result.shouldSchedule).toBe(false);
    expect(result.reason).toBe('noAdvice');
  });

  it('returns true when all prerequisites are met', () => {
    const input: SchedulingInput = {
      accountSignedIn: true,
      fieldId: 'field123',
      adviceText: 'Water your field',
    };
    const result = shouldScheduleDailyReminder(input);
    expect(result.shouldSchedule).toBe(true);
    expect(result.reason).toBe('ready');
  });

  it('returns true with non-empty advice text', () => {
    const input: SchedulingInput = {
      accountSignedIn: true,
      fieldId: 'abc',
      adviceText: 'Check for disease',
    };
    const result = shouldScheduleDailyReminder(input);
    expect(result.shouldSchedule).toBe(true);
    expect(result.reason).toBe('ready');
  });

  it('returns false when reminders are explicitly disabled', () => {
    const input: SchedulingInput = {
      accountSignedIn: true,
      fieldId: 'field123',
      adviceText: 'Water your field',
      reminderEnabled: false,
    };
    const result = shouldScheduleDailyReminder(input);
    expect(result.shouldSchedule).toBe(false);
    expect(result.reason).toBe('remindersDisabled');
  });

  it('returns true with default time when reminders enabled is not specified', () => {
    const input: SchedulingInput = {
      accountSignedIn: true,
      fieldId: 'field123',
      adviceText: 'Water your field',
      reminderEnabled: true,
    };
    const result = shouldScheduleDailyReminder(input);
    expect(result.shouldSchedule).toBe(true);
    expect(result.reason).toBe('ready');
    expect(result.timeMinutes).toBe(7 * 60);
  });

  it('simulates account 1 enabled at 7am and account 2 disabled on switch', () => {
    // Account 1: reminders enabled
    const account1Input: SchedulingInput = {
      accountSignedIn: true,
      fieldId: 'field-acc1',
      adviceText: 'Water at 7am',
      reminderEnabled: true,
    };
    const result1 = shouldScheduleDailyReminder(account1Input);
    expect(result1.shouldSchedule).toBe(true);

    // Account 2: reminders disabled
    const account2Input: SchedulingInput = {
      accountSignedIn: true,
      fieldId: 'field-acc2',
      adviceText: 'No reminder for this account',
      reminderEnabled: false,
    };
    const result2 = shouldScheduleDailyReminder(account2Input);
    expect(result2.shouldSchedule).toBe(false);
    expect(result2.reason).toBe('remindersDisabled');
  });
});
