import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Calendar Scheduling Assistant",
  description: "Schedule appointments via Google Calendar and Outlook using natural language.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
