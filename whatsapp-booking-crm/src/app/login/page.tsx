"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const r = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    setBusy(false);
    if (r.ok) {
      router.push(params.get("next") || "/");
      router.refresh();
    } else {
      setError("Incorrect password");
    }
  };

  return (
    <main className="mx-auto grid min-h-[60vh] max-w-sm place-items-center px-5">
      <form onSubmit={submit} className="w-full rounded-2xl border border-line bg-white p-6 shadow-sm">
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight">Admin sign in</h1>
        <p className="mt-1 text-sm text-ink-soft">Enter your admin password to access the CRM.</p>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          className="mt-4 w-full rounded-lg border border-line px-3 py-2.5 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent-wash"
        />
        {error && <p className="mt-2 text-sm text-[#b42318]">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="mt-4 w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-ink disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-sm px-5 py-16 text-center text-ink-soft">Loading…</main>}>
      <LoginForm />
    </Suspense>
  );
}
