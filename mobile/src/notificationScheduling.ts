/** Pure notification scheduling decision logic.
 * Given account and field state, decide whether to schedule a daily reminder.
 * Separated from side effects (actual scheduling) for testability. */

export type SchedulingInput = {
  accountSignedIn: boolean;
  fieldId: string | null;
  adviceText: string | null;
};

export type SchedulingDecision = {
  shouldSchedule: boolean;
  reason: string;
};

/** Pure function: decide if a daily reminder should be scheduled.
 * Returns false if: no account signed in, no field, or no cached advice.
 * Returns true only if all prerequisites are met. */
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
  return { shouldSchedule: true, reason: 'ready' };
}
