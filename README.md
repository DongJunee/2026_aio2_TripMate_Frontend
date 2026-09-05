# TripMate frontend

Streamlit UI for TripMate.

## Run

```powershell
uv sync
uv run streamlit run streamlit_app.py
```

`BACKEND_URL` can stay blank in `.env` while running locally; it then uses
`http://127.0.0.1:8000`.

To render the interactive map locally, add the same Google Maps key value used
by the backend to this gitignored `frontend/.env` file:

```dotenv
GOOGLE_MAPS_API_KEY=""
```

For Streamlit Cloud, paste the same root-level `GOOGLE_MAPS_API_KEY` value into
the app's **Advanced settings → Secrets**. For classroom prototyping, use a
Google Maps Demo Key. It is safe for the browser to receive only a Demo Key;
never put Supabase, Gemini, or service-role secrets in the frontend `.env` or
Cloud Secrets. For a standard Google Maps key, a separate browser key restricted
to the deployed website is safer.
