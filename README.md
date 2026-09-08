# TripMate frontend

## Dashboard administrator access

Dashboard access is controlled by the Supabase `public.profiles.is_admin`
boolean column. Set it to `true` for the administrator profile after running
the backend migration `supabase/20260908_profile_admin.sql`. The frontend does
not use a dashboard token or an admin-related environment variable.

Streamlit UI for TripMate.

## Run

```powershell
uv sync
uv run streamlit run streamlit_app.py
```

`BACKEND_URL` can stay blank in `.env` while running locally; it then uses
`http://127.0.0.1:8000`.

운영 대시보드는 기존 TripMate 화면의 로그인 세션 안에서 사용할 수 있습니다.
로그인 후 사이드바의 `운영 대시보드`를 선택하면 같은 화면에서 대시보드가 열리고,
`여행 화면`을 선택하면 일정 화면으로 돌아갑니다. 별도 대시보드 호스트나 토큰
입력은 필요하지 않습니다.

운영 대시보드는 Supabase `public.profiles.is_admin` 값으로 접근 권한을
판별합니다. 백엔드의 `supabase/20260908_profile_admin.sql`을 1회 실행한 뒤
관리자 프로필의 `is_admin`을 `true`로 설정하면 됩니다. 관리자 토큰이나
관리자 이메일 환경변수는 사용하지 않습니다.

운영 대시보드의 `운영콘솔` 버튼에서 사용자 목록과 사용자별 여행·활동·API 요청
정보를 조회할 수 있습니다. 현재 운영콘솔은 조회 전용입니다.

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
