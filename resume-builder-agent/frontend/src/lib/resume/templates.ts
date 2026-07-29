export interface TemplateMeta {
  id: string;
  name: string;
  description: string;
  accentColor: string;
  fontFamily: string;
}

// All templates are strictly single-column with a linear reading order —
// the layout ATS parsers handle reliably. They differ only in typography,
// spacing and accenting, not in structure, so every one stays ATS-safe.
export const TEMPLATES: TemplateMeta[] = [
  {
    id: "modern",
    name: "Modern",
    description: "Clean sans-serif with a bold accent color and underlined section headings.",
    accentColor: "#2563eb",
    fontFamily: "Inter",
  },
  {
    id: "classic",
    name: "Classic",
    description: "Traditional centered serif header — the safest choice for conservative fields.",
    accentColor: "#1f2937",
    fontFamily: "Times New Roman",
  },
  {
    id: "minimal",
    name: "Minimal",
    description: "Grayscale, generous whitespace, small-caps section labels.",
    accentColor: "#111827",
    fontFamily: "Helvetica",
  },
  {
    id: "professional",
    name: "Professional",
    description: "Bold uppercase name, single-line contact bar, square accent bullets.",
    accentColor: "#0f766e",
    fontFamily: "Georgia",
  },
  {
    id: "compact",
    name: "Compact",
    description: "Tighter spacing to fit more on one page without feeling cramped.",
    accentColor: "#b91c1c",
    fontFamily: "Inter",
  },
];

export function getTemplate(id: string): TemplateMeta {
  return TEMPLATES.find((t) => t.id === id) ?? TEMPLATES[0];
}
