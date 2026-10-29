# Indian Cinema Pulse — Supabase Edition 🎬

News/headline discovery app for Indian cinema, backed by Supabase for persistent storage.

## Setup
1. Run `schema.sql` in the Supabase SQL Editor.
2. Upload `app.py`, `requirements.txt`, `schema.sql`, and `README.md` to a GitHub repo.
3. In Streamlit Community Cloud, deploy `app.py`.
4. In app settings → Secrets, add:
```toml
SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SUPABASE_KEY = "YOUR-PUBLISHABLE-OR-ANON-KEY"
```
5. Never use or expose the Supabase `service_role` key in a public app.

## How data refresh works
Click **Fetch latest headlines** to query multiple public Google News RSS searches. New/updated article metadata is upserted into Supabase and remains available across app restarts. This is near-real-time on refresh, not a guaranteed always-on feed. Automated scheduled refresh can be added with a separate scheduler/worker within free-tier limits.

## Important security note
The included SQL uses public read/write policies to make a personal demo simple. Because this is a public app, anyone could add or delete shared bookmarks. Do not use this policy for private multi-user data. Before inviting users, enable Supabase Auth and enforce row-level security with `user_id` ownership. Use only synthetic/public headline data.
