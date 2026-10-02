# GitHub Upload Checklist — V3 Project Memory

## Replace these existing files

- `app.py`
- `config.py`
- `requirements.txt`
- `.env.example`
- `llm.py` (keeps Market V2 long-report token settings)
- `tools/market.py` (Market Research V2)
- `tools/marketing.py` (Marketing V2.1 schema mapping / dataset-fit fix)
- `tools/report_generator.py`
- `skills/MARKET_SKILL.md`
- `skills/MARKETING_SKILL.md`

## Keep / upload these current files

- `agent.py`
- `tools/operations.py`
- `tools/finance.py`
- `skills/OPERATIONS_SKILL.md`
- `skills/FINANCE_SKILL.md`
- `data/creator_sample.csv`
- `data/finance_sample.csv`

## Add these new folders/files

- `storage/__init__.py`
- `storage/schemas.py`
- `storage/supabase_client.py`
- `storage/auth.py`
- `storage/project_store.py`
- `storage/file_store.py`
- `database/schema.sql`
- `.streamlit/secrets.toml.example`
- `README_PROJECT_MEMORY.md`
- `UPLOAD_CHECKLIST.md`

## Do not upload real secrets

Do not create or commit `.streamlit/secrets.toml` with real keys. Put the real values in Streamlit Cloud > Settings > Secrets.
