/** @type {import('tailwindcss').Config} */
module.exports = {
  corePlugins: {
    preflight: false,
  },
  content: ["./index.html", "./src/**/*.{vue,ts,tsx,js}"],
  theme: {
    extend: {},
  },
  plugins: [],
};
