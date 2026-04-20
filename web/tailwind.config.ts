import type { Config } from "tailwindcss";
// Load at build time — tokens.json lives outside the TS rootDir so we use require
// eslint-disable-next-line @typescript-eslint/no-require-imports, @typescript-eslint/no-explicit-any
const tokens: any = require("../design/tokens.json");

// Extract hex value from a token leaf
function val(t: { value: string }): string {
  return t.value;
}

const { color, radius, shadow, transition } = tokens;

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Signal / stripboard colors
        day:      val(color.signal["day"]),
        dayInt:   val(color.signal["day-int"]),
        night:    val(color.signal["night"]),
        nightInt: val(color.signal["night-int"]),
        dusk:     val(color.signal["dusk"]),

        // Ink — plus opacity variants as explicit shades
        slate:    val(color.ink["slate"]),
        "slate-70": val(color.ink["slate-70"]),
        "slate-50": val(color.ink["slate-50"]),
        "slate-30": val(color.ink["slate-30"]),

        // Surface
        chalk:    val(color.surface["chalk"]),
        paper:    val(color.surface["paper"]),
        hair:     val(color.surface["hair"]),
        "hair-soft": val(color.surface["hair-soft"]),

        // Accent
        cueRed:    val(color.accent["cue-red"]),
        "cue-red-10": val(color.accent["cue-red-10"]),

        // DOOD status
        doodWork:   val(color.dood["work"]),
        doodHold:   val(color.dood["hold"]),
        doodTravel: val(color.dood["travel"]),
      },
      fontFamily: {
        serif:  ["var(--font-serif)", "Georgia", "serif"],
        sans:   ["var(--font-ui)", "-apple-system", "system-ui", "sans-serif"],
        mono:   ["var(--font-mono)", "ui-monospace", "monospace"],
        strip:  ["var(--font-strip)", "'Oswald'", "sans-serif"],
        erica:  ["var(--font-erica)", "'Oswald'", "sans-serif"],
      },
      borderRadius: {
        none: `${radius.none.value}px`,
        sm:   `${radius.sm.value}px`,
        md:   `${radius.md.value}px`,
        lg:   `${radius.lg.value}px`,
        pill: `${radius.pill.value}px`,
      },
      boxShadow: {
        none:  shadow.none.value,
        card:  shadow.card.value,
        modal: shadow.modal.value,
      },
      transitionDuration: {
        fast: transition.fast.value.split("ms")[0],
        base: transition.base.value.split("ms")[0],
      },
      maxWidth: {
        page: "1280px",
      },
    },
  },
  plugins: [],
};

export default config;
