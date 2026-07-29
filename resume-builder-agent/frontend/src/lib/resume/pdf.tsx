import { Document, Page, View, Text, StyleSheet, Font, pdf } from "@react-pdf/renderer";
import type { ResumeData, ResumeStyles } from "@/lib/resume/types";
import { getTemplate } from "@/lib/resume/templates";

// react-pdf ships Helvetica / Times-Roman / Courier without needing to fetch
// font files, which keeps PDF export reliable offline. Map our style picker
// onto the closest built-in family instead of loading remote TTFs.
function pdfFontFamily(fontFamily: string): string {
  const f = fontFamily.toLowerCase();
  if (f.includes("times") || f.includes("georgia") || f.includes("garamond")) return "Times-Roman";
  if (f.includes("courier")) return "Courier";
  return "Helvetica";
}

Font.registerHyphenationCallback((word) => [word]);

function buildStyles(styles: ResumeStyles, templateId: string) {
  const template = getTemplate(templateId);
  const accent = styles.accentColor || template.accentColor;
  const fontFamily = pdfFontFamily(styles.fontFamily || template.fontFamily);
  const fontSize = styles.fontSizePt;

  return StyleSheet.create({
    page: {
      padding: 42,
      fontFamily,
      fontSize,
      color: styles.textColor,
      lineHeight: styles.lineSpacing,
    },
    headerCenter: { textAlign: templateId === "classic" ? "center" : "left", marginBottom: 16 },
    name: { fontSize: fontSize * 2, fontWeight: 700, color: accent },
    headline: { fontSize: fontSize * 1.05, color: "#475569", marginTop: 2 },
    contact: { fontSize: fontSize * 0.85, color: "#64748b", marginTop: 6 },
    section: { marginBottom: 14 },
    heading: {
      fontSize: fontSize * 0.95,
      fontWeight: 700,
      color: accent,
      marginBottom: 6,
      textTransform: templateId === "classic" || templateId === "professional" ? "uppercase" : "none",
      borderBottomWidth: 1,
      borderBottomColor: accent,
      paddingBottom: 3,
    },
    itemRow: { flexDirection: "row", justifyContent: "space-between" },
    itemTitle: { fontWeight: 700 },
    itemMeta: { fontSize: fontSize * 0.85, color: "#64748b" },
    bullet: { flexDirection: "row", marginTop: 2 },
    bulletDot: { width: 10, fontSize },
    bulletText: { flex: 1, fontSize },
    para: { fontSize },
    itemBlock: { marginBottom: 8 },
  });
}

function ResumePdfDocument({
  templateId,
  data,
  styles,
}: {
  templateId: string;
  data: ResumeData;
  styles: ResumeStyles;
}) {
  const s = buildStyles(styles, templateId);
  const visibleSections = data.sections.filter((sec) => sec.visible);
  const contactLine = [
    data.personal.email,
    data.personal.phone,
    data.personal.location,
    data.personal.linkedin,
    data.personal.website,
  ]
    .filter(Boolean)
    .join("   •   ");

  return (
    <Document title={data.personal.fullName || "Resume"}>
      <Page size="LETTER" style={s.page}>
        <View style={s.headerCenter}>
          <Text style={s.name}>{data.personal.fullName || "Your Name"}</Text>
          {data.personal.headline ? <Text style={s.headline}>{data.personal.headline}</Text> : null}
          {contactLine ? <Text style={s.contact}>{contactLine}</Text> : null}
        </View>

        {visibleSections.map((section) => (
          <View key={section.id} style={s.section} wrap={false}>
            <Text style={s.heading}>{section.title}</Text>

            {section.content.kind === "text" && <Text style={s.para}>{section.content.text}</Text>}

            {section.content.kind === "experience" &&
              section.content.items.map((item) => (
                <View key={item.id} style={s.itemBlock}>
                  <View style={s.itemRow}>
                    <Text style={s.itemTitle}>
                      {item.role}
                      {item.company ? ` · ${item.company}` : ""}
                    </Text>
                    <Text style={s.itemMeta}>
                      {item.startDate} – {item.current ? "Present" : item.endDate}
                    </Text>
                  </View>
                  {item.location ? <Text style={s.itemMeta}>{item.location}</Text> : null}
                  {item.bullets.filter(Boolean).map((b, i) => (
                    <View key={i} style={s.bullet}>
                      <Text style={s.bulletDot}>•</Text>
                      <Text style={s.bulletText}>{b}</Text>
                    </View>
                  ))}
                </View>
              ))}

            {section.content.kind === "education" &&
              section.content.items.map((item) => (
                <View key={item.id} style={s.itemBlock}>
                  <View style={s.itemRow}>
                    <Text style={s.itemTitle}>
                      {item.degree}
                      {item.institution ? ` · ${item.institution}` : ""}
                    </Text>
                    <Text style={s.itemMeta}>
                      {item.startDate} – {item.endDate}
                    </Text>
                  </View>
                  {item.details ? <Text style={s.para}>{item.details}</Text> : null}
                </View>
              ))}

            {section.content.kind === "projects" &&
              section.content.items.map((item) => (
                <View key={item.id} style={s.itemBlock}>
                  <Text style={s.itemTitle}>
                    {item.name}
                    {item.link ? ` · ${item.link}` : ""}
                  </Text>
                  {item.description ? <Text style={s.para}>{item.description}</Text> : null}
                  {item.bullets.filter(Boolean).map((b, i) => (
                    <View key={i} style={s.bullet}>
                      <Text style={s.bulletDot}>•</Text>
                      <Text style={s.bulletText}>{b}</Text>
                    </View>
                  ))}
                </View>
              ))}

            {section.content.kind === "certifications" &&
              section.content.items.map((item) => (
                <View key={item.id} style={s.itemRow}>
                  <Text style={s.para}>
                    {item.name}
                    {item.issuer ? ` · ${item.issuer}` : ""}
                  </Text>
                  <Text style={s.itemMeta}>{item.date}</Text>
                </View>
              ))}

            {section.content.kind === "list" && (
              <Text style={s.para}>
                {section.content.items.map((i) => i.label).filter(Boolean).join("   ·   ")}
              </Text>
            )}
          </View>
        ))}
      </Page>
    </Document>
  );
}

export async function generateResumePdfBlob(
  templateId: string,
  data: ResumeData,
  styles: ResumeStyles
): Promise<Blob> {
  return pdf(<ResumePdfDocument templateId={templateId} data={data} styles={styles} />).toBlob();
}
