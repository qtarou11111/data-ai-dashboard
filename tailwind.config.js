/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: '#0a0e1a',
        card: '#111827',
        border: '#1e293b',
        accent: '#00d4ff',
        dau: '#00e676',
        wau: '#7c3aed',
        mau: '#00d4ff',
        up: '#00e676',
        down: '#ef4444',
        'text-main': '#f1f5f9',
        'text-sub': '#94a3b8',
      },
      fontFamily: {
        syne: ['Syne', 'sans-serif'],
        mono: ['DM Mono', 'monospace'],
        inter: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
