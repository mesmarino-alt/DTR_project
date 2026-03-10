Project: DTR Automate

Deployment / Supabase notes

This project uses Supabase (Postgres) for production data storage. Do NOT commit local DB files or secrets.

Required environment variables (set in Render or your host):
- DATABASE_URL (preferred) OR set individually:
  - DB_HOST
  - DB_NAME
  - DB_USER
  - DB_PASS
  - DB_PORT
- PORT (optional) — port the app listens on
- RUN_INIT_DB (optional) — set to "1" only when you want to run init_db.py once to create schema and seed data
- ALLOW_DB_TEST (optional) — set to "1" to allow running test_db.py and check_db.py locally/CI
- TESTING_MODE (optional) — when True the app marks records as testing (is_test = TRUE). Configure in helpers.py or pass a value via env var if you add support.

Important deployment guidance
- Add database.db / *.sqlite / .venv / .env to .gitignore (already added).
- Remove any tracked local DB files from git: git rm --cached database.db; git commit -m "Remove local DB"; git push
- Do NOT set RUN_INIT_DB=1 on every deploy — only run once (or run init_db.py manually) to avoid accidental schema resets.
- Use migrations (recommended) for schema changes instead of re-running init_db.

Health & diagnostics
- A /health endpoint is available (routes/health.py) which checks DB connectivity and essential tables.
- Diagnostic scripts (test_db.py, check_db.py) exist for local use. They are guarded by ALLOW_DB_TEST and should not be run on public environments.

Security
- Never commit secrets (.env) or credentials to repo. Use Render environment variables or secret manager.
- Consider protecting /health in production (IP restriction or simple auth) to avoid exposing DB info.

If you need help:
- I can purge database.db from the git history (BFG/git-filter-repo) if it was ever committed and needs removal.
- I can add environment-variable support for TESTING_MODE and other run-time flags if desired.
