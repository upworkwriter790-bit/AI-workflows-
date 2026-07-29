"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, BadgeCheck } from "lucide-react";
import { useAuth } from "@/lib/auth/AuthContext";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { Button } from "@/components/ui/Button";
import { TEMPLATES } from "@/lib/resume/templates";
import { DEFAULT_STYLES } from "@/lib/resume/types";
import { ResumePreview } from "@/components/resume/ResumePreview";
import { defaultResumeData } from "@/lib/resume/defaultData";
import { resumeApi } from "@/lib/resume/api";

const SAMPLE_DATA = {
  personal: {
    fullName: "Alex Morgan",
    headline: "Product Marketing Manager",
    email: "alex.morgan@email.com",
    phone: "+1 555 010 2020",
    location: "Austin, TX",
    linkedin: "linkedin.com/in/alexmorgan",
    website: "",
  },
  sections: [
    {
      id: "s1",
      type: "summary" as const,
      title: "Professional Summary",
      visible: true,
      content: {
        kind: "text" as const,
        text: "Results-driven marketing manager with 6+ years launching B2B SaaS products.",
      },
    },
    {
      id: "s2",
      type: "experience" as const,
      title: "Work Experience",
      visible: true,
      content: {
        kind: "experience" as const,
        items: [
          {
            id: "e1",
            role: "Senior Product Marketing Manager",
            company: "Northwind Inc.",
            location: "Remote",
            startDate: "2022",
            endDate: "",
            current: true,
            bullets: ["Led go-to-market for 3 major releases, growing adoption 40% YoY."],
          },
        ],
      },
    },
  ],
};

function TemplatesContent() {
  const router = useRouter();
  const { user } = useAuth();
  const [creatingId, setCreatingId] = useState<string | null>(null);

  async function selectTemplate(templateId: string) {
    setCreatingId(templateId);
    try {
      const resume = await resumeApi.create({
        title: "Untitled Resume",
        template_id: templateId,
        data: defaultResumeData(user),
        styles: DEFAULT_STYLES,
      });
      router.push(`/builder/${resume.id}`);
    } finally {
      setCreatingId(null);
    }
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-10">
      <Button variant="ghost" onClick={() => router.push("/dashboard")} className="mb-6">
        <ArrowLeft size={16} /> Back to dashboard
      </Button>

      <h1 className="text-2xl font-bold text-slate-900">Choose a template</h1>
      <p className="mt-1 flex items-center gap-1.5 text-sm text-slate-500">
        <BadgeCheck size={16} className="text-green-600" /> Every template is single-column and
        ATS-verified — safe to parse by applicant tracking systems.
      </p>

      <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {TEMPLATES.map((t) => (
          <div key={t.id} className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="h-64 overflow-hidden rounded-lg border border-slate-100 bg-slate-50">
              <div className="origin-top-left scale-[0.36]">
                <ResumePreview templateId={t.id} data={SAMPLE_DATA} styles={DEFAULT_STYLES} />
              </div>
            </div>
            <p className="mt-3 font-semibold text-slate-900">{t.name}</p>
            <p className="mt-1 text-sm text-slate-500">{t.description}</p>
            <Button
              className="mt-4 w-full"
              loading={creatingId === t.id}
              onClick={() => selectTemplate(t.id)}
            >
              Use this template
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TemplatesPage() {
  return (
    <ProtectedRoute>
      <TemplatesContent />
    </ProtectedRoute>
  );
}
