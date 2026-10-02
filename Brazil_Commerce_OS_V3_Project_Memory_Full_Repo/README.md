# Brazil Commerce OS

Streamlit prototype for a four-stage cross-border commerce workflow:

1. Market Intelligence
2. Business Operations & Localization
3. Creator & Campaign
4. Finance & Performance

This V3 build adds persistent multi-project memory with Supabase Auth, Postgres and private file storage. Read `README_PROJECT_MEMORY.md` before deployment.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

For cloud persistence, run `database/schema.sql` in Supabase and configure Streamlit Secrets using `.streamlit/secrets.toml.example`.
