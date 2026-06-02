'use client';

import Link from 'next/link';
import { usePathname, useParams } from 'next/navigation';
import { ChevronRight } from 'lucide-react';

function buildCrumbs(pathname, params) {
  const crumbs = [{ label: 'Dashboard', href: '/dashboard' }];
  const { projectId, groupId, studentId, overlapId } = params || {};

  if (pathname.startsWith('/projects/new')) {
    crumbs.push({ label: 'Projects', href: '/projects' });
    crumbs.push({ label: 'New Project', href: null });
  } else if (pathname.startsWith('/projects')) {
    crumbs.push({ label: 'Projects', href: '/projects' });
    if (projectId)
      crumbs.push({ label: 'Project', href: `/projects/${projectId}` });
    if (groupId)
      crumbs.push({
        label: 'Group',
        href: `/projects/${projectId}/groups/${groupId}`,
      });
    if (pathname.includes('/overlaps/') && overlapId) {
      crumbs.push({
        label: 'Overlaps',
        href: `/projects/${projectId}/groups/${groupId}/overlaps`,
      });
      crumbs.push({ label: 'Detail', href: null });
    } else if (pathname.includes('/overlaps')) {
      crumbs.push({ label: 'Overlaps', href: null });
    } else if (studentId) {
      crumbs.push({ label: 'Assessment', href: null });
    } else if (pathname.includes('/criteria')) {
      crumbs.push({ label: 'Criteria & Rubrics', href: null });
    }
  } else if (pathname.startsWith('/reports')) {
    crumbs.push({ label: 'Reports', href: null });
  } else if (pathname.startsWith('/settings')) {
    crumbs.push({ label: 'Settings', href: null });
  }

  return crumbs;
}

export default function Breadcrumb() {
  const pathname = usePathname();
  const params = useParams();
  const crumbs = buildCrumbs(pathname, params);

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
