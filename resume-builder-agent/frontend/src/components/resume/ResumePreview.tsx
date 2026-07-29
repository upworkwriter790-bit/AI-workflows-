import type { CSSProperties } from "react";
import type { ResumeData, ResumeStyles } from "@/lib/resume/types";
import { getTemplate } from "@/lib/resume/templates";

interface ResumePreviewProps {
  templateId: string;
  data: ResumeData;
  styles: ResumeStyles;
}

function headingClasses(templateId: string): string {
  switch (templateId) {
    case "classic":
      return "uppercase tracking-[0.15em] text-[0.85em] font-semibold border-b pb-1";
    case "minimal":
      return "uppercase tracking-[0.2em] text-[0.75em] font-medium text-slate-500";
    case "professional":
      return "uppercase text-[0.85em] font-bold flex items-center gap-2";
    case "compact":
      return "font-bold text-[0.95em] border-b pb-0.5";
    case "modern":
    default:
      return "font-bold text-[1em] border-b-2 pb-1";
  }
}

function headerAlignClass(templateId: string): string {
  return templateId === "classic" ? "text-center" : "text-left";
}

export function ResumePreview({ templateId, data, styles }: ResumePreviewProps) {
  const template = getTemplate(templateId);
  const accent = styles.accentColor || template.accentColor;

  const pageStyle: CSSProperties = {
    fontFamily: `${styles.fontFamily || template.fontFamily}, sans-serif`,
    fontSize: `${styles.fontSizePt}pt`,
    color: styles.textColor,
    lineHeight: styles.lineSpacing,
    letterSpacing: `${styles.letterSpacingPx}px`,
    wordSpacing: `${styles.wordSpacingPx}px`,
  };

  const visibleSections = data.sections.filter((s) => s.visible);

  return (
    <div
      className="mx-auto w-full max-w-[8.5in] bg-white p-10 shadow-sm print:shadow-none"
      style={pageStyle}
      data-template={templateId}
    >
      <header className={headerAlignClass(templateId)}>
        <h1 className="text-[1.9em] font-bold" style={{ color: accent }}>
          {data.personal.fullName || "Your Name"}
        </h1>
        {data.personal.headline && (
          <p className="mt-0.5 text-[1.05em] text-slate-600">{data.personal.headline}</p>
        )}
        <p className="mt-1.5 text-[0.85em] text-slate-500">
          {[data.personal.email, data.personal.phone, data.personal.location, data.personal.linkedin, data.personal.website]
            .filter(Boolean)
            .join("  •  ")}
        </p>
      </header>

      <div className="mt-6 space-y-5">
        {visibleSections.map((section) => (
          <section key={section.id}>
            <h2 className={headingClasses(templateId)} style={{ borderColor: accent, color: templateId === "professional" || templateId === "modern" ? accent : undefined }}>
              {templateId === "professional" && (
                <span className="inline-block h-2 w-2" style={{ backgroundColor: accent }} />
              )}
              {section.title}
            </h2>

            <div className="mt-2">
              {section.content.kind === "text" && (
                <p className="whitespace-pre-line text-[0.95em]">{section.content.text}</p>
              )}

              {section.content.kind === "experience" &&
                section.content.items.map((item) => (
                  <div key={item.id} className="mb-3 last:mb-0">
                    <div className="flex items-baseline justify-between gap-4">
                      <p className="font-semibold">
                        {item.role}
                        {item.company && <span className="font-normal"> · {item.company}</span>}
                      </p>
                      <p className="shrink-0 text-[0.85em] text-slate-500">
                        {item.startDate} – {item.current ? "Present" : item.endDate}
                      </p>
                    </div>
                    {item.location && <p className="text-[0.85em] text-slate-500">{item.location}</p>}
                    {item.bullets.filter(Boolean).length > 0 && (
                      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[0.95em]">
                        {item.bullets.filter(Boolean).map((b, i) => (
                          <li key={i}>{b}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}

              {section.content.kind === "education" &&
                section.content.items.map((item) => (
                  <div key={item.id} className="mb-2 last:mb-0">
                    <div className="flex items-baseline justify-between gap-4">
                      <p className="font-semibold">
                        {item.degree}
                        {item.institution && <span className="font-normal"> · {item.institution}</span>}
                      </p>
                      <p className="shrink-0 text-[0.85em] text-slate-500">
                        {item.startDate} – {item.endDate}
                      </p>
                    </div>
                    {item.details && <p className="text-[0.9em]">{item.details}</p>}
                  </div>
                ))}

              {section.content.kind === "projects" &&
                section.content.items.map((item) => (
                  <div key={item.id} className="mb-3 last:mb-0">
                    <p className="font-semibold">
                      {item.name}
                      {item.link && <span className="font-normal text-slate-500"> · {item.link}</span>}
                    </p>
                    {item.description && <p className="text-[0.9em]">{item.description}</p>}
                    {item.bullets.filter(Boolean).length > 0 && (
                      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[0.95em]">
                        {item.bullets.filter(Boolean).map((b, i) => (
                          <li key={i}>{b}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}

              {section.content.kind === "certifications" &&
                section.content.items.map((item) => (
                  <div key={item.id} className="mb-1 flex items-baseline justify-between gap-4 last:mb-0">
                    <p>
                      <span className="font-semibold">{item.name}</span>
                      {item.issuer && ` · ${item.issuer}`}
                    </p>
                    <p className="shrink-0 text-[0.85em] text-slate-500">{item.date}</p>
                  </div>
                ))}

              {section.content.kind === "list" && (
                <p className="text-[0.95em]">
                  {section.content.items.map((i) => i.label).filter(Boolean).join("  ·  ")}
                </p>
              )}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
