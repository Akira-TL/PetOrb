import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PetOrb Detection Workbench",
  description: "PetOrb 宠物口腔影像辅助风险观察",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
