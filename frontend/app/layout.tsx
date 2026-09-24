import type { Metadata } from "next";

import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Supply Chain Intelligence Platform",
  description: "Enterprise supply-chain analytics, ML risk prediction, and AI copilot",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
