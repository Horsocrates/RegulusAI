import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Regulus AI",
  description: "Structural Guardrail for LLM Reasoning",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
