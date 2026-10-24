import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nyay AI: Indian law in your language",
  description:
    "Ask questions about the Bharatiya Nyaya Sanhita, the Bharatiya Nagarik Suraksha Sanhita and the Constitution of India. Get answers with the exact sections cited.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
