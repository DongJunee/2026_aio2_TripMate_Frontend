# TripMate frontend

Streamlit UI for TripMate.

## Run

```powershell
uv sync
uv run streamlit run streamlit_app.py
```

`BACKEND_URL` can stay blank in `.env` while running locally; it then uses
`http://127.0.0.1:8000`.

관리자 대시보드는 기존 여행 화면과 별도로 실행합니다.

```powershell
uv run streamlit run admin_dashboard.py
```

백엔드의 `DASHBOARD_ADMIN_TOKEN`을 프론트엔드 실행 환경변수로 설정하거나,
대시보드 왼쪽 메뉴에서 관리자 토큰을 입력하면 됩니다. 이 토큰은 프론트엔드
코드에 저장하지 않습니다.

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
