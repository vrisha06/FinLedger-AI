/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        parchment: {
          DEFAULT: '#F4F0E5',
          50: '#FAF8F2',
          100: '#F4F0E5',
          200: '#EAE4D3',
          300: '#DFD8C1',
        },
        oat: {
          DEFAULT: '#EAE2D2',
          100: '#F5F0E6',
          200: '#EAE2D2',
          300: '#DDD2BD',
        },
        paper: {
          50: '#FFFEFA',
          100: '#F4F0E5',
          200: '#EAE4D3',
          300: '#DFD8C1',
        },
        surface: {
          DEFAULT: '#FFFEFA',
          elevated: '#FFFFFF',
          muted: '#F4F0E5',
        },
        ink: {
          950: '#141A15',
          900: '#202822',
          800: '#2F3A32',
          700: '#465349',
          600: '#526057', // Secondary ink
          500: '#758579',
          400: '#94A298',
          300: '#B8C3BC',
          200: '#D6DED9',
          100: '#E8EFEA',
        },
        forest: {
          950: '#0C271E',
          900: '#103B2E', // Dark evergreen
          800: '#174B3A', // Deep forest (signature reference)
          700: '#206A4C', // Primary evergreen
          600: '#287756', // Rich green / Confirmed success
          500: '#34936D',
          400: '#4CAE86',
          300: '#8ACDB0',
          200: '#C7D8BF', // Pale moss
          100: '#E0EADF', // Soft sage
          50: '#F0F6F0',
        },
        sage: {
          DEFAULT: '#DCE8D8',
          50: '#F4F8F4',
          100: '#EAF1E6', // Soft green mist
          200: '#DCE8D8', // Pale sage
          300: '#C7D8BF',
          400: '#9EB9A0', // Muted eucalyptus
          500: '#5F896F', // Medium sage-green
        },
        eucalyptus: {
          DEFAULT: '#9EB9A0',
          50: '#F2F7F2',
          100: '#E2EDE3',
          200: '#C5DCC6',
          300: '#9EB9A0',
          400: '#7FA382',
          500: '#5F896F',
        },
        mist: {
          DEFAULT: '#EAF1E6',
          50: '#F4F8F2',
          100: '#EAF1E6',
          200: '#DCE8D8',
          300: '#CDDFCA',
        },
        gold: {
          DEFAULT: '#B08A45', // Muted gold
          50: '#FDFBF7',
          100: '#F8F3E5',
          200: '#EEDEA8',
          300: '#DFD0A8',
          800: '#8A6926',
        },
        copper: {
          900: '#693820',
          800: '#8E4D2C',
          700: '#AD6945', // Burnished copper
          600: '#C57E58',
          500: '#D7936E',
          400: '#E3AC8D',
          300: '#ECC6AE',
          200: '#EEDDCF', // Warm clay
          100: '#F7EDE6',
          50: '#FCF7F3',
        },
        moss: {
          DEFAULT: '#C7D8BF',
          100: '#E0EADF',
          200: '#C7D8BF',
          300: '#AEC4A3',
        },
        clay: {
          DEFAULT: '#EEDDCF',
          100: '#F7EDE6',
          200: '#EEDDCF',
          300: '#E3CBB8',
        },
        hairline: {
          subtle: '#E2E0D4',
          DEFAULT: '#C9C8BB',
          strong: '#B4B2A0',
          forest: '#174B3A',
          sage: '#9EB9A0',
        },
        semantic: {
          success: '#287756',
          warning: '#95611C',
          danger: '#B44747',
        },
        forensic: {
          950: '#08100C',
          900: '#0D1813',
          850: '#11221B',
          800: '#162C23',
          750: '#1D382D',
          700: '#25473A',
          border: '#25473A',
          borderSub: '#162C23',
          amber: '#95611C',
          crimson: '#B44747',
          sage: '#287756',
          violet: '#8E5BB5',
        },
      },
      fontFamily: {
        serif: ['Newsreader', 'Georgia', 'Cambria', 'Times New Roman', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'IBM Plex Mono', 'Menlo', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'atelier': '0 1px 4px 0 rgba(32, 40, 34, 0.08), 0 1px 2px -1px rgba(32, 40, 34, 0.06)',
        'atelier-md': '0 4px 10px -2px rgba(32, 40, 34, 0.10), 0 2px 5px -2px rgba(32, 40, 34, 0.06)',
        'atelier-lg': '0 12px 24px -4px rgba(32, 40, 34, 0.12), 0 4px 8px -4px rgba(32, 40, 34, 0.06)',
        'hero': '0 10px 32px -6px rgba(23, 75, 58, 0.35)',
      }
    },
  },
  plugins: [],
}
