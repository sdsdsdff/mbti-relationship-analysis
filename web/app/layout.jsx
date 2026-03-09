import "./globals.css";

export const metadata = {
  title: "MBTI Relationship Analysis",
  description: "Route B MVP frontend for transcript upload and report review.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
