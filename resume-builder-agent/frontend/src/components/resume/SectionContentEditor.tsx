"use client";

import { Plus, Trash2 } from "lucide-react";
import type { SectionContent } from "@/lib/resume/types";
import {
  blankCertification,
  blankEducation,
  blankExperience,
  blankProject,
  blankSimpleEntry,
} from "@/lib/resume/factories";
import { Input, Label } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";

function BulletsEditor({ bullets, onChange }: { bullets: string[]; onChange: (b: string[]) => void }) {
  return (
    <div>
      <Label>Bullet points (one per line)</Label>
      <textarea
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
        rows={3}
        value={bullets.join("\n")}
        onChange={(e) => onChange(e.target.value.split("\n"))}
      />
    </div>
  );
}

export function SectionContentEditor({
  content,
  onChange,
}: {
  content: SectionContent;
  onChange: (content: SectionContent) => void;
}) {
  if (content.kind === "text") {
    return (
      <textarea
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
        rows={4}
        value={content.text}
        onChange={(e) => onChange({ kind: "text", text: e.target.value })}
        placeholder="Write a short summary…"
      />
    );
  }

  if (content.kind === "experience") {
    return (
      <div className="space-y-4">
        {content.items.map((item, idx) => (
          <div key={item.id} className="rounded-lg border border-slate-200 p-3">
            <div className="mb-2 flex justify-end">
              <button
                onClick={() =>
                  onChange({ kind: "experience", items: content.items.filter((i) => i.id !== item.id) })
                }
                className="text-slate-400 hover:text-red-600"
                aria-label="Remove entry"
              >
                <Trash2 size={16} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Input
                placeholder="Role / title"
                value={item.role}
                onChange={(e) => {
                  const items = [...content.items];
                  items[idx] = { ...item, role: e.target.value };
                  onChange({ kind: "experience", items });
                }}
              />
              <Input
                placeholder="Company"
                value={item.company}
                onChange={(e) => {
                  const items = [...content.items];
                  items[idx] = { ...item, company: e.target.value };
                  onChange({ kind: "experience", items });
                }}
              />
              <Input
                placeholder="Location"
                value={item.location}
                onChange={(e) => {
                  const items = [...content.items];
                  items[idx] = { ...item, location: e.target.value };
                  onChange({ kind: "experience", items });
                }}
              />
              <div className="flex gap-2">
                <Input
                  placeholder="Start (e.g. 2021)"
                  value={item.startDate}
                  onChange={(e) => {
                    const items = [...content.items];
                    items[idx] = { ...item, startDate: e.target.value };
                    onChange({ kind: "experience", items });
                  }}
                />
                <Input
                  placeholder="End"
                  value={item.endDate}
                  disabled={item.current}
                  onChange={(e) => {
                    const items = [...content.items];
                    items[idx] = { ...item, endDate: e.target.value };
                    onChange({ kind: "experience", items });
                  }}
                />
              </div>
            </div>
            <label className="mt-2 flex items-center gap-2 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={item.current}
                onChange={(e) => {
                  const items = [...content.items];
                  items[idx] = { ...item, current: e.target.checked };
                  onChange({ kind: "experience", items });
                }}
              />
              I currently work here
            </label>
            <div className="mt-2">
              <BulletsEditor
                bullets={item.bullets}
                onChange={(bullets) => {
                  const items = [...content.items];
                  items[idx] = { ...item, bullets };
                  onChange({ kind: "experience", items });
                }}
              />
            </div>
          </div>
        ))}
        <Button
          variant="outline"
          className="w-full"
          onClick={() => onChange({ kind: "experience", items: [...content.items, blankExperience()] })}
        >
          <Plus size={14} /> Add experience
        </Button>
      </div>
    );
  }

  if (content.kind === "education") {
    return (
      <div className="space-y-4">
        {content.items.map((item, idx) => (
          <div key={item.id} className="rounded-lg border border-slate-200 p-3">
            <div className="mb-2 flex justify-end">
              <button
                onClick={() =>
                  onChange({ kind: "education", items: content.items.filter((i) => i.id !== item.id) })
                }
                className="text-slate-400 hover:text-red-600"
                aria-label="Remove entry"
              >
                <Trash2 size={16} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Input
                placeholder="Degree"
                value={item.degree}
                onChange={(e) => {
                  const items = [...content.items];
                  items[idx] = { ...item, degree: e.target.value };
                  onChange({ kind: "education", items });
                }}
              />
              <Input
                placeholder="Institution"
                value={item.institution}
                onChange={(e) => {
                  const items = [...content.items];
                  items[idx] = { ...item, institution: e.target.value };
                  onChange({ kind: "education", items });
                }}
              />
              <Input
                placeholder="Start"
                value={item.startDate}
                onChange={(e) => {
                  const items = [...content.items];
                  items[idx] = { ...item, startDate: e.target.value };
                  onChange({ kind: "education", items });
                }}
              />
              <Input
                placeholder="End"
                value={item.endDate}
                onChange={(e) => {
                  const items = [...content.items];
                  items[idx] = { ...item, endDate: e.target.value };
                  onChange({ kind: "education", items });
                }}
              />
            </div>
            <Input
              className="mt-2"
              placeholder="Details (GPA, honors…)"
              value={item.details}
              onChange={(e) => {
                const items = [...content.items];
                items[idx] = { ...item, details: e.target.value };
                onChange({ kind: "education", items });
              }}
            />
          </div>
        ))}
        <Button
          variant="outline"
          className="w-full"
          onClick={() => onChange({ kind: "education", items: [...content.items, blankEducation()] })}
        >
          <Plus size={14} /> Add education
        </Button>
      </div>
    );
  }

  if (content.kind === "projects") {
    return (
      <div className="space-y-4">
        {content.items.map((item, idx) => (
          <div key={item.id} className="rounded-lg border border-slate-200 p-3">
            <div className="mb-2 flex justify-end">
              <button
                onClick={() =>
                  onChange({ kind: "projects", items: content.items.filter((i) => i.id !== item.id) })
                }
                className="text-slate-400 hover:text-red-600"
                aria-label="Remove entry"
              >
                <Trash2 size={16} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Input
                placeholder="Project name"
                value={item.name}
                onChange={(e) => {
                  const items = [...content.items];
                  items[idx] = { ...item, name: e.target.value };
                  onChange({ kind: "projects", items });
                }}
              />
              <Input
                placeholder="Link (optional)"
                value={item.link}
                onChange={(e) => {
                  const items = [...content.items];
                  items[idx] = { ...item, link: e.target.value };
                  onChange({ kind: "projects", items });
                }}
              />
            </div>
            <Input
              className="mt-2"
              placeholder="One-line description"
              value={item.description}
              onChange={(e) => {
                const items = [...content.items];
                items[idx] = { ...item, description: e.target.value };
                onChange({ kind: "projects", items });
              }}
            />
            <div className="mt-2">
              <BulletsEditor
                bullets={item.bullets}
                onChange={(bullets) => {
                  const items = [...content.items];
                  items[idx] = { ...item, bullets };
                  onChange({ kind: "projects", items });
                }}
              />
            </div>
          </div>
        ))}
        <Button
          variant="outline"
          className="w-full"
          onClick={() => onChange({ kind: "projects", items: [...content.items, blankProject()] })}
        >
          <Plus size={14} /> Add project
        </Button>
      </div>
    );
  }

  if (content.kind === "certifications") {
    return (
      <div className="space-y-3">
        {content.items.map((item, idx) => (
          <div key={item.id} className="flex items-center gap-2">
            <Input
              placeholder="Certification name"
              value={item.name}
              onChange={(e) => {
                const items = [...content.items];
                items[idx] = { ...item, name: e.target.value };
                onChange({ kind: "certifications", items });
              }}
            />
            <Input
              placeholder="Issuer"
              value={item.issuer}
              onChange={(e) => {
                const items = [...content.items];
                items[idx] = { ...item, issuer: e.target.value };
                onChange({ kind: "certifications", items });
              }}
            />
            <Input
              placeholder="Date"
              className="w-28"
              value={item.date}
              onChange={(e) => {
                const items = [...content.items];
                items[idx] = { ...item, date: e.target.value };
                onChange({ kind: "certifications", items });
              }}
            />
            <button
              onClick={() =>
                onChange({ kind: "certifications", items: content.items.filter((i) => i.id !== item.id) })
              }
              className="text-slate-400 hover:text-red-600"
              aria-label="Remove entry"
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
        <Button
          variant="outline"
          className="w-full"
          onClick={() =>
            onChange({ kind: "certifications", items: [...content.items, blankCertification()] })
          }
        >
          <Plus size={14} /> Add certification
        </Button>
      </div>
    );
  }

  // list (skills / languages / awards)
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {content.items.map((item, idx) => (
          <div key={item.id} className="flex items-center gap-1 rounded-full bg-slate-100 pl-3 pr-1 py-1">
            <input
              className="w-28 bg-transparent text-sm outline-none"
              value={item.label}
              placeholder="e.g. Python"
              onChange={(e) => {
                const items = [...content.items];
                items[idx] = { ...item, label: e.target.value };
                onChange({ kind: "list", items });
              }}
            />
            <button
              onClick={() => onChange({ kind: "list", items: content.items.filter((i) => i.id !== item.id) })}
              className="text-slate-400 hover:text-red-600"
              aria-label="Remove"
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>
      <Button
        variant="outline"
        onClick={() => onChange({ kind: "list", items: [...content.items, blankSimpleEntry()] })}
      >
        <Plus size={14} /> Add item
      </Button>
    </div>
  );
}
