import "./globals.css";

export const metadata = {
  title: "MBTI Relationship Analysis",
  description: "A minimalist tool to analyze relationship dynamics from transcripts.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-gray-900 text-white">{children}</body>
    </html>
  );
}
