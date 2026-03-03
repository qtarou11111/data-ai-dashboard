export default function KPICard({ title, value, change, icon }) {
  const isUp = change >= 0
  return (
    <div className="bg-card border border-border rounded-xl p-5 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-text-sub text-sm">{title}</span>
        <span className="text-lg text-text-sub">{icon}</span>
      </div>
      <div className="font-number text-2xl font-medium text-text-main">
        {typeof value === 'number' && value > 1000
          ? value.toLocaleString()
          : value}
        {title === 'Retention' || title === 'Stickiness' ? '%' : ''}
      </div>
      <div className={`text-sm font-medium flex items-center gap-1 ${isUp ? 'text-up' : 'text-down'}`}>
        <span>{isUp ? '▲' : '▼'}</span>
        <span className="font-number">{Math.abs(change).toFixed(1)}%</span>
        <span className="text-text-sub text-xs ml-1">vs prev</span>
      </div>
    </div>
  )
}
