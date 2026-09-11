/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Space Grotesk"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        ink: {
          950: "#070b11",
          900: "#0a0e14",
          850: "#0d131b",
          800: "#111927",
          700: "#1a2534",
          600: "#26344a",
        },
        teal: { DEFAULT: "#2dd4bf", soft: "#7ff0e3" },
        amber: { DEFAULT: "#fbbf24" },
        rose: { DEFAULT: "#fb7185" },
        violet: { DEFAULT: "#a78bfa" },
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(45,212,191,0.25), 0 8px 40px -12px rgba(45,212,191,0.35)",
      },
      keyframes: {
        dash: { to: { strokeDashoffset: "0" } },
        pulseGlow: {
          "0%,100%": { opacity: "0.4" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        pulseGlow: "pulseGlow 2.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
