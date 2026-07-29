"use client";

import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { SignInForm } from "@/components/auth/SignInForm";
import { SignUpForm } from "@/components/auth/SignUpForm";

type Mode = "signin" | "signup";

export function AuthModal({
  open,
  onClose,
  initialMode = "signin",
}: {
  open: boolean;
  onClose: () => void;
  initialMode?: Mode;
}) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [signedUpBanner, setSignedUpBanner] = useState<string | null>(null);

  function handleClose() {
    setMode(initialMode);
    setSignedUpBanner(null);
    onClose();
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={mode === "signin" ? "Sign in" : "Create your account"}
      maxWidthClassName={mode === "signin" ? "max-w-md" : "max-w-xl"}
    >
      {signedUpBanner && mode === "signin" && (
        <div className="mb-4 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700">
          Account created for <strong>{signedUpBanner}</strong>. Sign in below to continue.
        </div>
      )}

      {mode === "signin" ? (
        <SignInForm onSwitchToSignUp={() => setMode("signup")} />
      ) : (
        <SignUpForm
          onSignedUp={(email) => {
            setSignedUpBanner(email);
            setMode("signin");
          }}
        />
      )}

      {mode === "signup" && (
        <p className="mt-4 text-center text-sm text-slate-500">
          Already have an account?{" "}
          <button
            onClick={() => setMode("signin")}
            className="font-medium text-blue-600 hover:underline"
          >
            Sign in
          </button>
        </p>
      )}
    </Modal>
  );
}
