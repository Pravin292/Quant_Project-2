# ADR 0001: Host frontend and Python API on one Vercel project
**Decision:** Next.js frontend and FastAPI function in one repo and one Vercel project.
**Why:** free, always-on, one shareable link, no "wake up" screen.
**Risk and fallback:** Vercel Python bundle size and time limits. Milestone M9 measures them; if exceeded, host only the API on Render or Railway.
