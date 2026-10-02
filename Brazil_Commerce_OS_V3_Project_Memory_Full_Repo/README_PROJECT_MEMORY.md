# Brazil Commerce OS — Project Memory V3

This package adds persistent multi-project memory to the existing Streamlit agent without changing the core Market / Operations / Marketing / Finance tool contracts.

## What users get

- Email/password sign-in (Supabase Auth)
- Multiple independent projects
- Project switcher in the sidebar
- Persistent project metadata: product, market, category, selected platform, current stage
- Saved Market / Operations / Marketing / Finance runs with version history
- Saved uploaded Creator and Finance files
- Saved Market Word/PDF deliverables
- Project progress dashboard
- Activity history
- Private per-user storage protected by Row Level Security (RLS)
- Session-only fallback when Supabase is not configured

## Files to replace

- `app.py`
- `config.py`
- `requirements.txt`
- `.env.example`

## Files to add

- `storage/__init__.py`
- `storage/schemas.py`
- `storage/supabase_client.py`
- `storage/auth.py`
- `storage/project_store.py`
- `storage/file_store.py`
- `database/schema.sql`
- `.streamlit/secrets.toml.example`
- `README_PROJECT_MEMORY.md`

## One-time Supabase setup

1. Create a Supabase project.
2. Open **SQL Editor** and run the complete contents of `database/schema.sql` once.
3. In **Authentication > Providers > Email**, keep Email enabled. For a classroom/demo MVP, disabling Confirm email makes first login faster. For a public production app, email confirmation is recommended.
4. In **Project Settings > API**, copy your Project URL and anon/publishable key.
5. In Streamlit Cloud > App > Settings > Secrets, add `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and the existing LLM / Serper keys. Use `.streamlit/secrets.toml.example` as the template.
6. Commit the new files to GitHub. Streamlit will rebuild because `requirements.txt` changes.

## Security

- Do not commit real API keys.
- The app uses the Supabase anon key together with authenticated user JWTs and RLS; do not use a service-role key in this Streamlit app.
- The Storage bucket is private. Each file path starts with the authenticated user's UUID, and Storage policies restrict access to that folder.

## Persistence behavior

With Supabase configured and `AUTH_REQUIRED=true`, projects survive browser restarts and app redeployments. If Supabase is not configured, the app keeps working but project data is only stored in `st.session_state` and is not durable.

## Current scope

This V3 package adds the project-memory foundation and connects the current four modules to it. It does **not** yet replace the current Section 2 content with the planned platform-specific Operations & Localization consultant. That should be the next focused upgrade after persistence is stable.
