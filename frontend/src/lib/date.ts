// Small date-string helpers, 'YYYY-MM-DD' throughout to match the backend's
// date-only fields (session_date, activity's from/to). Deliberately computed
// against a caller-supplied IANA timezone, not the browser's, so the
// activity grid's window matches the server's own local_date_for(tz).

export function todayInTimezone(timezone: string): string {
  // en-CA formats as YYYY-MM-DD, which is exactly the wire format we want.
  return new Intl.DateTimeFormat('en-CA', { timeZone: timezone }).format(new Date());
}

export function addDays(dateStr: string, days: number): string {
  const [year, month, day] = dateStr.split('-').map(Number);
  const d = new Date(Date.UTC(year, month - 1, day));
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
