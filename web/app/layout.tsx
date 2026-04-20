import "./globals.css";
import type { Metadata } from "next";
import {
  IBM_Plex_Serif,
  IBM_Plex_Mono,
  Big_Shoulders_Display,
  Erica_One,
  Inter,
} from "next/font/google";
import Providers from "@/components/ui/Providers";

const ibmPlexSerif = IBM_Plex_Serif({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  variable: "--font-serif",
  display: "swap",
});
const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});
const bigShoulders = Big_Shoulders_Display({
  subsets: ["latin"],
  weight: ["500", "700", "800"],
  variable: "--font-strip",
  display: "swap",
});
const ericaOne = Erica_One({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-erica",
  display: "swap",
});
const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-ui",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Cue — Pre-production",
  description: "Pre-production, the way the room works.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const fontVars = [
    ibmPlexSerif.variable,
    ibmPlexMono.variable,
    bigShoulders.variable,
    ericaOne.variable,
    inter.variable,
  ].join(" ");

  return (
    <html lang="en" className={fontVars}>
      <body className="min-h-screen">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
