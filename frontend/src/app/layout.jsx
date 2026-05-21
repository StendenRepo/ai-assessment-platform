import './globals.css';

export const metadata = {
  title: 'AI Assessment System',
  description: 'Group Project Evaluation Platform',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-gray-50">{children}</body>
    </html>
  );
}
