/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Primary colors (same for both modes)
        primary: {
          DEFAULT: '#6366F1', // Indigo 500
          hover: '#4F46E5',   // Indigo 600
        },
        // Light mode colors (default)
        bg: {
          primary: '#FFFFFF',     // White
          secondary: '#F1F5F9',   // Slate 100
          card: '#E2E8F0',       // Slate 200
        },
        text: {
          primary: '#1E293B',    // Slate 800
          secondary: '#64748B',   // Slate 500
        },
        // Semantic colors (same for both modes)
        success: '#22C55E',      // Green 500
        error: '#EF4444',        // Red 500
        warning: '#F59E0B',       // Amber 500
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bounce-subtle': 'bounceSubtle 1s ease-in-out infinite',
      },
      keyframes: {
        bounceSubtle: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5%)' },
        }
      }
    },
  },
  plugins: [],
}
