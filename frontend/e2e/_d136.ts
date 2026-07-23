// D-136 TEMPORARY tolerance -- NOT a fix. See docs/07-decisions.md D-136.
//
// Two continuation-row specs are intermittently flaky in CI: they pass on some
// runs and fail on others with a transient `[pageerror] Cannot use 'in'
// operator ... 'explanation'`, never deterministically (playwright was green on
// commit 121fe4b, red on the next two with the SAME frontend code). Fixing them
// needs the D-136 campaign (25-30 clean runs plus the continuation-row
// group-ordering work) and is out of scope for now.
//
// Until then, ONLY the two tagged tests run in a dedicated Playwright project
// WITH retries, so a FLAKE is tolerated (green, reported as flaky) while a
// CONSISTENT failure still fails every retry (red). Every OTHER spec runs with
// retries 0, so a genuinely new regression is visible immediately -- which is
// the whole point (guarding against the D-103/D-152 "a red job nobody reads"
// decay). Tag a third spec and it is tolerated too, but that is a visible,
// recorded edit, never silent.
//
// This tolerance EXPIRES so it cannot become permanent by inattention: past the
// date the tagged specs get retries 0 and any flake turns the job red, forcing
// the campaign or a deliberate renewal.

export const D136_TAG = '@d136-flaky';
export const D136_TOLERANCE_EXPIRES = '2026-09-15';
export const D136_RETRIES = 3;

export function d136Retries(now: Date = new Date()): number {
  if (now >= new Date(D136_TOLERANCE_EXPIRES)) {
    console.warn(
      `D-136 retry tolerance EXPIRED (${D136_TOLERANCE_EXPIRES}). The ${D136_TAG} ` +
        `specs now fail the job on any flake. Fix D-136 or renew the expiry in _d136.ts.`,
    );
    return 0;
  }
  console.warn(
    `D-136 retry tolerance ACTIVE until ${D136_TOLERANCE_EXPIRES}: ${D136_TAG} specs ` +
      `get ${D136_RETRIES} retries (temporary, not a fix). Every other spec has retries 0.`,
  );
  return D136_RETRIES;
}
