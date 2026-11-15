import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Legion Quant Terminal",
  description: "Market research terminal: charting, indicators and rule-based scanning.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0a0d12" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
