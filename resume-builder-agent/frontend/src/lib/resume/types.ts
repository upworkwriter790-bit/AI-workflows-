export type SectionType =
  | "summary"
  | "experience"
  | "education"
  | "skills"
  | "projects"
  | "certifications"
  | "languages"
  | "awards"
  | "custom";

export interface ExperienceEntry {
  id: string;
  role: string;
  company: string;
  location: string;
  startDate: string;
  endDate: string;
  current: boolean;
  bullets: string[];
}

export interface EducationEntry {
  id: string;
  degree: string;
  institution: string;
  location: string;
  startDate: string;
  endDate: string;
  details: string;
}

export interface ProjectEntry {
  id: string;
  name: string;
  link: string;
  description: string;
  bullets: string[];
}

export interface CertificationEntry {
  id: string;
  name: string;
  issuer: string;
  date: string;
}

export interface SimpleEntry {
  id: string;
  label: string;
  value?: string;
}

export type SectionContent =
  | { kind: "text"; text: string }
  | { kind: "experience"; items: ExperienceEntry[] }
  | { kind: "education"; items: EducationEntry[] }
  | { kind: "projects"; items: ProjectEntry[] }
  | { kind: "certifications"; items: CertificationEntry[] }
  | { kind: "list"; items: SimpleEntry[] };

export interface ResumeSection {
  id: string;
  type: SectionType;
  title: string;
  visible: boolean;
  content: SectionContent;
}

export interface PersonalInfo {
  fullName: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  website: string;
}

export interface ResumeStyles {
  fontFamily: string;
  fontSizePt: number;
  textColor: string;
  accentColor: string;
  lineSpacing: number;
  letterSpacingPx: number;
  wordSpacingPx: number;
}

export const DEFAULT_STYLES: ResumeStyles = {
  fontFamily: "Inter",
  fontSizePt: 10.5,
  textColor: "#1a1a1a",
  accentColor: "#2563eb",
  lineSpacing: 1.35,
  letterSpacingPx: 0,
  wordSpacingPx: 0,
};

export interface ResumeData {
  personal: PersonalInfo;
  sections: ResumeSection[];
}

export interface Resume {
  id: string;
  userId: string;
  title: string;
  templateId: string;
  data: ResumeData;
  styles: ResumeStyles;
  source: "new" | "upload";
  createdAt: string;
  updatedAt: string;
}

export const FONT_OPTIONS = [
  { label: "Inter (Sans)", value: "Inter" },
  { label: "Georgia (Serif)", value: "Georgia" },
  { label: "Times New Roman (Serif)", value: "Times New Roman" },
  { label: "Helvetica (Sans)", value: "Helvetica" },
  { label: "Courier New (Mono)", value: "Courier New" },
  { label: "Garamond (Serif)", value: "Garamond" },
] as const;
