import { GutterTick } from '../gutter/Gutter';
import type { SessionExercise } from '../../lib/types';

// Session progress rendered as gutter marks (docs/08b), not a progress bar.
export function SessionProgressRail({ exercises, currentIndex }: { exercises: SessionExercise[]; currentIndex: number }) {
  return (
    <div className="flex items-center gap-2" aria-label={`Exercise ${currentIndex + 1} of ${exercises.length}`}>
      {exercises.map((exercise, i) => (
        <GutterTick
          key={exercise.exercise_id}
          filled={exercise.attempted || i < currentIndex}
          boss={exercise.is_boss}
          label={`Slot ${exercise.slot}${exercise.is_boss ? ' (boss)' : ''}${exercise.attempted ? ', done' : ''}`}
        />
      ))}
    </div>
  );
}
