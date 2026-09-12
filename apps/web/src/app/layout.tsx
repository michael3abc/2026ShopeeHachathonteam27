import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "退貨案件工作台", description: "退貨案件審核、人工裁決與經驗學習工作台" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-Hant"><body>{children}</body></html>;
}
