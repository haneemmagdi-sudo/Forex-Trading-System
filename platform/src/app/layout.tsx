import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { arSA } from "@clerk/localizations";
import "./globals.css";

export const metadata: Metadata = {
  title: "Quantum Forex AI — منصة التداول الذكي",
  description: "نظام تداول الفوركس بالذكاء الاصطناعي — 4 وكلاء ذكاء اصطناعي يعملون معاً لتحقيق أفضل النتائج",
  keywords: ["تداول الفوركس", "ذكاء اصطناعي", "MT5", "Forex AI"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider localization={arSA}>
      <html lang="ar" dir="rtl">
        <head>
          <link rel="preconnect" href="https://fonts.googleapis.com" />
          <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
          <link
            href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;500;600;700;800;900&family=Tajawal:wght@300;400;500;700;800&display=swap"
            rel="stylesheet"
          />
        </head>
        <body className="antialiased">
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
