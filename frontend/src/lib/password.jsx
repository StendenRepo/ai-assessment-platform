import { Check, X } from 'lucide-react';

const PASSWORD_RULES = [
  { label: 'At least 8 characters', test: (p) => p.length >= 8 },
  { label: 'One uppercase letter', test: (p) => /[A-Z]/.test(p) },
  { label: 'One lowercase letter', test: (p) => /[a-z]/.test(p) },
  { label: 'One number', test: (p) => /\d/.test(p) },
  { label: 'One special character', test: (p) => /[^A-Za-z0-9]/.test(p) },
];

export function isPasswordStrong(password) {
  return PASSWORD_RULES.every((r) => r.test(password));
}

export function PasswordStrength({ password }) {
  if (!password) return null;
  return (
    <ul className="mt-1.5 space-y-1">
      {PASSWORD_RULES.map(({ label, test }) => {
        const met = test(password);
        return (
          <li
            key={label}
            className={`flex items-center gap-1.5 text-xs ${met ? 'text-green-500' : 'text-muted-foreground'}`}
          >
            {met ? <Check size={10} /> : <X size={10} />}
            {label}
          </li>
        );
      })}
    </ul>
  );
}
