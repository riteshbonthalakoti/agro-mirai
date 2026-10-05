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
});
