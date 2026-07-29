"use client";

import type { PersonalInfo } from "@/lib/resume/types";
import { Input, Label } from "@/components/ui/Field";

export function PersonalInfoEditor({
  personal,
  onChange,
}: {
  personal: PersonalInfo;
  onChange: (personal: PersonalInfo) => void;
}) {
  function update<K extends keyof PersonalInfo>(key: K, value: PersonalInfo[K]) {
    onChange({ ...personal, [key]: value });
  }

  return (
    <div className="space-y-3">
      <div>
        <Label htmlFor="pi-name">Full name</Label>
        <Input id="pi-name" value={personal.fullName} onChange={(e) => update("fullName", e.target.value)} />
      </div>
      <div>
        <Label htmlFor="pi-headline">Headline / target role</Label>
        <Input
          id="pi-headline"
          value={personal.headline}
          onChange={(e) => update("headline", e.target.value)}
          placeholder="e.g. Senior Frontend Engineer"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="pi-email">Email</Label>
          <Input id="pi-email" value={personal.email} onChange={(e) => update("email", e.target.value)} />
        </div>
        <div>
          <Label htmlFor="pi-phone">Phone</Label>
          <Input id="pi-phone" value={personal.phone} onChange={(e) => update("phone", e.target.value)} />
        </div>
      </div>
      <div>
        <Label htmlFor="pi-location">Location</Label>
        <Input
          id="pi-location"
          value={personal.location}
          onChange={(e) => update("location", e.target.value)}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="pi-linkedin">LinkedIn</Label>
          <Input
            id="pi-linkedin"
            value={personal.linkedin}
            onChange={(e) => update("linkedin", e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="pi-website">Website / portfolio</Label>
          <Input
            id="pi-website"
            value={personal.website}
            onChange={(e) => update("website", e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
