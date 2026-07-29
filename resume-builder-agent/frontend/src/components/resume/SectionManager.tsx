"use client";

import { useState } from "react";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ChevronDown, Eye, EyeOff, GripVertical, Plus, Trash2 } from "lucide-react";
import type { ResumeSection } from "@/lib/resume/types";
import { blankSection, SECTION_TYPE_OPTIONS } from "@/lib/resume/factories";
import { SectionContentEditor } from "@/components/resume/SectionContentEditor";
import { Input } from "@/components/ui/Field";

function SortableSection({
  section,
  expanded,
  onToggleExpand,
  onChange,
  onRemove,
}: {
  section: ResumeSection;
  expanded: boolean;
  onToggleExpand: () => void;
  onChange: (section: ResumeSection) => void;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: section.id,
  });

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }}
      className="rounded-xl border border-slate-200 bg-white"
    >
      <div className="flex items-center gap-2 px-3 py-2">
        <button
          {...attributes}
          {...listeners}
          className="cursor-grab text-slate-400 hover:text-slate-600 active:cursor-grabbing"
          aria-label="Drag to reorder"
        >
          <GripVertical size={16} />
        </button>

        <Input
          value={section.title}
          onChange={(e) => onChange({ ...section, title: e.target.value })}
          className="!py-1"
        />

        <button
          onClick={() => onChange({ ...section, visible: !section.visible })}
          className="text-slate-400 hover:text-slate-600"
          aria-label={section.visible ? "Hide section" : "Show section"}
          title={section.visible ? "Visible on resume" : "Hidden from resume"}
        >
          {section.visible ? <Eye size={16} /> : <EyeOff size={16} />}
        </button>

        <button onClick={onRemove} className="text-slate-400 hover:text-red-600" aria-label="Delete section">
          <Trash2 size={16} />
        </button>

        <button
          onClick={onToggleExpand}
          className="text-slate-400 hover:text-slate-600"
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          <ChevronDown size={16} className={`transition-transform ${expanded ? "rotate-180" : ""}`} />
        </button>
      </div>

      {expanded && (
        <div className="border-t border-slate-100 p-3">
          <SectionContentEditor
            content={section.content}
            onChange={(content) => onChange({ ...section, content })}
          />
        </div>
      )}
    </div>
  );
}

export function SectionManager({
  sections,
  onChange,
}: {
  sections: ResumeSection[];
  onChange: (sections: ResumeSection[]) => void;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(sections[0]?.id ?? null);
  const [addOpen, setAddOpen] = useState(false);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = sections.findIndex((s) => s.id === active.id);
    const newIndex = sections.findIndex((s) => s.id === over.id);
    onChange(arrayMove(sections, oldIndex, newIndex));
  }

  return (
    <div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={sections.map((s) => s.id)} strategy={verticalListSortingStrategy}>
          <div className="space-y-2">
            {sections.map((section) => (
              <SortableSection
                key={section.id}
                section={section}
                expanded={expandedId === section.id}
                onToggleExpand={() => setExpandedId(expandedId === section.id ? null : section.id)}
                onChange={(updated) => onChange(sections.map((s) => (s.id === updated.id ? updated : s)))}
                onRemove={() => onChange(sections.filter((s) => s.id !== section.id))}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      <div className="relative mt-3">
        <button
          onClick={() => setAddOpen((v) => !v)}
          className="flex w-full items-center justify-center gap-1 rounded-lg border border-dashed border-slate-300 py-2 text-sm text-slate-600 hover:border-blue-400 hover:text-blue-600"
        >
          <Plus size={14} /> Add section
        </button>
        {addOpen && (
          <div className="absolute z-10 mt-1 w-full rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
            {SECTION_TYPE_OPTIONS.map((opt) => (
              <button
                key={opt.type}
                onClick={() => {
                  const section = blankSection(opt.type);
                  onChange([...sections, section]);
                  setExpandedId(section.id);
                  setAddOpen(false);
                }}
                className="block w-full rounded-md px-3 py-1.5 text-left text-sm hover:bg-slate-50"
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
