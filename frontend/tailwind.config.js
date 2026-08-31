/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#0f172a",
        surface2: "#1e293b",
        accent: "#3b82f8",
        escalation: "#ef4444",
        ok: "#22c55e",
      },
    },
  },
  plugins: [],
};
