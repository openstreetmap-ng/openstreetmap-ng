export const olderThan = (count: number, unit: string, now = new Date()) => {
  const cutoff = new Date(now)
  if (unit === "days" || unit === "weeks") {
    cutoff.setUTCDate(cutoff.getUTCDate() - count * (unit === "weeks" ? 7 : 1))
  } else {
    const day = cutoff.getUTCDate()
    cutoff.setUTCDate(1)
    cutoff.setUTCMonth(cutoff.getUTCMonth() - count * (unit === "years" ? 12 : 1))
    const lastDay = new Date(cutoff)
    lastDay.setUTCMonth(lastDay.getUTCMonth() + 1, 0)
    cutoff.setUTCDate(Math.min(day, lastDay.getUTCDate()))
  }
  // The server's upper bound is inclusive, while "older than" is strict.
  return BigInt(Math.max(0, Math.ceil(cutoff.getTime() / 1000) - 1))
}
