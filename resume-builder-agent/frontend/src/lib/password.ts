export interface PasswordCheck {
  hasLower: boolean;
  hasUpper: boolean;
  hasNumber: boolean;
  hasSymbol: boolean;
  hasMinLength: boolean;
  score: number; // 0-5
  label: "Very weak" | "Weak" | "Fair" | "Strong" | "Very strong";
}

const SYMBOL_RE = /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?~`]/;

export function checkPassword(password: string): PasswordCheck {
  const hasLower = /[a-z]/.test(password);
  const hasUpper = /[A-Z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  const hasSymbol = SYMBOL_RE.test(password);
  const hasMinLength = password.length >= 8;

  const score = [hasLower, hasUpper, hasNumber, hasSymbol, hasMinLength].filter(
    Boolean
  ).length;

  const labels: PasswordCheck["label"][] = [
    "Very weak",
    "Very weak",
    "Weak",
    "Fair",
    "Strong",
    "Very strong",
  ];

  return {
    hasLower,
    hasUpper,
    hasNumber,
    hasSymbol,
    hasMinLength,
    score,
    label: labels[score],
  };
}

export function isPasswordValid(password: string): boolean {
  const c = checkPassword(password);
  return c.hasLower && c.hasUpper && c.hasNumber && c.hasSymbol && c.hasMinLength;
}

const LOWER = "abcdefghijkmnopqrstuvwxyz";
const UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ";
const NUMBERS = "23456789";
const SYMBOLS = "!@#$%^&*()_+-=?";

function randomChar(pool: string): string {
  const bytes = new Uint32Array(1);
  crypto.getRandomValues(bytes);
  return pool[bytes[0] % pool.length];
}

/** Generates a strong password guaranteed to satisfy checkPassword() fully. */
export function generateStrongPassword(length = 14): string {
  const pools = [LOWER, UPPER, NUMBERS, SYMBOLS];
  const required = pools.map(randomChar);
  const all = LOWER + UPPER + NUMBERS + SYMBOLS;
  const rest = Array.from({ length: Math.max(length - required.length, 0) }, () =>
    randomChar(all)
  );

  const chars = [...required, ...rest];
  // Fisher-Yates shuffle so required chars aren't always up front.
  for (let i = chars.length - 1; i > 0; i--) {
    const bytes = new Uint32Array(1);
    crypto.getRandomValues(bytes);
    const j = bytes[0] % (i + 1);
    [chars[i], chars[j]] = [chars[j], chars[i]];
  }

  return chars.join("");
}
