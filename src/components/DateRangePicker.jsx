const presets = [
  { label: '7日', days: 7 },
  { label: '30日', days: 30 },
  { label: '90日', days: 90 },
]

export default function DateRangePicker({ rangeDays, onRangeChange, customStart, customEnd, onCustomChange }) {
  const isCustom = rangeDays === 0

  return (
    <div className="flex items-center gap-2">
      {presets.map((p) => (
        <button
          key={p.days}
          onClick={() => onRangeChange(p.days)}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            rangeDays === p.days
              ? 'bg-accent text-bg'
              : 'bg-card border border-border text-text-sub hover:text-text-main'
          }`}
        >
          {p.label}
        </button>
      ))}
      <button
        onClick={() => onRangeChange(0)}
        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
          isCustom
            ? 'bg-accent text-bg'
            : 'bg-card border border-border text-text-sub hover:text-text-main'
        }`}
      >
        カスタム
      </button>
      {isCustom && (
        <div className="flex items-center gap-2 ml-2">
          <input
            type="date"
            value={customStart}
            onChange={(e) => onCustomChange('start', e.target.value)}
            className="bg-card border border-border rounded-lg px-2 py-1.5 text-text-main text-sm focus:outline-none focus:border-accent"
          />
          <span className="text-text-sub">–</span>
          <input
            type="date"
            value={customEnd}
            onChange={(e) => onCustomChange('end', e.target.value)}
            className="bg-card border border-border rounded-lg px-2 py-1.5 text-text-main text-sm focus:outline-none focus:border-accent"
          />
        </div>
      )}
    </div>
  )
}
