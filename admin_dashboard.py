from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import streamlit as st


def _load_env() -> None:
    """로컬 실행 시 프론트엔드 .env의 설정을 읽는다."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()
BACKEND_URL = os.getenv("BACKEND_URL", "").strip() or "http://127.0.0.1:8000"
KST = ZoneInfo("Asia/Seoul")


def _period_params(start_date: date, end_date: date) -> dict[str, str]:
    start_at = datetime.combine(start_date, time.min, tzinfo=KST)
    end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=KST)
    return {"start_at": start_at.isoformat(), "end_at": end_at.isoformat()}


def _get_json(path: str, token: str, params: dict[str, str]) -> dict | list:
    try:
        response = httpx.get(
            f"{BACKEND_URL}{path}",
            params=params,
            headers={"X-Admin-Token": token},
            timeout=30,
        )
    except httpx.ConnectError as error:
        raise RuntimeError("백엔드에 연결할 수 없습니다. 백엔드 실행 상태를 확인하세요.") from error
    except httpx.TimeoutException as error:
        raise RuntimeError("대시보드 데이터 조회 시간이 초과되었습니다.") from error

    if response.status_code == 401:
        raise RuntimeError("관리자 토큰이 올바르지 않습니다.")
    if response.status_code >= 400:
        raise RuntimeError("대시보드 데이터를 조회하지 못했습니다.")
    return response.json()


def _metric_value(value: int | float | None, suffix: str = "") -> str:
    return f"{value or 0}{suffix}"


def _render_summary(summary: dict) -> None:
    kpis = summary.get("kpis", {})
    cards = st.columns(6)
    card_values = [
        ("사용자 가입 수", kpis.get("user_signup_count", 0), ""),
        ("전체 요청 수", kpis.get("total_requests", 0), ""),
        ("성공 수", kpis.get("success_count", 0), ""),
        ("실패 수", kpis.get("failure_count", 0), ""),
        ("에러율", kpis.get("error_rate_percent", 0), "%"),
        ("평균 응답시간", kpis.get("average_latency_ms", 0), " ms"),
    ]
    for column, (label, value, suffix) in zip(cards, card_values):
        with column:
            st.metric(label, _metric_value(value, suffix))

    st.subheader("시간별 요청량")
    hourly = summary.get("hourly_requests", [])
    if hourly:
        st.line_chart(
            {
                "요청 수": [item.get("request_count", 0) for item in hourly],
                "성공 수": [item.get("success_count", 0) for item in hourly],
                "실패 수": [item.get("failure_count", 0) for item in hourly],
            }
        )
        st.dataframe(
            [
                {
                    "시간": item.get("hour"),
                    "요청 수": item.get("request_count", 0),
                    "성공 수": item.get("success_count", 0),
                    "실패 수": item.get("failure_count", 0),
                }
                for item in hourly
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("선택한 기간에 요청 로그가 없습니다.")

    left, right = st.columns(2)
    with left:
        st.subheader("엔드포인트별 이용량")
        endpoints = summary.get("endpoint_usage", [])
        st.dataframe(
            [
                {
                    "엔드포인트": item.get("endpoint"),
                    "요청 수": item.get("request_count", 0),
                    "고유 사용자": item.get("unique_user_count", 0),
                    "평균 응답시간(ms)": item.get("average_latency_ms", 0),
                    "에러율(%)": item.get("error_rate_percent", 0),
                }
                for item in endpoints
            ],
            use_container_width=True,
            hide_index=True,
        )
    with right:
        st.subheader("LLM 요청 요약")
        llm_summary = summary.get("llm_summary", [])
        st.dataframe(
            [
                {
                    "모델": item.get("model"),
                    "요청 수": item.get("request_count", 0),
                    "실패 수": item.get("failure_count", 0),
                    "에러율(%)": item.get("error_rate_percent", 0),
                    "평균 응답시간(ms)": item.get("average_latency_ms", 0),
                }
                for item in llm_summary
            ],
            use_container_width=True,
            hide_index=True,
        )


def main() -> None:
    st.set_page_config(page_title="TripMate 관리자 대시보드", page_icon="📊", layout="wide")
    st.title("TripMate 관리자 대시보드")

    with st.sidebar:
        st.header("조회 조건")
        start_date = st.date_input("시작일", value=date.today())
        end_date = st.date_input("종료일", value=date.today())
        token = os.getenv("DASHBOARD_ADMIN_TOKEN", "").strip()
        if not token:
            token = st.text_input("관리자 토큰(운영 모드에서만 필요)", type="password")
        st.button("새로고침")
        st.caption("테스트 모드에서는 토큰을 비워둬도 됩니다.")

    if start_date > end_date:
        st.error("종료일은 시작일보다 빠를 수 없습니다.")
        st.stop()
    params = _period_params(start_date, end_date)
    try:
        summary = _get_json("/admin/dashboard/summary", token, params)
        errors = _get_json("/admin/dashboard/errors", token, {**params, "limit": "100"})
    except RuntimeError as error:
        st.error(str(error))
        st.stop()

    period = summary.get("period", {})
    st.caption(f"조회 기간: {period.get('start_at', '')} ~ {period.get('end_at', '')}")
    _render_summary(summary)

    st.subheader("최근 오류 로그")
    error_items = errors.get("items", []) if isinstance(errors, dict) else []
    if error_items:
        st.dataframe(
            [
                {
                    "발생 시각": item.get("occurred_at"),
                    "요청 ID": item.get("request_id"),
                    "메서드": item.get("method"),
                    "엔드포인트": item.get("endpoint"),
                    "상태 코드": item.get("status_code"),
                    "응답시간(ms)": item.get("latency_ms"),
                    "오류 유형": item.get("error_type"),
                    "모델": item.get("model"),
                }
                for item in error_items
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("선택한 기간에 오류 로그가 없습니다.")


if __name__ == "__main__":
    main()
