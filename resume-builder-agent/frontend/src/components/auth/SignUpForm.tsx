"use client";

import { useState, type FormEvent } from "react";
import { Sparkles, Eye, EyeOff } from "lucide-react";
import { useAuth } from "@/lib/auth/AuthContext";
import { api, ApiError } from "@/lib/api";
import { generateStrongPassword, isPasswordValid } from "@/lib/password";
import { COUNTRY_CODES } from "@/lib/countryCodes";
import { Button } from "@/components/ui/Button";
import { Input, Label, Select, FieldError } from "@/components/ui/Field";
import { PasswordStrengthMeter } from "@/components/auth/PasswordStrengthMeter";
import type { AddressType, Gender, SignUpPayload } from "@/lib/auth/types";

const INITIAL_FORM = {
  firstName: "",
  lastName: "",
  gender: "prefer_not_to_say" as Gender,
  addressType: "permanent" as AddressType,
  address: "",
  countryCode: "+1",
  phone: "",
  country: "",
  state: "",
  city: "",
  email: "",
  password: "",
  confirmPassword: "",
};

export function SignUpForm({ onSignedUp }: { onSignedUp: (email: string) => void }) {
  const { signOut } = useAuth();
  const [form, setForm] = useState(INITIAL_FORM);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function update<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function handleGeneratePassword() {
    const generated = generateStrongPassword();
    setForm((f) => ({ ...f, password: generated, confirmPassword: generated }));
    setShowPassword(true);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (!isPasswordValid(form.password)) {
      setError("Password doesn't meet the strength requirements yet.");
      return;
    }
    if (form.password !== form.confirmPassword) {
      setError("Passwords don't match.");
      return;
    }

    const payload: SignUpPayload = {
      first_name: form.firstName,
      last_name: form.lastName,
      gender: form.gender,
      address_type: form.addressType,
      address: form.address,
      country_code: form.countryCode,
      phone: form.phone,
      country: form.country,
      state: form.state,
      city: form.city,
      email: form.email,
      password: form.password,
    };

    setLoading(true);
    try {
      // Signing up authenticates immediately on the backend; sign back out
      // so the user lands on the Sign In screen as designed, with their
      // account already saved.
      await api.post("/auth/signup", payload);
      await signOut();
      onSignedUp(form.email);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="firstName">First name</Label>
          <Input
            id="firstName"
            required
            value={form.firstName}
            onChange={(e) => update("firstName", e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="lastName">Last name</Label>
          <Input
            id="lastName"
            required
            value={form.lastName}
            onChange={(e) => update("lastName", e.target.value)}
          />
        </div>
      </div>

      <div>
        <Label htmlFor="gender">Gender</Label>
        <Select
          id="gender"
          value={form.gender}
          onChange={(e) => update("gender", e.target.value as Gender)}
        >
          <option value="male">Male</option>
          <option value="female">Female</option>
          <option value="prefer_not_to_say">Prefer not to say</option>
        </Select>
      </div>

      <div>
        <Label htmlFor="address">Address</Label>
        <div className="flex gap-2">
          <div className="w-40 shrink-0">
            <Select
              value={form.addressType}
              onChange={(e) => update("addressType", e.target.value as AddressType)}
            >
              <option value="permanent">Permanent</option>
              <option value="temporary">Temporary</option>
            </Select>
          </div>
          <Input
            id="address"
            placeholder="Street, area"
            value={form.address}
            onChange={(e) => update("address", e.target.value)}
          />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          <Label htmlFor="country">Country</Label>
          <Input
            id="country"
            required
            value={form.country}
            onChange={(e) => update("country", e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="state">State</Label>
          <Input id="state" value={form.state} onChange={(e) => update("state", e.target.value)} />
        </div>
        <div>
          <Label htmlFor="city">City</Label>
          <Input id="city" value={form.city} onChange={(e) => update("city", e.target.value)} />
        </div>
      </div>

      <div>
        <Label htmlFor="phone">Phone number</Label>
        <div className="flex gap-2">
          <div className="w-32 shrink-0">
            <Select value={form.countryCode} onChange={(e) => update("countryCode", e.target.value)}>
              {COUNTRY_CODES.map((c) => (
                <option key={c.iso2} value={c.dialCode}>
                  {c.iso2} {c.dialCode}
                </option>
              ))}
            </Select>
          </div>
          <Input
            id="phone"
            type="tel"
            required
            placeholder="98765 43210"
            value={form.phone}
            onChange={(e) => update("phone", e.target.value)}
          />
        </div>
      </div>

      <div>
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          required
          value={form.email}
          onChange={(e) => update("email", e.target.value)}
          placeholder="you@example.com"
        />
      </div>

      <div>
        <div className="flex items-center justify-between">
          <Label htmlFor="password">Password</Label>
          <button
            type="button"
            onClick={handleGeneratePassword}
            className="mb-1 flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline"
          >
            <Sparkles size={12} /> Suggest a strong password
          </button>
        </div>
        <div className="relative">
          <Input
            id="password"
            type={showPassword ? "text" : "password"}
            required
            value={form.password}
            onChange={(e) => update("password", e.target.value)}
            className="pr-10"
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            aria-label={showPassword ? "Hide password" : "Show password"}
          >
            {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
        <PasswordStrengthMeter password={form.password} />
      </div>

      <div>
        <Label htmlFor="confirmPassword">Confirm password</Label>
        <Input
          id="confirmPassword"
          type={showPassword ? "text" : "password"}
          required
          value={form.confirmPassword}
          onChange={(e) => update("confirmPassword", e.target.value)}
        />
        <FieldError>
          {form.confirmPassword && form.confirmPassword !== form.password
            ? "Passwords don't match"
            : undefined}
        </FieldError>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <Button type="submit" className="w-full" loading={loading}>
        Create account
      </Button>
    </form>
  );
}
