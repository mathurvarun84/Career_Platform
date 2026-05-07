/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: "#6c47ff",
        "brand-dark": "#1a1a2e",
        "brand-light": "#f7f5ff",
        "brand-border": "#c4b5fd",
      },
    },
  },
  plugins: [],
};
