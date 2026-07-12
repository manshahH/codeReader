import { addDays } from '../../lib/date';
import type { ActivityDay } from '../../lib/types';

interface Props {
  days: ActivityDay[];
  from: string; // 'YYYY-MM-DD', inclusive
  to: string;
}

type Cell = { date: string; completed: boolean } | 'none' | 'pad';

// GitHub-scale proportions (11px cell, 3px gap, 2px radius) -- deliberately
// NOT the 24px GutterCell: at these dimensions 53 weeks is ~762 viewBox
// units wide, and since this renders as an SVG with viewBox + width="100%"
// (no fixed pixel width), it scales to fill any container losslessly and
// NEVER needs a horizontal scrollbar, at 1440px or at 320px alike.
const CELL = 11;
const GAP = 3;
const STEP = CELL + GAP;
const RADIUS = 2;
const LABEL_COL_WIDTH = 24;
const MONTH_ROW_HEIGHT = 16;
const WEEKDAY_LABELS: Record<number, string> = { 1: 'Mon', 3: 'Wed', 5: 'Fri' };

function weekday(dateStr: string): number {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d)).getUTCDay();
}

function monthAbbrev(dateStr: string): string {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
}

// Sunday-aligned weeks, padded at both ends to full weeks. 'pad' (outside
// [from, to]) is distinct from 'none' (a real day in range with no
// daily_sessions row) -- conflating "before the window" with "skipped the
// app" would be a real correctness bug, not a cosmetic one.
function buildWeeks(days: ActivityDay[], from: string, to: string): Cell[][] {
  const byDate = new Map(days.map((d) => [d.session_date, d.completed]));
  const start = addDays(from, -weekday(from));
  const end = addDays(to, 6 - weekday(to));

  const cells: Cell[] = [];
  for (let cursor = start; cursor <= end; cursor = addDays(cursor, 1)) {
    if (cursor < from || cursor > to) {
      cells.push('pad');
    } else if (byDate.has(cursor)) {
      cells.push({ date: cursor, completed: byDate.get(cursor) as boolean });
    } else {
      cells.push('none');
    }
  }

  const weeks: Cell[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return weeks;
}

// D-99: a blue-intensity contribution grid -- hollow (no session) / tinted
// fill (opened, not finished) / solid fill (completed), all --color-action,
// never green. Month labels across the top, weekday labels down the left,
// matching the GitHub spatial convention without its color convention.
export function ActivityHeatmap({ days, from, to }: Props) {
  const weeks = buildWeeks(days, from, to);
  const width = LABEL_COL_WIDTH + weeks.length * STEP;
  const height = MONTH_ROW_HEIGHT + 7 * STEP;

  let lastMonth = '';
  const monthLabels: { x: number; label: string }[] = [];
  weeks.forEach((week, wi) => {
    const firstReal = week.find((c): c is Exclude<Cell, 'pad'> => c !== 'pad');
    if (!firstReal || firstReal === 'none') return;
    const label = monthAbbrev(firstReal.date);
    if (label !== lastMonth) {
      lastMonth = label;
      monthLabels.push({ x: LABEL_COL_WIDTH + wi * STEP, label });
    }
  });

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      style={{ width: '100%', height: 'auto', display: 'block' }}
      role="img"
      aria-label={`Activity heatmap, ${from} to ${to}`}
    >
      {monthLabels.map(({ x, label }) => (
        <text key={x} x={x} y={11} className="fill-ink-muted font-ui" fontSize={9}>
          {label}
        </text>
      ))}
      {Object.entries(WEEKDAY_LABELS).map(([row, label]) => (
        <text
          key={row}
          x={0}
          y={MONTH_ROW_HEIGHT + Number(row) * STEP + CELL - 2}
          className="fill-ink-muted font-ui"
          fontSize={9}
        >
          {label}
        </text>
      ))}
      {weeks.map((week, wi) =>
        week.map((cell, di) => {
          if (cell === 'pad') return null;
          const x = LABEL_COL_WIDTH + wi * STEP;
          const y = MONTH_ROW_HEIGHT + di * STEP;
          if (cell === 'none') {
            return (
              <rect
                key={di}
                x={x}
                y={y}
                width={CELL}
                height={CELL}
                rx={RADIUS}
                fill="none"
                className="stroke-border"
              >
                <title>No session</title>
              </rect>
            );
          }
          return (
            <rect
              key={di}
              x={x}
              y={y}
              width={CELL}
              height={CELL}
              rx={RADIUS}
              className={cell.completed ? 'fill-action' : 'fill-action-tint'}
            >
              <title>
                {cell.date}: {cell.completed ? 'completed' : 'opened, not completed'}
              </title>
            </rect>
          );
        }),
      )}
    </svg>
  );
}
