import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "News Summarizer",
  description: "Authenticated RAG-powered news article summarizer and Q&A",
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
