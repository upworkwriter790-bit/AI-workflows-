import { newId } from "@/lib/resume/defaultData";
import type {
  CertificationEntry,
  EducationEntry,
  ExperienceEntry,
  ProjectEntry,
  ResumeSection,
  SectionType,
  SimpleEntry,
} from "@/lib/resume/types";

const SECTION_LABELS: Record<SectionType, string> = {
  summary: "Professional Summary",
  experience: "Work Experience",
  education: "Education",
  skills: "Skills",
  projects: "Projects",
  certifications: "Certifications",
  languages: "Languages",
  awards: "Awards",
  custom: "Custom Section",
};

export function blankSection(type: SectionType): ResumeSection {
  const base = { id: newId("sec"), type, title: SECTION_LABELS[type], visible: true };
  switch (type) {
    case "summary":
    case "custom":
      return { ...base, content: { kind: "text", text: "" } };
    case "experience":
      return { ...base, content: { kind: "experience", items: [] } };
    case "education":
      return { ...base, content: { kind: "education", items: [] } };
    case "projects":
      return { ...base, content: { kind: "projects", items: [] } };
    case "certifications":
      return { ...base, content: { kind: "certifications", items: [] } };
    case "skills":
    case "languages":
    case "awards":
    default:
      return { ...base, content: { kind: "list", items: [] } };
  }
}

export const SECTION_TYPE_OPTIONS: { type: SectionType; label: string }[] = [
  { type: "summary", label: "Summary" },
  { type: "experience", label: "Work Experience" },
  { type: "education", label: "Education" },
  { type: "skills", label: "Skills" },
  { type: "projects", label: "Projects" },
  { type: "certifications", label: "Certifications" },
  { type: "languages", label: "Languages" },
  { type: "awards", label: "Awards" },
  { type: "custom", label: "Custom (free text)" },
];

export function blankExperience(): ExperienceEntry {
  return {
    id: newId("exp"),
    role: "",
    company: "",
    location: "",
    startDate: "",
    endDate: "",
    current: false,
    bullets: [""],
  };
}

export function blankEducation(): EducationEntry {
  return {
    id: newId("edu"),
    degree: "",
    institution: "",
    location: "",
    startDate: "",
    endDate: "",
    details: "",
  };
}

export function blankProject(): ProjectEntry {
  return {
    id: newId("proj"),
    name: "",
    link: "",
    description: "",
    bullets: [""],
  };
}

export function blankCertification(): CertificationEntry {
  return { id: newId("cert"), name: "", issuer: "", date: "" };
}

export function blankSimpleEntry(): SimpleEntry {
  return { id: newId("item"), label: "" };
}
