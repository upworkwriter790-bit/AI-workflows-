"use client";

import { checkPassword } from "@/lib/password";

const BAR_COLORS = ["bg-red-400", "bg-red-400", "bg-amber-400", "bg-amber-400", "bg-green-500", "bg-green-600"];

export function PasswordStrengthMeter({ password }: { password: string }) {
  const check = checkPassword(password);

  const requirements = [
    { met: check.hasMinLength, label: "At least 8 characters" },
    { met: check.hasLower, label: "A lowercase letter" },
    { met: check.hasUpper, label: "An uppercase letter" },
    { met: check.hasNumber, label: "A number" },
    { met: check.hasSymbol, label: "A symbol (!@#$...)" },
  ];

  return (
    <div className="mt-2">
      <div className="flex gap-1">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className={`h-1.5 flex-1 rounded-full ${
              i < check.score ? BAR_COLORS[check.score] : "bg-slate-200"
            }`}
          />
        ))}
      </div>
      <p className="mt-1 text-xs font-medium text-slate-500">
        {password ? check.label : "Enter a password"}
      </p>
      <ul className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs text-slate-500">
        {requirements.map((r) => (
          <li key={r.label} className={r.met ? "text-green-600" : ""}>
            {r.met ? "✓" : "•"} {r.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
