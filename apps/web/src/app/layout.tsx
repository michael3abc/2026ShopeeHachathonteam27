import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "退貨案件工作台", description: "退貨案件 Agent 重建專案" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-Hant"><body>{children}</body></html>;
}
