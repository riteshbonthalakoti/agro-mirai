import { splitAdvice } from '../adviceParsing';

// Field finding (2026-10-26): recommended_action text that arrives already
// numbered ("1. Prune... 2. Apply...") produced orphan steps that were
// nothing but a bare digit, because splitting on ". " also breaks right
// after each step's own number.
describe('splitAdvice', () => {
  it('drops orphan digit steps from a pre-numbered action string', () => {
    const raw =
      '1. Prune infected lower foliage with sterilized shears. ' +
      '2. Apply copper oxychloride or organic neem spray in early morning. ' +
      '3. Avoid overhead splashing. Use drip irrigation to minimize leaf wetness.';

    const { steps } = splitAdvice(raw);

    expect(steps).toEqual([
      'Prune infected lower foliage with sterilized shears',
      'Apply copper oxychloride or organic neem spray in early morning',
      'Avoid overhead splashing',
      'Use drip irrigation to minimize leaf wetness',
    ]);
  });

  it('still splits a plain, unnumbered sentence list normally', () => {
    const raw = 'Scout immediately. Remove badly hit leaves.';
    const { steps } = splitAdvice(raw);
    expect(steps).toEqual(['Scout immediately', 'Remove badly hit leaves']);
  });

  it('still parses "Other possibilities" and "Note" sections', () => {
    const raw = 'Scout immediately. Other possibilities: rust; blight. Note: confidence is low.';
    const { steps, others, note } = splitAdvice(raw);
    expect(steps).toEqual(['Scout immediately']);
    expect(others).toEqual(['rust', 'blight']);
    expect(note).toBe('confidence is low');
  });
});
