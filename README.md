# 🔥 ResumeForge

**Forge a Role-specific resume and personalized cover letter from one job description—without inventing experience or losing your established document style.**

ResumeForge is a private, multi-user application studio powered by Gemini. Each approved user maintains an isolated collection of resume variants, one cover-letter template, and a personal tailoring history.

## ✨ Highlights

- 🎯 **JD-aware tailoring** — extracts the role's strongest skills and keywords.
- 📄 **Multiple resume variants** — keep technical, consulting, product, or other specialized versions.
- ✉️ **Personalized cover letters** — follows the user's uploaded letter structure and tone.
- 🛡️ **Truth-first AI rules** — reframes existing evidence without fabricating achievements.
- 🔒 **Private user workspaces** — templates and generated documents never cross accounts.
- 📊 **ATS match insights** — shows matched keywords, genuine gaps, and tailoring decisions.
- 🔗 **Working hyperlinks** — contact, publication, portfolio, and certificate links remain clickable.
- 🧾 **Export options** — print-ready PDF output and Overleaf-compatible `.tex` downloads.
- 🕘 **Private history** — reopen recent document sets without regenerating them.

## 🧭 Workflow

1. Sign in with an administrator-provided account.
2. Upload one or more resume templates.
3. Upload one cover-letter template.
4. Choose a resume and paste the complete job description.
5. Generate, review, and export both tailored documents.

> For the closest possible Overleaf reproduction, upload the original `.tex` source. PDF and DOCX uploads preserve readable content and hyperlink references, but compiled PDFs do not expose every original layout command.

## 🧰 Stack

| Layer | Technology |
| --- | --- |
| Frontend | React, Vite, Tailwind CSS |
| Backend | FastAPI, Python |
| AI | Google Gemini with structured output |
| Storage | Local filesystem or private object storage |
| Authentication | Signed, HTTP-only session cookies |
| Documents | PDF, DOCX, TXT, and Overleaf TEX |

## 🚀 Local setup

### 1. Configure environment variables

Copy `.env.example` to `.env` and add your own values:

```env
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-3.5-flash-lite
SESSION_SECRET=at_least_32_random_characters
AUTH_USERS_JSON=[{"id":"user1","name":"User One","email":"user@example.com","password":"change-me"}]
```

Never commit `.env` or real credentials.

### 2. Start the backend

```powershell
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

### 3. Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

Alternatively, run both services with Docker:

```bash
docker compose up --build
```

## 🔐 Security model

- There is no public registration endpoint.
- Approved accounts are supplied through environment secrets.
- Passwords and API keys are excluded from the repository.
- Authentication cookies are HTTP-only, signed, expiring, and secure in production.
- Every storage path is namespaced by the authenticated user ID.
- Private templates require an authenticated API request to download.

## 🧪 Quality checks

```powershell
cd frontend
npm run build

cd ..\backend
python -m compileall -q .
```

## 📁 Project structure

```text
ResumeForge/
├── api/                  # FastAPI application entrypoint
├── backend/              # Auth, AI, storage, templates, exports
├── frontend/             # React application studio
├── docker-compose.yml
└── README.md
```

## 📜 License

This project is provided for personal and educational use. Review third-party model and hosting terms before wider distribution.
