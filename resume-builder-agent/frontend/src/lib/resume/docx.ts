import {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  AlignmentType,
  BorderStyle,
} from "docx";
import type { ResumeData } from "@/lib/resume/types";

function heading(text: string, accentHex: string): Paragraph {
  return new Paragraph({
    text,
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 80 },
    border: {
      bottom: { style: BorderStyle.SINGLE, size: 4, color: accentHex.replace("#", "") },
    },
  });
}

function bullet(text: string): Paragraph {
  return new Paragraph({ text, bullet: { level: 0 } });
}

export async function generateResumeDocxBlob(data: ResumeData, accentColor: string): Promise<Blob> {
  const accentHex = accentColor.replace("#", "") || "2563EB";
  const contactLine = [
    data.personal.email,
    data.personal.phone,
    data.personal.location,
    data.personal.linkedin,
    data.personal.website,
  ]
    .filter(Boolean)
    .join("   |   ");

  const children: Paragraph[] = [
    new Paragraph({
      alignment: AlignmentType.LEFT,
      children: [
        new TextRun({ text: data.personal.fullName || "Your Name", bold: true, size: 44, color: accentHex }),
      ],
    }),
  ];

  if (data.personal.headline) {
    children.push(new Paragraph({ children: [new TextRun({ text: data.personal.headline, size: 24 })] }));
  }
  if (contactLine) {
    children.push(
      new Paragraph({ children: [new TextRun({ text: contactLine, size: 20, color: "64748B" })] })
    );
  }

  for (const section of data.sections.filter((s) => s.visible)) {
    children.push(heading(section.title, accentHex));

    if (section.content.kind === "text" && section.content.text) {
      children.push(new Paragraph({ text: section.content.text }));
    }

    if (section.content.kind === "experience") {
      for (const item of section.content.items) {
        children.push(
          new Paragraph({
            children: [
              new TextRun({ text: `${item.role}${item.company ? " · " + item.company : ""}`, bold: true }),
              new TextRun({
                text: `   ${item.startDate} – ${item.current ? "Present" : item.endDate}`,
                color: "64748B",
              }),
            ],
          })
        );
        item.bullets.filter(Boolean).forEach((b) => children.push(bullet(b)));
      }
    }

    if (section.content.kind === "education") {
      for (const item of section.content.items) {
        children.push(
          new Paragraph({
            children: [
              new TextRun({
                text: `${item.degree}${item.institution ? " · " + item.institution : ""}`,
                bold: true,
              }),
              new TextRun({ text: `   ${item.startDate} – ${item.endDate}`, color: "64748B" }),
            ],
          })
        );
        if (item.details) children.push(new Paragraph({ text: item.details }));
      }
    }

    if (section.content.kind === "projects") {
      for (const item of section.content.items) {
        children.push(
          new Paragraph({
            children: [
              new TextRun({ text: `${item.name}${item.link ? " · " + item.link : ""}`, bold: true }),
            ],
          })
        );
        if (item.description) children.push(new Paragraph({ text: item.description }));
        item.bullets.filter(Boolean).forEach((b) => children.push(bullet(b)));
      }
    }

    if (section.content.kind === "certifications") {
      for (const item of section.content.items) {
        children.push(
          new Paragraph({
            text: `${item.name}${item.issuer ? " · " + item.issuer : ""}${item.date ? "   " + item.date : ""}`,
          })
        );
      }
    }

    if (section.content.kind === "list") {
      const line = section.content.items.map((i) => i.label).filter(Boolean).join("   ·   ");
      if (line) children.push(new Paragraph({ text: line }));
    }
  }

  const doc = new Document({ sections: [{ children }] });
  return Packer.toBlob(doc);
}
