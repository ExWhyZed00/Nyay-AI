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

// Runs before the page is drawn, so a saved light/dark choice is applied without a flash.
const themeScript = `(function(){try{var t=localStorage.getItem("nyay-theme");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t);}}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
