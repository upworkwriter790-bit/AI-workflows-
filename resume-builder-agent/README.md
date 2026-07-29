# Resume Builder Agent

Build a new resume from an ATS-verified template, or improve one you already
have — fill in your details once, fine-tune fonts/colors/spacing, and export
a clean PDF or Word document.

**Stack:** Next.js (frontend) + FastAPI (backend) + PostgreSQL (database).

```
resume-builder-agent/
├── frontend/   # Next.js app (auth UI, template gallery, resume editor)
└── backend/    # FastAPI app (auth, profile, resumes API)
```

## What's implemented so far

- **Auth**: sign up (name, gender, address, country code + phone, location,
  email, password) with a live strength meter and a "suggest a strong
  password" generator. Email/password sign-in, plus Google and GitHub OAuth.
  Signing up logs you in once server-side, then hands you back to the Sign In
  screen with your email pre-filled, matching the flow you described.
- **Dashboard**: your saved profile info, and a "Resume Builder" section with
  **New resume** (template gallery) or **Upload a resume** (PDF/Word).
- **Templates**: five single-column, ATS-safe templates (Modern, Classic,
  Minimal, Professional, Compact) — no multi-column layouts, since those are
  what typically break applicant tracking system parsers.
- **Editor**: personal info auto-filled from your profile, drag-to-reorder
  sections you can rename/hide/delete/add (experience, education, skills,
  projects, certifications, languages, custom text), and a design panel for
  font, size, text/accent color, and line/letter/word spacing — all reflected
  live in the preview.
- **Save**: explicit Save button, persisted to Postgres via the FastAPI
  backend (no autosave-only guessing about what got kept).
- **Download**: PDF (via `@react-pdf/renderer`, real selectable text — not a
  screenshot) or Word `.docx` (via the `docx` package).

## Running it locally

### 1. Database

You need a running PostgreSQL instance. Quickest option locally:

```bash
createdb resume_builder
```

### 2. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL / JWT_SECRET at minimum
uvicorn app.main:app --reload --port 8000
```

Tables are created automatically on startup. For real schema migrations
later, switch to Alembic (already in `requirements.txt`).

### 3. Frontend (Next.js)

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open http://localhost:3000.

### 4. Google / GitHub sign-in (optional)

These need OAuth app credentials only you can create:

- **Google**: [Google Cloud Console](https://console.cloud.google.com/) →
  APIs & Services → Credentials → OAuth client ID (Web application).
  Authorized redirect URI: `http://localhost:8000/auth/google/callback`.
- **GitHub**: GitHub → Settings → Developer settings → OAuth Apps → New OAuth
  App. Authorization callback URL:
  `http://localhost:8000/auth/github/callback`.

Paste the client ID/secret pairs into `backend/.env`. Email/password sign-in
works fully without either of these.

## Notes on "Upload a resume"

Uploading currently stores your original PDF/Word file as-is (validated,
size-capped at 10 MB) and drops you into the same structured editor, seeded
from your profile, so you can rebuild it in a template rather than staring at
a blank page. Parsing the uploaded file's content automatically into the
editor is a natural next step — flagged here since it wasn't in scope yet.

## What's next

This is the first slice — auth, templates, the editor, save/download. Further
features (resume parsing on upload, additional templates, richer profile
management, etc.) can layer on top of this foundation.
