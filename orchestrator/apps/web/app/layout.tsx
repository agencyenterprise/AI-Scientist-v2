import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { Providers } from "./providers"
import Link from "next/link"

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans"
})

export const metadata: Metadata = {
  title: "AI Scientist Orchestrator",
  description:
    "Monitor AI scientist hypotheses, runs, validations, and artifacts powered by MongoDB state."
}

export const dynamic = "force-dynamic"

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.variable} bg-slate-950 text-slate-100`}>
        <Providers>
          <div className="flex min-h-screen flex-col">
            <Header />
            <main className="flex-1 px-8 py-6">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  )
}

function Header() {
  return (
    <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-8 py-4">
        <Link href="/" className="text-lg font-semibold text-white">
          AI Scientist Orchestrator
        </Link>
        <nav className="flex items-center gap-6 text-sm text-slate-300">
          <Link className="hover:text-white" href="/runs">
            Runs
          </Link>
          <Link className="hover:text-white" href="/hypotheses">
            Hypotheses
          </Link>
          <Link className="hover:text-white" href="/validations/queue">
            Validation Queue
          </Link>
        </nav>
      </div>
    </header>
  )
}
