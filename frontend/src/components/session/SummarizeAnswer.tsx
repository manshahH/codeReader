import type { SessionExercisePayload } from '../../lib/types';

interface Props {
  payload: SessionExercisePayload;
  text: string;
  onChangeText: (text: string) => void;
}

function wordCount(text: string): number {
  const trimmed = text.trim();
  return trimmed.length === 0 ? 0 : trimmed.split(/\s+/).length;
}

export function SummarizeAnswer({ payload, text, onChangeText }: Props) {
  const maxWords = payload.max_words ?? 60;
  const count = wordCount(text);
  const overLimit = count > maxWords;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <label htmlFor="summary" className="mb-2 block text-sm text-ink-muted">
          Describe what this does, in one or two sentences.
        </label>
        <textarea
          id="summary"
          className="w-full rounded-soft border border-border bg-surface-reading p-4 font-explanation text-base leading-relaxed text-ink outline-none focus-visible:border-action"
          rows={4}
          value={text}
          onChange={(event) => onChangeText(event.target.value)}
        />
        <p className={`mt-2 text-sm ${overLimit ? 'text-incorrect' : 'text-ink-muted'}`} aria-live="polite">
          {count} / {maxWords} words{overLimit ? ' — over the limit' : ''}
        </p>
      </div>
    </div>
  );
}
