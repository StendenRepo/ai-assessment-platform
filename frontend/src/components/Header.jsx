'use client';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
const navItems = [
    { label: 'Dashboard', href: '/dashboard' },
    { label: 'Projects', href: '/projects' },
    { label: 'New Project', href: '/projects/new' },
    { label: 'Reports', href: '/reports' },
    { label: 'Settings', href: '/settings' },
];
export default function Header() {
    const pathname = usePathname();
    const router = useRouter();
    const isActive = (href) => {
        if (href === '/dashboard')
            return pathname === '/dashboard';
        if (href === '/projects/new')
            return pathname === '/projects/new';
        if (href === '/projects')
            return pathname.startsWith('/projects') && pathname !== '/projects/new';
        return pathname.startsWith(href);
    };
    return (<div className="bg-white border-b-2 border-gray-300">
      <div className="max-w-7xl mx-auto px-8 py-4">
        <div className="flex justify-between items-center mb-4">
          <div>
            <div className="text-2xl font-bold mb-1">[LOGO] AI Assessment System</div>
            <div className="text-sm text-gray-600">Group Project Evaluation Platform</div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-sm">
              <div className="font-bold">Dr. John Smith</div>
              <div className="text-gray-600">Lecturer</div>
            </div>
            <button onClick={() => router.push('/')} className="border-2 border-gray-400 px-4 py-2 text-sm hover:bg-gray-100">
              [LOG OUT]
            </button>
          </div>
        </div>

        <div className="flex gap-0 border-b-2 border-gray-300">
          {navItems.map((item) => (<Link key={item.href} href={item.href} className={`px-6 py-3 border-b-4 ${isActive(item.href)
                ? 'border-black font-bold bg-gray-100'
                : 'border-transparent hover:bg-gray-50'}`}>
              {item.label}
            </Link>))}
        </div>
      </div>
    </div>);
}
