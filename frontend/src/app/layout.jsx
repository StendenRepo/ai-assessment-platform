import './globals.css';
import { ThemeProvider } from '@/context/ThemeContext';
import { TeacherPreferenceProvider } from '@/context/TeacherPreferenceContext';
import { AuthProvider } from '@/context/AuthContext';

export const metadata = {
  title: 'AssessAI',
  description: 'Group Project Evaluation Platform',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem('theme')||'dark';document.documentElement.classList.toggle('dark',t==='dark')}catch(e){document.documentElement.classList.add('dark')}`,
          }}
        />
      </head>
      <body>
        <ThemeProvider>
          <AuthProvider>
            <TeacherPreferenceProvider>{children}</TeacherPreferenceProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
