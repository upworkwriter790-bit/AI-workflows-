"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FileText, LogOut, Plus, Upload, User as UserIcon } from "lucide-react";
import { useAuth } from "@/lib/auth/AuthContext";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { Button } from "@/components/ui/Button";
import { resumeApi } from "@/lib/resume/api";
import type { Resume } from "@/lib/resume/types";

function DashboardContent() {
  const { user, signOut } = useAuth();
  const router = useRouter();
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loadingResumes, setLoadingResumes] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    resumeApi
      .list()
      .then(setResumes)
      .finally(() => setLoadingResumes(false));
  }, []);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError(null);
    setUploading(true);
    try {
      const resume = await resumeApi.upload(file);
      router.push(`/builder/${resume.id}`);
    } catch {
      setUploadError("Couldn't upload that file. Please try a PDF or Word document under 10 MB.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-10">
      <header className="mb-10 flex items-center justify-between">
        <div className="flex items-center gap-2 font-semibold text-slate-900">
          <FileText className="text-blue-600" size={22} />
          Resume Builder Agent
        </div>
        <Button variant="ghost" onClick={() => signOut().then(() => router.replace("/"))}>
          <LogOut size={16} /> Sign out
        </Button>
      </header>

      <section className="mb-10 flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-50 text-blue-600">
          <UserIcon size={22} />
        </div>
        <div>
          <p className="font-semibold text-slate-900">
            {user?.first_name} {user?.last_name}
          </p>
          <p className="text-sm text-slate-500">
            {user?.email} · {[user?.city, user?.state, user?.country].filter(Boolean).join(", ")}
          </p>
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-xl font-semibold text-slate-900">Resume Builder</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <button
            onClick={() => router.push("/templates")}
            className="flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 bg-white p-8 text-center hover:border-blue-400 hover:bg-blue-50/40"
          >
            <Plus className="text-blue-600" size={28} />
            <span className="font-medium text-slate-900">New resume</span>
            <span className="text-sm text-slate-500">Start from an ATS-verified template</span>
          </button>

          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 bg-white p-8 text-center hover:border-blue-400 hover:bg-blue-50/40 disabled:opacity-60"
          >
            <Upload className="text-blue-600" size={28} />
            <span className="font-medium text-slate-900">
              {uploading ? "Uploading…" : "Upload a resume"}
            </span>
            <span className="text-sm text-slate-500">PDF or Word, up to 10 MB</span>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx"
              className="hidden"
              onChange={handleUpload}
            />
          </button>
        </div>
        {uploadError && <p className="mt-3 text-sm text-red-600">{uploadError}</p>}
      </section>

      {!loadingResumes && resumes.length > 0 && (
        <section className="mt-10">
          <h2 className="mb-4 text-xl font-semibold text-slate-900">Your resumes</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
            {resumes.map((r) => (
              <button
                key={r.id}
                onClick={() => router.push(`/builder/${r.id}`)}
                className="rounded-2xl border border-slate-200 bg-white p-5 text-left hover:border-blue-300 hover:shadow-sm"
              >
                <p className="font-medium text-slate-900">{r.title}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {r.source === "upload" ? "Uploaded" : "Template"} · Updated{" "}
                  {new Date(r.updatedAt).toLocaleDateString()}
                </p>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
