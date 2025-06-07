import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Website Cloner - AI-Powered Website Cloning Tool",
  description: "Clone any website's design with AI. Enter a URL and get a complete HTML recreation that matches the original aesthetics.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
