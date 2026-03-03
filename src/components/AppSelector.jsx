import { apps } from '../data/mockData'

export default function AppSelector({ selectedApp, onSelect }) {
  return (
    <div className="flex items-center gap-4">
      <h1 className="font-heading text-2xl font-bold text-text-main">
        Analytics
      </h1>
      <select
        value={selectedApp}
        onChange={(e) => onSelect(e.target.value)}
        className="bg-card border border-border rounded-lg px-3 py-2 text-text-main text-sm focus:outline-none focus:border-accent cursor-pointer"
      >
        {apps.map((app) => (
          <option key={app.id} value={app.id}>
            {app.name}
          </option>
        ))}
      </select>
    </div>
  )
}
