export function pluralizeDays(count: number): string {
  return `${count} ${count === 1 ? 'day' : 'days'}`;
}

export function formatRelativeDate(iso: string): string {
  const diffDays = Math.round((new Date(iso).getTime() - Date.now()) / (24 * 60 * 60 * 1000));
  if (diffDays < 0) return 'overdue';
  if (diffDays === 0) return 'due today';
  if (diffDays === 1) return 'due tomorrow';
  return `due in ${diffDays} days`;
}
