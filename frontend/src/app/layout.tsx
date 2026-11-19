import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mini Sorting Hub · Bench",
  description: "Dashboard สำหรับทดสอบระบบคัดแยกพัสดุบนโต๊ะ",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="th"><body>{children}</body></html>;
}
