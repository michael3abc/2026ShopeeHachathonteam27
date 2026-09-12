import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "ReturnFlow — 智慧退貨處理",
  description: "AI-assisted return resolution demo",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
