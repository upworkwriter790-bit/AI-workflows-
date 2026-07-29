"use client";

import { useState } from "react";
import { saveAs } from "file-saver";
import { ChevronDown, Download } from "lucide-react";
import type { ResumeData, ResumeStyles } from "@/lib/resume/types";
import { generateResumePdfBlob } from "@/lib/resume/pdf";
import { generateResumeDocxBlob } from "@/lib/resume/docx";
import { Button } from "@/components/ui/Button";

export function DownloadMenu({
  title,
  templateId,
  data,
  styles,
}: {
  title: string;
  templateId: string;
  data: ResumeData;
  styles: ResumeStyles;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<"pdf" | "docx" | null>(null);

  const fileBase = (title || "resume").replace(/[^a-z0-9-_]+/gi, "_");

  async function downloadPdf() {
    setBusy("pdf");
    try {
      const blob = await generateResumePdfBlob(templateId, data, styles);
      saveAs(blob, `${fileBase}.pdf`);
    } finally {
      setBusy(null);
      setOpen(false);
    }
  }

  async function downloadDocx() {
    setBusy("docx");
    try {
      const blob = await generateResumeDocxBlob(data, styles.accentColor);
      saveAs(blob, `${fileBase}.docx`);
    } finally {
      setBusy(null);
      setOpen(false);
    }
  }

  return (
    <div className="relative">
      <Button variant="secondary" onClick={() => setOpen((v) => !v)} loading={busy !== null}>
        <Download size={16} /> Download <ChevronDown size={14} />
      </Button>
      {open && (
        <div className="absolute right-0 z-10 mt-1 w-40 rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
          <button
            onClick={downloadPdf}
            className="block w-full rounded-md px-3 py-1.5 text-left text-sm hover:bg-slate-50"
          >
            Download PDF
          </button>
          <button
            onClick={downloadDocx}
            className="block w-full rounded-md px-3 py-1.5 text-left text-sm hover:bg-slate-50"
          >
            Download Word (.docx)
          </button>
        </div>
      )}
    </div>
  );
}
