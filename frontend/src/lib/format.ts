/** Format milliseconds as `m:ss.mmm` (Assetto Corsa style), mirroring the
 * legacy dashboard's `fmt()` in src/dashboard/static/index.html so lap times
 * read identically across both frontends during the migration. */
export function formatLapTime(ms: number | null | undefined): string {
  if (ms == null || ms <= 0 || !Number.isFinite(ms)) return '-:--.---'
  const minutes = Math.floor(ms / 60000)
  const seconds = Math.floor((ms % 60000) / 1000)
  const millis = Math.floor(ms % 1000)
  return `${minutes}:${String(seconds).padStart(2, '0')}.${String(millis).padStart(3, '0')}`
}

/** Format a signed delta in seconds with an explicit `+`/`-` sign, e.g. `+0.42`. */
export function formatSignedSeconds(value: number | null | undefined, decimals = 3): string {
  if (value == null || !Number.isFinite(value)) return '---'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}`
}
