/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#04060A',
          900: '#070A10',
          850: '#0A0E16',
          800: '#0D121C',
          700: '#121928',
          600: '#1A2336',
        },
        line: 'rgba(148, 163, 184, 0.12)',
        lineBright: 'rgba(148, 163, 184, 0.22)',
        fog: {
          50: '#F2F5F9',
          100: '#E2E8F0',
          300: '#B7C1D1',
          400: '#94A3B8',
          500: '#74809A',
          600: '#5A657E',
        },
        accent: {
          DEFAULT: '#2DD4BF',
          bright: '#5EEAD4',
          dim: '#14B8A6',
          deep: '#0F766E',
        },
        quantum: {
          DEFAULT: '#8B7CF6',
          bright: '#A99DFF',
          dim: '#6D5BD8',
        },
        amber: {
          soft: '#FBBF24',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'Inter', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      letterSpacing: {
        tightest: '-0.04em',
        widest2: '0.22em',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(18px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'orbit-slow': {
          from: { transform: 'rotate(0deg)' },
          to: { transform: 'rotate(360deg)' },
        },
        'pulse-ring': {
          '0%': { opacity: '0.5', transform: 'scale(0.9)' },
          '70%': { opacity: '0', transform: 'scale(1.6)' },
          '100%': { opacity: '0', transform: 'scale(1.6)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-400px 0' },
          '100%': { backgroundPosition: '400px 0' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.25' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.7s cubic-bezier(0.22, 1, 0.36, 1) both',
        'fade-in': 'fade-in 0.9s ease both',
        'orbit-slow': 'orbit-slow 14s linear infinite',
        'orbit-fast': 'orbit-slow 7s linear infinite reverse',
        'pulse-ring': 'pulse-ring 3s ease-out infinite',
        shimmer: 'shimmer 1.8s linear infinite',
        blink: 'blink 1.2s steps(1) infinite',
      },
    },
  },
  plugins: [],
}
