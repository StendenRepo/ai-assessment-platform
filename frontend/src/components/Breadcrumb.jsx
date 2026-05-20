'use client';
import Link from 'next/link';
export default function Breadcrumb({ crumbs }) {
    return (<div className="bg-gray-200 border-b border-gray-300">
      <div className="max-w-7xl mx-auto px-8 py-2">
        <div className="text-sm text-gray-600 flex items-center gap-1">
          {crumbs.map((crumb, i) => (<span key={i} className="flex items-center gap-1">
              {i > 0 && <span className="mx-1">/</span>}
              {crumb.href ? (<Link href={crumb.href} className="hover:underline">
                  {crumb.label}
                </Link>) : (<span className="font-bold">{crumb.label}</span>)}
            </span>))}
        </div>
      </div>
    </div>);
}
