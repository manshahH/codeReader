import type { AccuracyHistoryDay } from '../../lib/types';

interface Props {
  data: AccuracyHistoryDay[];
}

const WIDTH = 480;
const HEIGHT = 96;
const PAD = 4;

// A plain line, not a number -- the trend itself is the content. SVG with
// viewBox + no fixed pixel width, same responsive approach as
// ActivityHeatmap: scales to fill its container, never scrolls.
export function AccuracyLine({ data }: Props) {
  if (data.length < 2) {
    return <p className="text-sm text-ink-muted">Not enough data yet.</p>;
  }

  const points = data.map((day, i) => {
    const x = PAD + (i / (data.length - 1)) * (WIDTH - PAD * 2);
    const y = PAD + (1 - day.accuracy) * (HEIGHT - PAD * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const first = data[0];
  const last = data[data.length - 1];

  return (
    <div className="flex flex-col gap-1">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        style={{ width: '100%', height: 'auto', display: 'block' }}
        role="img"
        aria-label={`Daily accuracy from ${first.date} to ${last.date}`}
      >
        <line x1={PAD} y1={HEIGHT / 2} x2={WIDTH - PAD} y2={HEIGHT / 2} className="stroke-border" strokeWidth={1} strokeDasharray="2 3" />
        <polyline points={points.join(' ')} fill="none" className="stroke-action" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <div className="flex items-center justify-between font-code text-2xs text-ink-muted">
        <span>{first.date}</span>
        <span>{last.date}</span>
      </div>
    </div>
  );
}
