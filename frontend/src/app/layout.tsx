import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nursify MedSpa AI",
  description: "Daily financial reporting for your med spa",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  );
}
