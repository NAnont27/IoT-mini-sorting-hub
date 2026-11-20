import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sorta · Mini Sorting Hub",
  description: "ศูนย์ควบคุมและติดตามระบบคัดแยกพัสดุ Mini Sorting Hub",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="th"><body>{children}</body></html>;
}
