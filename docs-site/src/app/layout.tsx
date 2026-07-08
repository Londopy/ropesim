import type { Metadata } from 'next';
import { DM_Sans, IBM_Plex_Mono, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import Navbar from '@/components/layout/Navbar';
import Footer from '@/components/layout/Footer';

const dmSans = DM_Sans({
  subsets: ['latin'],
  variable: '--font-dm-sans',
});
const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-plex-mono',
});
const jetbrains = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains',
});

export const metadata: Metadata = {
  title: {
    default: 'ropesim — climbing rope physics engine',
    template: '%s · ropesim',
  },
  description:
    'UIAA 101 / EN 892 fall physics in Rust, with a Python library, CLI, TUI, and native 3D desktop application.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      data-theme="dark"
      className={`${dmSans.variable} ${plexMono.variable} ${jetbrains.variable}`}
      suppressHydrationWarning
    >
      <body className="grain min-h-screen">
        <div className="topo-bg" aria-hidden />
        <Navbar />
        <main className="min-h-[calc(100vh-8rem)]">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
