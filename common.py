"""공용 Streamlit API 도우미와 세션에 안전한 오류 메시지를 제공한다."""

import json
import os
from pathlib import Path

import httpx
import streamlit as st


def _load_env() -> None:
    """기존 값을 덮어쓰지 않고 선택적인 프론트엔드 환경 설정을 불러온다."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# 아래에서 백엔드 주소를 계산하기 전에 프론트엔드 전용 .env를 읽는다.
_load_env()
BACKEND_URL = os.getenv("BACKEND_URL", "").strip() or "http://127.0.0.1:8000"
# 실습용 프로젝트에서는 백엔드와 같은 Google Maps 키 값을 재사용할 수 있다.
# Streamlit Cloud에서는 최상위 시크릿이 환경 변수가 되므로 프론트엔드에서도
# 익숙한 GOOGLE_MAPS_API_KEY 이름을 그대로 사용할 수 있다.
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
HTTP_TIMEOUT = 60


class ApiError(Exception):
    """Streamlit 화면에 안전하게 보여 줄 수 있는 API 문제를 나타낸다."""


class SessionExpired(ApiError):
    """로컬 로그인 세션을 비워야 하는 401 응답을 나타낸다."""


def stream_answer(
    path: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
):
    """인증된 SSE 채팅 응답에서 텍스트 조각을 순서대로 반환한다.

    API는 각 Server-Sent Event를 ``data:`` 줄의 JSON 객체로 보낸다.
    완료된 응답에는 ``done: true``가 들어가며, 스트리밍 시작 뒤에는 HTTP 상태를
    바꿀 수 없으므로 오류를 ``error`` 이벤트로 보낸다.
    """
    try:
        with httpx.stream(
            "POST",
            f"{BACKEND_URL}{path}",
            json=payload or {},
            headers=headers,
            timeout=HTTP_TIMEOUT,
        ) as response:
            # 스트리밍 응답의 JSON 오류 본문을 쓰려면 먼저 응답을 모두 읽어야 한다.
            if response.status_code == 401:
                response.read()
                raise SessionExpired("로그인이 만료되었습니다. 다시 로그인해 주세요.")

            if response.status_code >= 400:
                response.read()
                try:
                    detail = response.json().get("detail", "")
                except ValueError:
                    detail = ""
                raise ApiError(detail or f"요청에 실패했습니다. ({response.status_code})")

            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line.removeprefix("data: "))
                except json.JSONDecodeError as error:
                    raise ApiError("답변 스트림 형식을 읽지 못했습니다.") from error

                if "error" in event:
                    raise ApiError(f"답변을 만들지 못했습니다. {event['error']}")
                if event.get("done"):
                    return
                if text := event.get("text"):
                    yield text

            # 네트워크 연결이 끊기면 오류 이벤트 없이 SSE 응답이 끝날 수 있다.
            # AI 답변이 저장된 것처럼 화면을 다시 실행하지 않는다.
            raise ApiError("AI 답변 스트림이 완료되기 전에 연결이 끊겼습니다. 다시 시도해 주세요.")
    except httpx.ConnectError as error:
        raise ApiError("백엔드 서버에 연결할 수 없습니다. backend 서버가 실행 중인지 확인하세요.") from error
    except httpx.TimeoutException as error:
        raise ApiError("서버 응답이 늦습니다. 잠시 후 다시 시도하세요.") from error


def api(method: str, path: str, **kwargs):
    """API 요청을 보내고 전송·HTTP 실패를 화면용 오류로 바꾼다."""
    try:
        response = httpx.request(method, f"{BACKEND_URL}{path}", timeout=HTTP_TIMEOUT, **kwargs)
    except httpx.ConnectError as error:
        raise ApiError("백엔드 서버에 연결할 수 없습니다. backend 서버가 실행 중인지 확인하세요.") from error
    except httpx.TimeoutException as error:
        raise ApiError("서버 응답이 늦습니다. 잠시 후 다시 시도하세요.") from error

    if response.status_code == 401:
        raise SessionExpired("로그인이 만료되었습니다. 다시 로그인해 주세요.")

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", "")
        except ValueError:
            detail = ""
        raise ApiError(detail or f"요청에 실패했습니다. ({response.status_code})")

    return response.json() if response.content else None


def api_bytes(method: str, path: str, **kwargs) -> bytes:
    """지도 이미지처럼 인증이 필요한 이진 데이터를 돌려주는 API 요청을 보낸다.

    Streamlit 이미지 위젯은 URL을 직접 받을 때 사용자 Bearer 토큰을 붙일 수 없다.
    여기서 이미지 바이트를 가져오면 보호된 백엔드 프록시를 비공개로 유지하면서
    JavaScript 없이도 화면에 결과를 표시할 수 있다.
    """

    try:
        response = httpx.request(method, f"{BACKEND_URL}{path}", timeout=HTTP_TIMEOUT, **kwargs)
    except httpx.ConnectError as error:
        raise ApiError("백엔드 서버에 연결할 수 없습니다. backend 서버가 실행 중인지 확인하세요.") from error
    except httpx.TimeoutException as error:
        raise ApiError("서버 응답이 늦습니다. 잠시 후 다시 시도하세요.") from error

    if response.status_code == 401:
        raise SessionExpired("로그인이 만료되었습니다. 다시 로그인해 주세요.")
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", "")
        except ValueError:
            detail = ""
        raise ApiError(detail or f"요청에 실패했습니다. ({response.status_code})")
    return response.content


def auth_headers() -> dict[str, str]:
    """활성화되고 인증된 Streamlit 세션에만 사용할 API 헤더를 만든다."""

    token = st.session_state.get("access_token")
    if not token:
        # 보호된 API에 실수로 ``Bearer None``을 보내는 대신, 최상위 화면 보호 로직이
        # 불완전하거나 만료된 로컬 상태를 비우도록 한다.
        raise SessionExpired("로그인이 필요합니다. 다시 로그인해 주세요.")
    return {"Authorization": f"Bearer {token}"}
