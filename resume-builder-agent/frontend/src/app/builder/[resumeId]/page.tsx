"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Check, Palette, PenSquare } from "lucide-react";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { ResumePreview } from "@/components/resume/ResumePreview";
import { PersonalInfoEditor } from "@/components/resume/PersonalInfoEditor";
import { SectionManager } from "@/components/resume/SectionManager";
import { StylePanel } from "@/components/resume/StylePanel";
import { DownloadMenu } from "@/components/resume/DownloadMenu";
import { resumeApi } from "@/lib/resume/api";
import { defaultResumeData } from "@/lib/resume/defaultData";
import { useAuth } from "@/lib/auth/AuthContext";
import type { Resume } from "@/lib/resume/types";
import { DEFAULT_STYLES } from "@/lib/resume/types";

function BuilderContent() {
  const { resumeId } = useParams<{ resumeId: string }>();
  const router = useRouter();
  const { user } = useAuth();

  const [resume, setResume] = useState<Resume | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState<"content" | "design">("content");
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [savedJustNow, setSavedJustNow] = useState(false);

  useEffect(() => {
    resumeApi
      .get(resumeId)
      .then((r) => {
        // Uploaded files aren't parsed into structured data yet — hand the
        // user a normal editable resume seeded from their profile instead
        // of leaving them on a dead end.
        if (r.templateId === "uploaded") {
          setResume({
            ...r,
            templateId: "modern",
            data: r.data.sections?.length ? r.data : defaultResumeData(user),
            styles: Object.keys(r.styles).length ? r.styles : DEFAULT_STYLES,
          });
        } else {
          setResume(r);
        }
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeId]);

  const updateResume = useCallback((patch: Partial<Resume>) => {
    setResume((r) => (r ? { ...r, ...patch } : r));
    setDirty(true);
  }, []);

  async function handleSave() {
    if (!resume) return;
    setSaving(true);
    try {
      await resumeApi.update(resume.id, {
        title: resume.title,
        template_id: resume.templateId,
        data: resume.data,
        styles: resume.styles,
      });
      setDirty(false);
      setSavedJustNow(true);
      setTimeout(() => setSavedJustNow(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600" />
      </div>
    );
  }

  if (notFound || !resume) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3">
        <p className="text-slate-600">This resume doesn&apos;t exist or you don&apos;t have access to it.</p>
        <Button onClick={() => router.push("/dashboard")}>Back to dashboard</Button>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3">
        <Button variant="ghost" onClick={() => router.push("/dashboard")}>
          <ArrowLeft size={16} />
        </Button>
        <Input
          value={resume.title}
          onChange={(e) => updateResume({ title: e.target.value })}
          className="max-w-xs font-medium"
        />
        <div className="ml-auto flex items-center gap-2">
          {savedJustNow && (
            <span className="flex items-center gap-1 text-sm text-green-600">
              <Check size={14} /> Saved
            </span>
          )}
          <Button variant="outline" onClick={handleSave} loading={saving} disabled={!dirty && !saving}>
            Save
          </Button>
          <DownloadMenu
            title={resume.title}
            templateId={resume.templateId}
            data={resume.data}
            styles={resume.styles}
          />
        </div>
      </header>

      <div className="grid flex-1 grid-cols-1 lg:grid-cols-[380px_1fr]">
        <aside className="border-r border-slate-200 bg-white p-4 lg:h-[calc(100vh-57px)] lg:overflow-y-auto">
          <div className="mb-4 flex gap-1 rounded-lg bg-slate-100 p-1">
            <button
              onClick={() => setTab("content")}
              className={`flex flex-1 items-center justify-center gap-1.5 rounded-md py-1.5 text-sm font-medium ${
                tab === "content" ? "bg-white shadow-sm" : "text-slate-500"
              }`}
            >
              <PenSquare size={14} /> Content
            </button>
            <button
              onClick={() => setTab("design")}
              className={`flex flex-1 items-center justify-center gap-1.5 rounded-md py-1.5 text-sm font-medium ${
                tab === "design" ? "bg-white shadow-sm" : "text-slate-500"
              }`}
            >
              <Palette size={14} /> Design
            </button>
          </div>

          {tab === "content" ? (
            <div className="space-y-6">
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-900">Personal info</h3>
                <PersonalInfoEditor
                  personal={resume.data.personal}
                  onChange={(personal) => updateResume({ data: { ...resume.data, personal } })}
                />
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-900">Sections</h3>
                <SectionManager
                  sections={resume.data.sections}
                  onChange={(sections) => updateResume({ data: { ...resume.data, sections } })}
                />
              </div>
            </div>
          ) : (
            <StylePanel styles={resume.styles} onChange={(styles) => updateResume({ styles })} />
          )}
        </aside>

        <main className="overflow-y-auto bg-slate-100 p-6 lg:h-[calc(100vh-57px)]">
          <ResumePreview templateId={resume.templateId} data={resume.data} styles={resume.styles} />
        </main>
      </div>
    </div>
  );
}

export default function BuilderPage() {
  return (
    <ProtectedRoute>
      <BuilderContent />
    </ProtectedRoute>
  );
}
