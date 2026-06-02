/** Shared form control classes — keep inputs and selects visually aligned. */

export const inputCls =
  'w-full h-10 min-h-10 bg-secondary border border-border rounded-md px-3 py-2 text-sm leading-normal text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';

/** Native select: fixed height, custom chevron via globals.css `select` rules */
export const selectCls =
  'h-10 min-h-10 bg-secondary border border-border rounded-md pl-3 pr-9 text-sm leading-normal text-foreground cursor-pointer focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';

export const selectFullCls = `w-full ${selectCls}`;

/** Inline filters (toolbar) — auto width from content */
export const selectInlineCls = `${selectCls} w-auto min-w-[9rem] max-w-full`;
