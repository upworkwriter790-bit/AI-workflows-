"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FileText, Sparkles, ShieldCheck } from "lucide-react";
import { useAuth } from "@/lib/auth/AuthContext";
import { Button } from "@/components/ui/Button";
import { AuthModal } from "@/components/auth/AuthModal";

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"signin" | "signup">("signup");

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  function open(mode: "signin" | "signup") {
    setAuthMode(mode);
    setAuthOpen(true);
  }

  return (
    <main className="flex flex-1 flex-col">
      <header className="flex items-center justify-between px-6 py-5 sm:px-10">
        <div className="flex items-center gap-2 font-semibold text-slate-900">
          <FileText className="text-blue-600" size={22} />
          Resume Builder Agent
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => open("signin")}>
            Sign in
          </Button>
          <Button onClick={() => open("signup")}>Sign up</Button>
        </div>
      </header>

      <section className="mx-auto flex max-w-3xl flex-1 flex-col items-center justify-center px-6 py-16 text-center">
        <span className="mb-4 inline-flex items-center gap-1 rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
          <Sparkles size={12} /> ATS-verified templates
        </span>
        <h1 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
          Build a resume that gets past the bots and in front of humans.
        </h1>
        <p className="mt-4 max-w-xl text-lg text-slate-600">
          Start from a proven, ATS-friendly template or improve the resume you already have — then
          fine-tune fonts, colors and spacing until it&apos;s exactly yours.
        </p>
        <div className="mt-8 flex gap-3">
          <Button onClick={() => open("signup")} className="px-6 py-3 text-base">
            Get started free
          </Button>
          <Button variant="outline" onClick={() => open("signin")} className="px-6 py-3 text-base">
            I already have an account
          </Button>
        </div>
        <div className="mt-10 flex items-center gap-2 text-sm text-slate-500">
          <ShieldCheck size={16} className="text-green-600" />
          Your data is saved securely and never lost between sessions.
        </div>
      </section>

      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} initialMode={authMode} />
    </main>
  );
}
