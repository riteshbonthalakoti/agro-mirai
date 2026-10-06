/** Pure notification scheduling decision logic.
 * Given account and field state, decide whether to schedule a daily reminder.
 * Separated from side effects (actual scheduling) for testability. */

export type SchedulingInput = {
  accountSignedIn: boolean;
  fieldId: string | null;
  adviceText: string | null;
  reminderEnabled?: boolean;
};

export type SchedulingDecision = {
  shouldSchedule: boolean;
  reason: string;
  timeMinutes?: number;
};

/** Pure function: decide if a daily reminder should be scheduled.
 * Returns false if: no account signed in, no field, no cached advice, or reminders disabled.
 * Returns true with timeMinutes only if all prerequisites are met and reminders enabled. */
export function shouldScheduleDailyReminder(input: SchedulingInput): SchedulingDecision {
  if (!input.accountSignedIn) {
    return { shouldSchedule: false, reason: 'noAccount' };
  }
  if (!input.fieldId) {
    return { shouldSchedule: false, reason: 'noField' };
  }
  if (!input.adviceText) {
    return { shouldSchedule: false, reason: 'noAdvice' };
  }
  if (input.reminderEnabled === false) {
    return { shouldSchedule: false, reason: 'remindersDisabled' };
  }
  return { shouldSchedule: true, reason: 'ready', timeMinutes: 7 * 60 };
}
