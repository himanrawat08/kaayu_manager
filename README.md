# Kaayu Studio Manager

Internal studio management tool for Kaayu Studio LLP. Built with FastAPI + Jinja2 templates, deployed on Railway with Supabase (PostgreSQL + file storage).

## Stack

- **Backend:** FastAPI (Python), SQLAlchemy ORM, PostgreSQL (Supabase)
- **Frontend:** Jinja2 templates, Tailwind CSS
- **Storage:** Supabase Storage (design files, production files)
- **Deployment:** Railway (Python 3.12)

## Features

- Projects pipeline (Design → Production stages)
- Quotations with PDF generation
- Design file management (upload, mark sent/final, feedback)
- Production file management by category
- Yarn stock tracker
- Contacts / phonebook
- User management with roles
- Activity log
- Social media planner

---

## Changelog

### 2026-03-23

| Commit | Description |
|--------|-------------|
| `e36dd4b` | **Auth fix:** Replace `BaseHTTPMiddleware` auth guard with pure ASGI middleware. `BaseHTTPMiddleware` has known reliability issues in newer Starlette versions where it can silently fail to intercept requests. Pure ASGI reads `scope["session"]` directly, which is always populated by `SessionMiddleware`. |
| `11c89eb` | **Design file card overflow fix (attempt 2):** Add `min-w-0 overflow-hidden` to the file card `div` (the grid item). Grid items default to `min-width: auto`, which was preventing the inner flex truncation from working. |
| `71c7ab0` | **Design file card overflow fix (attempt 1):** Add `flex-1 min-w-0` to the filename `<span>` inside the design file card so `truncate` works correctly in a flex context. |
| `1498808` | **Projects list mobile layout:** Increase table `min-w` from 560px → 700px; hide description text on mobile (`hidden sm:block`); add `whitespace-nowrap` to Contact, Stage, Status, Updated columns to prevent wrapping within cells. |

### 2026-03-22

| Commit | Description |
|--------|-------------|
| `674b21f` | **Project detail mobile layout:** Restructure header (back link + actions on top row, title full-width below); add horizontal scroll to pipeline stepper; fix stage notes form width; wrap quotations, production files tables in `overflow-x-auto`; fix design/production upload forms to stack vertically; fix production details grid to `grid-cols-1 sm:grid-cols-2`. |
| `44edca5` | **Mobile layout audit — all templates:** Fixes across leads pipeline (kanban stacks vertically on mobile), social planner (sidebar stacks), yarn master + history tables (overflow-x-auto), contacts/projects/quotes/users lists (touch-friendly action buttons, whitespace-nowrap). |
| `cefb8f7` | **Phonebook mobile:** Add `overflow-x-auto` + `min-w-[600px]` to table; change search input from fixed `w-96` to `flex-1`. |
| `daf1beb` | **Yarn lookup — instant (zero API calls):** Embed full balance map as JSON in the dashboard page at load time; JS lookups are now instant dict reads with no fetch calls. |
| `0801125` | **Yarn lookup card width:** Constrain outer card to `max-width: 460px` so it doesn't stretch full page width. |
| `21b8fd8` | **Yarn lookup improvements:** Multi-code input (comma-separated), compact input, per-code result rows with status badges. |
| `c7213e3` | **Sidebar logo fix:** Switch from `logo.png` (8000×4500 full letterhead canvas) to `logo_resized.png` (2626×936 cropped logo mark). |

### 2026-03-21

| Commit | Description |
|--------|-------------|
| `2e1fd92` | Widen sidebar to 240px and fix logo sizing. |
| `66a0ad1` | Remove accidentally committed root files; update `.gitignore` to block PDFs/images/docs at root but allow `static/img/` assets. |
| `b125224` | Project detail: tabs (Overview / Design / Production), file previewer modal, UI cleanup. |
| `ddb8715` | Restructure project detail page: merged pipeline stepper, inline quotes table, compact UI. |
| `804276f` | Assign KS/NNNN order number when design is marked final; backfill existing projects. |
| `7eb178a` | Assign order number when project stage changes to Production. |
| `a59b726` | Auto-assign order number to projects (KS/NNNN format). |
| `a1798a2` | Production sheet: increase design image width to 65%. |
| `8e35e03` | Production sheet: larger logo, full A4 height, image fills remaining space. |
| `64f2942` | Add `pymupdf` to requirements for PDF design preview rendering. |
| `cfc4401` | Add production sheet details form and PDF design preview. |
| `e7a3e8b` | Add production sheet print view for projects. |
| `4457664` | Fix production file category icon rendering — use `\| safe` filter for HTML entities. |
| `21258aa` | Projects: fix production file naming, hide feedback/revision when final, remove stitch category. |
| `441481b` | Quote PDF: remove browser headers/footers, fill full page cream. |
| `e743878` | Fix quote PDF layout from review. |
| `b1c85d9` | Fix quote PDF issues from review. |
| `3011b31` | Redesign quote PDF to match Kaayu letterhead style. |
| `6e234e4` | Quotes: T&C checkbox list, remove image column, Kaayu logo in PDF. |
| `da7a6c5` | Pin Python to 3.12 to avoid `mise` freethreaded build issue on Railway. |
| `86bc3b3` | Redesign quotes — PDF-style layout, per-item GST, client auto-fill. |

### 2026-03-18

| Commit | Description |
|--------|-------------|
| `210c660` | Fix project deletion blocked by quotations FK constraint. |
| `0d30bf7` | Fix storage URLs by stripping whitespace from env vars. |
| `c76f8b3` | Fix file upload 500 error — increase timeout and catch storage exceptions. |

### 2026-03-16

| Commit | Description |
|--------|-------------|
| `7c9077b` | Redesign dashboard yarn lookup — bigger input, no dropdown, mobile-friendly. |
| `691915e` | Fix yarn stock N+1 query — replace 298 queries with 1. |
| `d1dce98` | Add Yarn Tracker feature. |
| `ca39132` | Initial commit — Kaayu Studio Manager. |

---

## Environment Variables (Railway)

Set these in the Railway dashboard:

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Long random string for session signing |
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | Supabase PostgreSQL connection string |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `SUPABASE_BUCKET` | Storage bucket name (default: `uploads`) |
