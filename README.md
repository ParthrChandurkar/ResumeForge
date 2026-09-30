# ResumeForge

ResumeForge is a multi-user resume and cover-letter tailoring application. It uses a FastAPI backend and Gemini structured output to adapt user-provided documents to a job description while retaining account-level storage boundaries.

## Features

- Multiple resume variants per user
- Cover-letter template management
- Job-description keyword and skill analysis
- Generation rules intended to avoid fabricated experience
- ATS-oriented match and gap summaries
- PDF-oriented preview and Overleaf-compatible `.tex` export
- Per-user document history

## Architecture

- `frontend/`: React, Vite, and Tailwind CSS interface
- `backend/`: authentication, Gemini integration, document processing, storage, and exports
- `api/`: FastAPI deployment entry point
- `docker-compose.yml`: local frontend and backend orchestration

Authentication uses signed HTTP-only session cookies. Storage paths are namespaced by authenticated user ID.

## Getting Started

Copy `.env.example` to `.env` and provide `GEMINI_API_KEY`, `GEMINI_MODEL`, `SESSION_SECRET`, and `AUTH_USERS_JSON`. Do not commit populated environment files.

Start both services with Docker:

```bash
docker compose up --build
```

For separate development processes, start the backend:

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Then start the frontend:

```bash
cd frontend
npm install
npm run dev
```

## Verification

```bash
cd frontend
npm run build

cd ../backend
python -m compileall -q .
```

## Limitations

- AI-generated documents require human review.
- PDF and DOCX imports cannot preserve every source-layout instruction; original `.tex` files provide the strongest Overleaf fidelity.
- User accounts are configured by an administrator; public registration is not implemented.

