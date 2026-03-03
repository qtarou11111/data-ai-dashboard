function generateDailyData(startDate, days, baseDAU, baseWAU, baseMAU) {
  const data = []
  const start = new Date(startDate)
  for (let i = 0; i < days; i++) {
    const date = new Date(start)
    date.setDate(start.getDate() + i)
    const noise = () => (Math.random() - 0.5) * 0.15
    const trend = 1 + i * 0.002
    data.push({
      date: date.toISOString().split('T')[0],
      dau: Math.round(baseDAU * trend * (1 + noise())),
      wau: Math.round(baseWAU * trend * (1 + noise())),
      mau: Math.round(baseMAU * trend * (1 + noise())),
    })
  }
  return data
}

function generateMonthlyInstalls(months, base) {
  const data = []
  const now = new Date()
  for (let i = months - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const label = d.toLocaleDateString('ja-JP', { year: 'numeric', month: 'short' })
    const noise = () => (Math.random() - 0.5) * 0.2
    data.push({
      month: label,
      installs: Math.round(base * (1 + noise()) * (1 + (months - i) * 0.03)),
    })
  }
  return data
}

export const apps = [
  { id: 'ios', name: 'MyApp iOS' },
  { id: 'android', name: 'MyApp Android' },
  { id: 'web', name: 'MyApp Web' },
]

export const appData = {
  ios: {
    daily: generateDailyData('2024-10-01', 180, 12000, 45000, 120000),
    installs: generateMonthlyInstalls(12, 28000),
    kpis: {
      dau: { value: 14520, change: 8.3 },
      wau: { value: 52300, change: 5.1 },
      mau: { value: 138000, change: 3.7 },
      installs: { value: 31200, change: 12.4 },
      retention: { value: 42.5, change: -1.2 },
      stickiness: { value: 27.8, change: 2.1 },
    },
  },
  android: {
    daily: generateDailyData('2024-10-01', 180, 18000, 62000, 185000),
    installs: generateMonthlyInstalls(12, 45000),
    kpis: {
      dau: { value: 21400, change: 11.2 },
      wau: { value: 71800, change: 7.5 },
      mau: { value: 203000, change: 5.9 },
      installs: { value: 52800, change: 15.7 },
      retention: { value: 38.2, change: -2.8 },
      stickiness: { value: 29.7, change: 3.4 },
    },
  },
  web: {
    daily: generateDailyData('2024-10-01', 180, 8000, 28000, 75000),
    installs: generateMonthlyInstalls(12, 15000),
    kpis: {
      dau: { value: 9200, change: 6.1 },
      wau: { value: 32100, change: 4.3 },
      mau: { value: 82000, change: 2.8 },
      installs: { value: 17500, change: 9.2 },
      retention: { value: 35.8, change: 0.5 },
      stickiness: { value: 28.5, change: 1.8 },
    },
  },
}

export function filterByDateRange(daily, startDate, endDate) {
  return daily.filter((d) => d.date >= startDate && d.date <= endDate)
}
