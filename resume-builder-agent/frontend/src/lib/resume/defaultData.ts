import type { UserProfile } from "@/lib/auth/types";
import type { ResumeData, ResumeSection } from "@/lib/resume/types";

let idCounter = 0;
export function newId(prefix = "id"): string {
  idCounter += 1;
  return `${prefix}-${Date.now().toString(36)}-${idCounter}`;
}

export function defaultSections(): ResumeSection[] {
  return [
    {
      id: newId("sec"),
      type: "summary",
      title: "Professional Summary",
      visible: true,
      content: { kind: "text", text: "" },
    },
    {
      id: newId("sec"),
      type: "experience",
      title: "Work Experience",
      visible: true,
      content: { kind: "experience", items: [] },
    },
    {
      id: newId("sec"),
      type: "education",
      title: "Education",
      visible: true,
      content: { kind: "education", items: [] },
    },
    {
      id: newId("sec"),
      type: "skills",
      title: "Skills",
      visible: true,
      content: { kind: "list", items: [] },
    },
    {
      id: newId("sec"),
      type: "projects",
      title: "Projects",
      visible: true,
      content: { kind: "projects", items: [] },
    },
    {
      id: newId("sec"),
      type: "certifications",
      title: "Certifications",
      visible: false,
      content: { kind: "certifications", items: [] },
    },
    {
      id: newId("sec"),
      type: "languages",
      title: "Languages",
      visible: false,
      content: { kind: "list", items: [] },
    },
  ];
}

export function defaultResumeData(profile?: UserProfile | null): ResumeData {
  const location = profile
    ? [profile.city, profile.state, profile.country].filter(Boolean).join(", ")
    : "";

  return {
    personal: {
      fullName: profile ? `${profile.first_name} ${profile.last_name}`.trim() : "",
      headline: "",
      email: profile?.email ?? "",
      phone: profile ? `${profile.country_code} ${profile.phone}`.trim() : "",
      location,
      linkedin: "",
      website: "",
    },
    sections: defaultSections(),
  };
}
