/** @type {import('tailwindcss').Config} */
export default {
  // Fix P1-1: Disable Tailwind preflight to prevent CSS reset from breaking Naive UI components
  corePlugins: {
    preflight: false,
  },
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Stripe Design System Colors
        stripe: {
          purple: '#533afd',
          'purple-hover': '#4434d4',
          'purple-deep': '#2e2b8c',
          'purple-light': '#b9b9f9',
          'purple-mid': '#665efd',
          navy: '#061b31',
          'dark-navy': '#0d253d',
          'brand-dark': '#1c1e54',
          slate: '#64748d',
          'dark-slate': '#273951',
          green: '#15be53',
          'green-text': '#108c3d',
          'green-light': 'rgba(21,190,83,0.2)',
          ruby: '#ea2261',
          magenta: '#f96bee',
          'magenta-light': '#ffd7ef',
          lemon: '#9b6829',
          border: '#e5edf5',
          'border-purple': '#b9b9f9',
          'border-soft-purple': '#d6d9fc',
        },
        // Legacy brand alias mapped to Stripe purple for compatibility
        brand: {
          50: '#f6f5ff',
          100: '#eeebff',
          200: '#d6d0ff',
          300: '#b9b0ff',
          400: '#9687ff',
          500: '#533afd',
          600: '#4434d4',
          700: '#3529ab',
          800: '#2e2b8c',
          900: '#1c1e54',
        },
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          "'SF Pro Text'",
          "'SF Pro Display'",
          "'PingFang SC'",
          "'Hiragino Sans GB'",
          "'Microsoft YaHei'",
          'sans-serif',
        ],
      },
      borderRadius: {
        'stripe': '8px',
        'stripe-sm': '6px',
        'stripe-xs': '4px',
      },
      boxShadow: {
        'stripe': 'rgba(50,50,93,0.25) 0px 13px 27px -5px, rgba(0,0,0,0.1) 0px 8px 16px -8px',
        'stripe-hover': 'rgba(50,50,93,0.25) 0px 30px 45px -30px, rgba(0,0,0,0.1) 0px 18px 36px -18px',
        'stripe-ambient': 'rgba(23,23,23,0.08) 0px 15px 35px 0px',
        'stripe-soft': 'rgba(23,23,23,0.06) 0px 3px 6px',
        'stripe-glow': '0 0 20px rgba(83,58,253,0.25)',
      },
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
      },
      transitionTimingFunction: {
        'apple': 'cubic-bezier(0.4, 0.0, 0.2, 1)',
      },
    },
  },
  plugins: [],
  safelist: [
    // YOY 红涨绿跌色块（Naive UI render 函数动态生成，JIT 无法静态分析）
    'tw-inline-flex',
    'tw-items-center',
    'tw-px-1',
    'tw-py-[2px]',
    'tw-rounded',
    'tw-bg-\\[\\#fef0f0\\]',
    'tw-bg-\\[\\#e8f8ee\\]',
    'tw-text-\\[\\#ea2261\\]',
    'tw-text-\\[\\#15be53\\]',
    'tw-text-\\[13px\\]',
    'tw-font-medium',
  ],
}
