import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "WhatsApp Booking CRM — multi-vertical booking automation",
  description:
    "Fill in your business details and a WhatsApp agent runs interactive booking conversations for clinics, dental, salons, hotels, restaurants, retail, travel and more.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Inter:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
          <Link href="/" className="font-[family-name:var(--font-display)] text-lg font-bold tracking-tight text-ink">
            wa<span className="text-accent">booking</span>
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            <Link href="/" className="rounded-lg px-3 py-1.5 font-medium text-ink-soft hover:bg-accent-wash hover:text-accent-ink">
              Builder
            </Link>
            <Link href="/inbox" className="rounded-lg px-3 py-1.5 font-medium text-ink-soft hover:bg-accent-wash hover:text-accent-ink">
              Inbox
            </Link>
            <Link href="/dashboard" className="rounded-lg px-3 py-1.5 font-medium text-ink-soft hover:bg-accent-wash hover:text-accent-ink">
              Dashboard
            </Link>
            <Link href="/settings" className="rounded-lg px-3 py-1.5 font-medium text-ink-soft hover:bg-accent-wash hover:text-accent-ink">
              Settings
            </Link>
            <a
              href="https://developers.facebook.com/docs/whatsapp/cloud-api"
              target="_blank"
              rel="noreferrer"
              className="rounded-lg px-3 py-1.5 font-medium text-ink-soft hover:bg-accent-wash hover:text-accent-ink"
            >
              Cloud API ↗
            </a>
          </nav>
        </header>
        {children}
        <footer className="mx-auto max-w-6xl px-5 py-10 text-center text-xs text-ink-soft">
          Multi-vertical WhatsApp booking automation · official Meta Cloud API · deterministic engine + Gemini/OpenAI
        </footer>
      </body>
    </html>
  );
}
