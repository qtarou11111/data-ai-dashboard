import { useState, useMemo } from 'react'
import AppSelector from './AppSelector'
import DateRangePicker from './DateRangePicker'
import KPICard from './KPICard'
import MainChart from './MainChart'
import InstallChart from './InstallChart'
import { appData, filterByDateRange } from '../data/mockData'

const kpiConfig = [
  { key: 'dau', title: 'DAU', icon: '👤' },
  { key: 'wau', title: 'WAU', icon: '👥' },
  { key: 'mau', title: 'MAU', icon: '🌐' },
  { key: 'installs', title: 'Installs', icon: '📥' },
  { key: 'retention', title: 'Retention', icon: '🔄' },
  { key: 'stickiness', title: 'Stickiness', icon: '📌' },
]

function getDateRange(days) {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - days)
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0],
  }
}

export default function Dashboard() {
  const [selectedApp, setSelectedApp] = useState('ios')
  const [rangeDays, setRangeDays] = useState(30)
  const [customStart, setCustomStart] = useState('2025-01-01')
  const [customEnd, setCustomEnd] = useState('2025-03-01')

  const data = appData[selectedApp]

  const chartData = useMemo(() => {
    if (rangeDays > 0) {
      const { start, end } = getDateRange(rangeDays)
      return filterByDateRange(data.daily, start, end)
    }
    return filterByDateRange(data.daily, customStart, customEnd)
  }, [selectedApp, rangeDays, customStart, customEnd, data.daily])

  const handleCustomChange = (field, value) => {
    if (field === 'start') setCustomStart(value)
    else setCustomEnd(value)
  }

  return (
    <div className="max-w-[1440px] mx-auto px-6 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <AppSelector selectedApp={selectedApp} onSelect={setSelectedApp} />
        <DateRangePicker
          rangeDays={rangeDays}
          onRangeChange={setRangeDays}
          customStart={customStart}
          customEnd={customEnd}
          onCustomChange={handleCustomChange}
        />
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
        {kpiConfig.map((kpi) => (
          <KPICard
            key={kpi.key}
            title={kpi.title}
            value={data.kpis[kpi.key].value}
            change={data.kpis[kpi.key].change}
            icon={kpi.icon}
          />
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <MainChart data={chartData} />
        </div>
        <div>
          <InstallChart data={data.installs} />
        </div>
      </div>
    </div>
  )
}
