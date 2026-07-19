import {
  CODE_SCALE_MAX,
  CODE_SCALE_MIN,
  CODE_SCALE_STEP,
  useCodeScale,
  useWrapPreference,
  type WrapPreference,
} from '../lib/code/viewerPreferences';

/**
 * Reading preferences: how code is displayed (D-132).
 *
 * These lived as a control strip above the code in the session player. They
 * are here now, and the reasoning is docs/08's, not convenience: "The session
 * player is a single focused column: context note, code (the hero of every
 * screen), answer control, nothing else competing." A permanent controls row
 * is a fourth element competing, and it competed at the worst possible place --
 * directly above the code, at the width where every vertical pixel is a line of
 * code the reader cannot see. It cost ~36px, which at the reading line-height
 * is about one and a half lines, on every exercise, forever.
 *
 * Both are set-once preferences, which is what makes moving them cheap:
 *   - Code size is a vision/comfort setting. Nobody changes it per exercise.
 *   - Wrap defaults to `auto`, which already resolves correctly by width (wrap
 *     on a phone, scroll on a desktop). The override exists for the reader who
 *     disagrees with that default -- once -- not for per-exercise switching.
 *
 * The cost is discoverability, and it is the right cost to pay: the default is
 * correct for almost everyone, so the control is rarely needed, and a rarely
 * needed control does not belong in the reading surface.
 */
export function ReadingPreferences() {
  const { preference, mode, setPreference } = useWrapPreference();
  const { scale, setScale } = useCodeScale();

  const OPTIONS: { value: WrapPreference; label: string; hint: string }[] = [
    { value: 'auto', label: 'Auto', hint: 'Wrap on narrow screens, scroll on wide ones' },
    { value: 'wrap', label: 'Wrap', hint: 'Never scroll sideways' },
    { value: 'scroll', label: 'Scroll', hint: 'Keep every line on one row' },
  ];

  return (
    <section className="flex flex-col gap-4 rounded-soft border border-border bg-surface-raised p-6">
      <p className="shrink-0 text-sm text-ink-muted">Reading</p>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm text-ink">Long lines</legend>
        {OPTIONS.map((option) => (
          <label
            key={option.value}
            className={`flex min-h-tap cursor-pointer items-center gap-3 rounded-soft border px-4 py-2 text-sm transition-colors duration-fast ${
              preference === option.value ? 'border-action bg-action-tint' : 'border-border'
            }`}
          >
            <input
              type="radio"
              name="wrap-preference"
              checked={preference === option.value}
              onChange={() => setPreference(option.value)}
            />
            <span className="flex min-w-0 flex-col">
              <span className="text-ink">
                {option.label}
                {option.value === 'auto' ? (
                  <span className="ml-2 font-code text-2xs text-ink-muted">currently {mode}</span>
                ) : null}
              </span>
              <span className="text-xs text-ink-muted">{option.hint}</span>
            </span>
          </label>
        ))}
      </fieldset>

      <div className="flex flex-col gap-2">
        <p className="text-sm text-ink">Code size</p>
        <div className="flex items-center gap-3" role="group" aria-label="Code size">
          <button
            type="button"
            onClick={() => setScale(scale - CODE_SCALE_STEP)}
            disabled={scale <= CODE_SCALE_MIN + 0.001}
            aria-label="Smaller code"
            className="min-h-tap min-w-tap rounded-soft border border-border font-code text-sm text-ink transition-colors duration-fast hover:border-action hover:text-action disabled:opacity-40"
          >
            A−
          </button>
          <button
            type="button"
            onClick={() => setScale(scale + CODE_SCALE_STEP)}
            disabled={scale >= CODE_SCALE_MAX - 0.001}
            aria-label="Larger code"
            className="min-h-tap min-w-tap rounded-soft border border-border font-code text-base text-ink transition-colors duration-fast hover:border-action hover:text-action disabled:opacity-40"
          >
            A+
          </button>
          <span className="font-code text-2xs tabular-nums text-ink-muted">{Math.round(scale * 100)}%</span>
        </div>
        {/* A live sample, so the setting is judged against code rather than
            against a number. The gutter is part of the sample because it is
            part of what the size changes. */}
        <div className="mt-1 flex overflow-hidden rounded-soft border border-border bg-surface-reading">
          <span className="shrink-0 select-none border-r border-border bg-surface-raised px-3 py-2 text-right font-code text-code leading-code tabular-nums text-ink-muted">
            1
          </span>
          <code className="min-w-0 flex-1 overflow-x-auto px-4 py-2 font-code text-code leading-code text-ink">
            for item in basket: total += item.price
          </code>
        </div>
      </div>
    </section>
  );
}
