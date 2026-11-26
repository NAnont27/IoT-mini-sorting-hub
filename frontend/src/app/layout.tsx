import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sorta · Mini Sorting Hub",
  description: "ศูนย์ควบคุมและติดตามระบบคัดแยกพัสดุ Mini Sorting Hub",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  // suppressHydrationWarning: browser extensions (e.g. Grammarly) add data-* attributes to
  // <body> before React hydrates. It only silences attribute diffs on <body> itself, not children.
  return <html lang="th"><body suppressHydrationWarning>{children}</body></html>;
}
