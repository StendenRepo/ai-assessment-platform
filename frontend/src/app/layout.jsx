import '../globals.css';
import Header from '@/components/Header';

export const metadata = {
  title: 'AI Assessment System',
  description: 'Group Project Evaluation Platform',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-gray-50">
        <div className="min-h-screen bg-gray-50">
          <Header />
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
