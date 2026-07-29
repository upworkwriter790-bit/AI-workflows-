"use client";

import type { ResumeStyles } from "@/lib/resume/types";
import { FONT_OPTIONS } from "@/lib/resume/types";
import { Label, Select } from "@/components/ui/Field";

function Slider({
  label,
  value,
  min,
  max,
  step,
  suffix,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix: string;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <Label>{label}</Label>
        <span className="text-xs text-slate-500">
          {value}
          {suffix}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-blue-600"
      />
    </div>
  );
}

export function StylePanel({
  styles,
  onChange,
}: {
  styles: ResumeStyles;
  onChange: (styles: ResumeStyles) => void;
}) {
  function update<K extends keyof ResumeStyles>(key: K, value: ResumeStyles[K]) {
    onChange({ ...styles, [key]: value });
  }

  return (
    <div className="space-y-4">
      <div>
        <Label>Font</Label>
        <Select value={styles.fontFamily} onChange={(e) => update("fontFamily", e.target.value)}>
          {FONT_OPTIONS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </Select>
      </div>

      <Slider
        label="Font size"
        value={styles.fontSizePt}
        min={8.5}
        max={13}
        step={0.5}
        suffix="pt"
        onChange={(v) => update("fontSizePt", v)}
      />

      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label>Text color</Label>
          <input
            type="color"
            value={styles.textColor}
            onChange={(e) => update("textColor", e.target.value)}
            className="h-9 w-full cursor-pointer rounded-lg border border-slate-300"
          />
        </div>
        <div>
          <Label>Accent color</Label>
          <input
            type="color"
            value={styles.accentColor}
            onChange={(e) => update("accentColor", e.target.value)}
            className="h-9 w-full cursor-pointer rounded-lg border border-slate-300"
          />
        </div>
      </div>

      <Slider
        label="Line spacing"
        value={styles.lineSpacing}
        min={1}
        max={2}
        step={0.05}
        suffix="×"
        onChange={(v) => update("lineSpacing", v)}
      />
      <Slider
        label="Letter spacing"
        value={styles.letterSpacingPx}
        min={-0.5}
        max={2}
        step={0.1}
        suffix="px"
        onChange={(v) => update("letterSpacingPx", v)}
      />
      <Slider
        label="Word spacing"
        value={styles.wordSpacingPx}
        min={0}
        max={8}
        step={0.5}
        suffix="px"
        onChange={(v) => update("wordSpacingPx", v)}
      />
    </div>
  );
}
