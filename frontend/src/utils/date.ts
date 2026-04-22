export function getMonthsElapsed(startDateStr: string): number {
  if (!startDateStr) return 0;
  const start = new Date(startDateStr);
  if (isNaN(start.getTime())) return 0;
  const now = new Date();
  
  const yearsDiff = now.getFullYear() - start.getFullYear();
  const monthsDiff = now.getMonth() - start.getMonth();
  
  let totalMonths = yearsDiff * 12 + monthsDiff;
  
  if (now.getDate() < start.getDate()) {
    totalMonths--;
  }
  
  return Math.max(0, totalMonths);
}
