import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dbe6fe",
          500: "#4f7cf7",
          600: "#3b5fe0",
          700: "#2f4bc0",
          900: "#1e2f75",
        },
      },
    },
  },
  plugins: [],
};
export default config;
