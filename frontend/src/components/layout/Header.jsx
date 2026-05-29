'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { GraduationCap, LogOut } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

/**
 * exact: true  — active only on the precise path
 * (e.g. /projects/new won't also highlight /projects)
 * exact: false (default) — active on the path and any sub-routes,
 * unless an exact item claims the current path
 */
const DEFAULT_NAV_ITEMS = [
  { href: '/dashboard', label: 'Dashboard', exact: true },
  { href: '/projects', label: 'Projects' },
  { href: '/projects/new', label: 'New Project', exact: true },
  { href: '/reports', label: 'Reports' },
  { href: '/settings', label: 'Settings', right: true },
];

// Returns up to 2 uppercase initials from a full name, e.g. "John Smith" → "JS"
function initials(name = '') {
  return name
    .split(' ')
    .map((p) => p[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export default function Header({
  navItems = DEFAULT_NAV_ITEMS,
  subtitle = 'Group Project Evaluation Platform',
  logoHref = '/dashboard',
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  return (
    <header className="bg-card border-b border-border sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-8">
        <div className="flex items-center justify-between h-16">
          <Link href={logoHref} className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <GraduationCap size={16} className="text-primary-foreground" />
            </div>
            <div>
              <div className="text-sm font-semibold text-foreground leading-none">
                AssessAI
              </div>
              <div className="text-[10px] text-muted-foreground mt-0.5">
                {subtitle}
              </div>
            </div>
          </Link>

          <div className="flex items-center gap-4">
            {user && (
              <>
                <div className="text-right">
                  <div className="text-sm font-semibold text-foreground">
                    {user.name}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {user.email}
                  </div>
                </div>
                <div className="w-9 h-9 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">
                  {initials(user.name)}
                </div>
              </>
            )}
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
            >
              <LogOut size={13} />
              Log out
            </button>
          </div>
        </div>

        <nav className="flex -mb-px">
          {navItems
            .filter((item) => !item.right)
            .map(({ href, label, exact }) => {
              const active = exact
                ? pathname === href
                : pathname === href ||
                  (pathname.startsWith(href + '/') &&
                    !navItems.some(
                      (item) => item.exact && pathname === item.href
                    ));
              return (
                <Link
                  key={href}
                  href={href}
                  className={`px-5 py-3 text-sm font-medium border-b-2 transition-all ${
                    active
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
                  }`}
                >
                  {label}
                </Link>
              );
            })}
          {navItems.some((item) => item.right) && <div className="flex-1" />}
          {navItems
            .filter((item) => item.right)
            .map(({ href, label, exact }) => {
              const active = exact
                ? pathname === href
                : pathname === href ||
                  (pathname.startsWith(href + '/') &&
                    !navItems.some(
                      (item) => item.exact && pathname === item.href
                    ));
              return (
                <Link
                  key={href}
                  href={href}
                  className={`px-5 py-3 text-sm font-medium border-b-2 transition-all ${
                    active
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
                  }`}
                >
                  {label}
                </Link>
              );
            })}
        </nav>
      </div>
    </header>
  );
}
