import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-card border border-border rounded-lg p-3 shadow-xl">
      <p className="text-text-sub text-xs mb-2">{label}</p>
      {payload.map((entry) => (
        <p key={entry.name} className="font-number text-sm" style={{ color: entry.color }}>
          {entry.name}: {entry.value.toLocaleString()}
        </p>
      ))}
    </div>
  )
}

export default function MainChart({ data }) {
  return (
    <div className="bg-card border border-border rounded-xl p-5 h-full">
      <h2 className="font-heading text-lg font-semibold text-text-main mb-4">
        DAU / WAU / MAU
      </h2>
      <ResponsiveContainer width="100%" height={320}>
        <AreaChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <defs>
            <linearGradient id="gradDAU" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00e676" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#00e676" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gradWAU" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#7c3aed" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#7c3aed" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gradMAU" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: '#1e293b' }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 12, color: '#94a3b8' }}
          />
          <Area type="monotone" dataKey="dau" name="DAU" stroke="#00e676" fill="url(#gradDAU)" strokeWidth={2} dot={false} />
          <Area type="monotone" dataKey="wau" name="WAU" stroke="#7c3aed" fill="url(#gradWAU)" strokeWidth={2} dot={false} />
          <Area type="monotone" dataKey="mau" name="MAU" stroke="#00d4ff" fill="url(#gradMAU)" strokeWidth={2} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
