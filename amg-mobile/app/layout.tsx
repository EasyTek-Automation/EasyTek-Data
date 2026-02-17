import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AMG Data Mobile",
  description: "Interface mobile para AMG Data - Monitoramento industrial",
  viewport: "width=device-width, initial-scale=1, maximum-scale=1",
  themeColor: "#78C2AD",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className="antialiased bg-gray-50">
        {children}
      </body>
    </html>
  );
}
