import type { Metadata } from "next";
import { Be_Vietnam_Pro, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import { AuthProvider } from "@/lib/auth-context";
import { Toaster } from "@/components/ui/Toaster";
import "./globals.css";

// subsets gồm "vietnamese" — nội dung ứng dụng chủ yếu tiếng Việt có dấu, cần glyph đầy đủ hơn
// "latin" đơn thuần (khác baolong vốn không có yêu cầu tiếng Việt chặt bằng).
const fontDisplay = Be_Vietnam_Pro({
  variable: "--font-display-family",
  weight: ["500", "600", "700"],
  subsets: ["latin", "vietnamese"],
});

const fontSans = IBM_Plex_Sans({
  variable: "--font-sans-family",
  weight: ["400", "500", "600"],
  subsets: ["latin", "vietnamese"],
});

const fontMono = IBM_Plex_Mono({
  variable: "--font-mono-family",
  weight: ["400", "500"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "VigiBank",
  description: "Giám sát phản hồi khách hàng và pain point theo thời gian thực",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="vi"
      className={`${fontDisplay.variable} ${fontSans.variable} ${fontMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <AuthProvider>{children}</AuthProvider>
        <Toaster />
      </body>
    </html>
  );
}
