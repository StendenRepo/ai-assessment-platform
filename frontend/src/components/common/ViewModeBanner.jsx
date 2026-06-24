import { Eye } from 'lucide-react';

export default function ViewModeBanner({ ownerName }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3">
      <Eye size={16} className="text-amber-400 mt-0.5 shrink-0" />
      <div>
        <p className="text-sm font-semibold text-amber-400">View Mode</p>
        <p className="text-xs text-amber-400/80 mt-0.5">
          {ownerName
            ? `This module is owned by ${ownerName}. `
            : 'This module is owned by another teacher. '}
          Changes cannot be made to modules you do not own.
        </p>
      </div>
    </div>
  );
}
