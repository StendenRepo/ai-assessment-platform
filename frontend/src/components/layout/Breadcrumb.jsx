'use client';

import Link from 'next/link';
import { usePathname, useParams, useSearchParams } from 'next/navigation';
import { ChevronRight } from 'lucide-react';
import { APP_PATHS } from '@/lib/routes';

function buildCrumbs(pathname, params, fromModule) {
  const crumbs = [{ label: 'Dashboard', href: APP_PATHS.dashboard }];
  const { moduleId, groupId, studentId } = params || {};

  if (pathname.startsWith(APP_PATHS.moduleNew)) {
    crumbs.push({ label: 'Modules', href: APP_PATHS.modules });
    crumbs.push({ label: 'New Module', href: null });
  } else if (pathname.startsWith(APP_PATHS.modules)) {
    crumbs.push({ label: 'Modules', href: APP_PATHS.modules });
    if (moduleId)
      crumbs.push({
        label: 'Module',
        href: `${APP_PATHS.modules}/${moduleId}`,
      });
    if (pathname.includes('/manage')) {
      crumbs.push({ label: 'Manage Roster', href: null });
    }
    if (groupId && !fromModule)
      crumbs.push({
        label: 'Group',
        href: `${APP_PATHS.modules}/${moduleId}/groups/${groupId}`,
      });
    if (studentId) {
      crumbs.push({ label: 'Assessment', href: null });
    } else if (pathname.includes('/criteria')) {
      crumbs.push({ label: 'Criteria & Rubrics', href: null });
    }
  } else if (pathname.startsWith(APP_PATHS.reports)) {
    crumbs.push({ label: 'Reports', href: null });
  } else if (pathname.startsWith(APP_PATHS.settings)) {
    crumbs.push({ label: 'Settings', href: null });
  }

  return crumbs;
}

export default function Breadcrumb() {
  const pathname = usePathname();
  const params = useParams();
  const searchParams = useSearchParams();
  const crumbs = buildCrumbs(
    pathname,
    params,
    searchParams.get('from') === 'module'
  );

  if (crumbs.length <= 1) return null;

  return (
    <div className="bg-secondary/50 border-b border-border">
      <div className="max-w-7xl mx-auto px-8 py-2.5">
        <nav className="flex items-center gap-1.5 text-sm">
          {crumbs.map((crumb, i) => (
            <span key={i} className="flex items-center gap-1.5">
              {i > 0 && (
                <ChevronRight size={13} className="text-muted-foreground/40" />
              )}
              {crumb.href ? (
                <Link
                  href={crumb.href}
                  className="text-muted-foreground hover:text-foreground transition-colors"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span className="text-foreground font-semibold">
                  {crumb.label}
                </span>
              )}
            </span>
          ))}
        </nav>
      </div>
    </div>
  );
}
