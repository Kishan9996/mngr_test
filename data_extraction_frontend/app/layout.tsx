import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Data Extraction Chatbot",
  description: "Natural-language queries over your ecommerce and support data",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
