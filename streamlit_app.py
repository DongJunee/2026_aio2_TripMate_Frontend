import json
import os
from datetime import date, datetime, time, timedelta, timezone
from html import escape
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components

from common import (
    GOOGLE_MAPS_API_KEY,
    ApiError,
    SessionExpired,
    _load_env,
    api,
    auth_headers,
    stream_answer,
)

# 자동로그인기능이라 추후에 빼야함
import time as time_module
##########################

# Streamlit 프론트엔드 진입점이다. 백엔드는 별도의 app/main.py를 사용한다.

# 화면 요소를 그리기 전에 브라우저 탭과 넓은 레이아웃을 설정한다.
st.set_page_config(
    page_title="TripMate",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 앱 시작 시 공용 페이지·내비게이션·카드·반응형 스타일을 적용한다.
st.markdown(
    """
    <style>
        
        /* .block-container { max-width: 1320px; padding-top: 2rem; padding-bottom: 3rem; } */
        .brand { color: #315cce; font-size: 2rem; font-weight: 800; letter-spacing: -0.08rem; }
        .sidebar-brand { display: flex; align-items: center; gap: .65rem; font-size: 1.3rem; font-weight: 800; letter-spacing: -.04rem; }
        .sidebar-brand-mark { display: inline-flex; align-items: center; justify-content: center; width: 2rem; height: 2rem; border-radius: .65rem; background: #3169e8; color: #fff; font-size: 1rem; }
        .sidebar-section-label { margin: .85rem 0 .35rem; font-size: .78rem; font-weight: 700; opacity: .62; }
        .sidebar-avatar { display: inline-flex; align-items: center; justify-content: center; width: 2rem; height: 2rem; border-radius: 50%; background: #e5edff; color: #3169e8; font-weight: 800; }
        .sidebar-profile-name { font-size: .88rem; font-weight: 800; line-height: 1.2; }
        .sidebar-profile-email { margin-top: .12rem; font-size: .72rem; opacity: .62; }
        /* 일반 여행 행에는 카드 색을 두지 않는다. 선택된 행만 파란색으로
           표시해 현재 선택한 여행을 쉽게 찾을 수 있게 한다. */
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_select_"] button[kind="secondary"] { background: transparent !important; border-color: transparent !important; color: inherit !important; }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_select_"] button {
            justify-content: flex-start !important;
            /* 겹쳐진 핀 뒤에서 제목이 시작하는 위치는 48px 값을 바꿔 조절한다. */
            padding-left: 48px !important;
            padding-right: 8px !important;
            text-align: left !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_select_"] button[kind="secondary"] p { width: 100%; color: inherit !important; text-align: left !important; }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_select_"] button > div,
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_select_"] button > div > span {
            justify-content: flex-start !important;
            width: 100% !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_select_"] button[kind="secondary"]:hover { background: rgba(49, 51, 63, .06) !important; border-color: transparent !important; }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_select_"] button[kind="primary"] { background: #e5f2ff !important; border-color: #d2e8ff !important; border-left: 4px solid #5479db; color: #2872d8 !important; }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_select_"] button[kind="primary"] p { width: 100%; color: #2872d8 !important; font-weight: 700; text-align: left !important; }
        /* 테두리 북마크는 고정되지 않음을, 파란 채움 북마크는 현재 고정 상태를
           뜻한다. Streamlit의 회색 스위치를 대신한다. */
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_pin_"] button {
            min-width: 2rem !important;
            min-height: 2rem !important;
            padding: 0 !important;
            border-radius: .55rem !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_pin_"] button[kind="secondary"] {
            background: transparent !important;
            border-color: transparent !important;
            color: #9aa7ba !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_pin_"] button[kind="secondary"]:hover {
            background: #eef3fb !important;
            color: #5479db !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_pin_"] button[kind="primary"] {
            background: #3169e8 !important;
            border-color: #3169e8 !important;
            color: #ffffff !important;
        }
        /* 각 행의 핀은 왼쪽에 별도 열을 차지하지 않고 전체 너비 여행 버튼 위에
           겹쳐 표시된다. */
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_row_"] {
            position: relative;
            min-height: 2.5rem;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_row_"] [class*="st-key-sidebar_trip_pin_"] {
            position: absolute !important;
            top: 50%;
            left: 8px;
            z-index: 2;
            transform: translateY(-50%);
        }
        /* Streamlit 바깥 사이드바가 두 번째 스크롤 영역이 되지 않게 한다.
           고정 높이를 가진 ``sidebar-trip-list``만 스크롤할 수 있다. */
        /* 기본 Streamlit 사이드바 너비는 약 336px이다. 235px은 여행 이름을
           읽기 좋게 유지하면서 그 너비의 약 70%에 해당한다. */
        [data-testid="stSidebar"] {
            width: 235px !important;
            min-width: 235px !important;
            max-width: 235px !important;
            flex: 0 0 235px !important;
            overflow: hidden;
        }
        [data-testid="stSidebar"] > div:first-child {
            width: 235px !important;
            min-width: 235px !important;
            max-width: 235px !important;
        }
        /* 상단 도구 모음과 사이드바 접기·펼치기 제어를 숨겨 Streamlit 페이지가
           앱처럼 보이게 한다. */
        header[data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stSidebarHeader"],
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stSidebarCollapsedControl"],
        #MainMenu,
        footer { display: none !important; }
        /* Streamlit 헤더를 숨기면 상단에 큰 빈 띠가 남는다. 대신 앱처럼 보이는
           작은 안쪽 여백만 유지한다. */
        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            display: flex;
            flex-direction: column;
            height: 100dvh;
            /* TripMate 영역을 세로로 옮기려면 이 값만 바꾼다. */
            padding-top: 20px !important;
            padding-bottom: .7rem !important;
            box-sizing: border-box;
            overflow: hidden;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            display: flex;
            flex: 1 1 auto;
            flex-direction: column;
            min-height: 0;
            box-sizing: border-box;
            padding-bottom: .7rem !important;
            overflow: hidden;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div:first-child {
            display: flex;
            flex: 1 1 auto;
            flex-direction: column;
            min-height: 0;
        }
        /* Streamlit은 key가 지정된 컨테이너 주위에 레이아웃 래퍼를 만든다.
           이 래퍼도 늘어나야 프로필의 ``margin-top: auto``가 아래로 밀려날
           빈 공간을 확보할 수 있다. */
        [data-testid="stSidebar"] [data-testid="stLayoutWrapper"]:has(> .st-key-sidebar-layout) {
            display: flex;
            flex: 1 1 auto;
            flex-direction: column;
            min-height: 0;
        }
        [data-testid="stSidebar"] [data-testid="stLayoutWrapper"]:has(> .st-key-sidebar-profile) {
            margin-top: auto !important;
        }
        /* Streamlit의 원래 390px 높이를 유지하지 않고, 하나의 스크롤 가능한
           여행 목록 영역이 고정 프로필 위의 모든 공간을 쓰게 한다. */
        [data-testid="stSidebar"] [data-testid="stLayoutWrapper"]:has(> .st-key-sidebar-trip-list) {
            flex: 1 1 0 !important;
            height: auto !important;
            min-height: 0;
        }
        [data-testid="stSidebar"] .st-key-sidebar-layout {
            display: flex;
            flex: 1 1 auto;
            flex-direction: column;
            min-height: 0;
        }
        [data-testid="stSidebar"] .st-key-sidebar-profile { margin-top: auto !important; }
        [data-testid="stSidebar"] .st-key-sidebar-trip-list {
            flex: 1 1 auto !important;
            height: 100% !important;
            min-height: 0;
            /* 여행 목록은 고정 픽셀이 아니라 부모 사이드바의 실제 폭을 그대로
               사용한다. 창 너비가 바뀌어도 목록과 세로 스크롤바가 함께 맞는다. */
            width: 100% !important;
            min-width: 0 !important;
            max-width: 100% !important;
            margin-right: 0 !important;
            margin-left: 0 !important;
            box-sizing: border-box;
            padding-right: 0px !important;
            padding-left: 0px !important;
            gap: .35rem;
            overflow-x: hidden !important;
            overflow-y: auto !important;
        }
        .eyebrow { color: #63718d; font-size: .76rem; font-weight: 800; letter-spacing: .08rem; }
        .hero { padding: 1.7rem; border-radius: 22px; background: linear-gradient(125deg, #123a80, #486fe0); color: white; margin-bottom: 1.2rem; }
        .hero h1 { color: white; margin: .25rem 0; font-size: 2rem; letter-spacing: -.07rem; }
        .hero p { color: #dbe5ff; margin: 0; }
        .stat { padding: 1rem 1.1rem; min-height: 105px; border: 1px solid #e3e8f2; border-radius: 16px; background: white; }
        .stat-label { color: #70809d; font-size: .78rem; font-weight: 700; }
        .stat-value { color: #1a2c51; font-size: 1.2rem; font-weight: 800; margin-top: .4rem; }
        .day-title { font-size: 1.18rem; font-weight: 800; color: #1a2d54; }
        .item-card { border: 1px solid #e2e8f4; border-left: 4px solid #5479db; border-radius: 12px; background: white; padding: .85rem 1rem; margin: .45rem 0; }
        .item-meta { color: #70809b; font-size: .83rem; margin-top: .22rem; }
        /* 장소가 연결된 일정에는 카드 안쪽 오른쪽 중앙에 작은 정보 버튼만 띄운다.
           카드에 오른쪽 여백을 남겨 제목이 버튼 아래로 겹치지 않게 한다. */
        [class*="st-key-itinerary_item_row_"] {
          position: relative !important;
        }
        [class*="st-key-itinerary_item_row_"] .item-card {
          padding-right: 4.3rem !important;
        }
        [class*="st-key-itinerary_item_row_"] [class*="st-key-itinerary_place_info_"] {
          position: absolute !important;
          top: 50% !important;
          right: .85rem !important;
          left: auto !important;
          width: fit-content !important;
          min-width: 0 !important;
          max-width: fit-content !important;
          z-index: 3 !important;
          margin: 0 !important;
          transform: translateY(-50%) !important;
        }
        [class*="st-key-itinerary_place_info_"] [data-testid="stPopover"] > button,
        [class*="st-key-itinerary_place_info_"] button {
          min-width: 2.9rem !important;
          width: auto !important;
          height: 2rem !important;
          padding: 0 .5rem !important;
          border: 1px solid #d8e3fa !important;
          border-radius: .55rem !important;
          background: #f3f7ff !important;
          color: #3169e8 !important;
          box-shadow: none !important;
          font-size: .75rem !important;
          font-weight: 700 !important;
        }
        [class*="st-key-itinerary_place_info_"] button:hover {
          border-color: #9eb6ee !important;
          background: #e7f0ff !important;
        }
        /* 삭제 버튼도 일정 카드의 가운데 높이에 맞춘다. */
        [class*="st-key-itinerary_delete_"] {
          margin-top: 1.25rem !important;
          text-align: center !important;
        }
        .empty-card { padding: 2.2rem; text-align: center; border: 1px dashed #c8d4eb; border-radius: 18px; background: white; }
        .login-wrap { max-width: 470px; margin: 8vh auto; }
        .login-card { padding: 2.7rem 2.25rem; border-radius: 24px; background: white; border: 1px solid #e3e9f6; box-shadow: 0 18px 45px rgba(37, 64, 120, .08); }
        @media (max-width: 800px) {
          .login-wrap { margin: 4vh auto; }
          .login-card { padding: 2rem 1.4rem; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

def initialize_session() -> None:
    """인증과 여행 화면에 필요한 세션 상태 기본값을 설정한다."""
    defaults = {
        "access_token": None,
        "user_email": None,
        "user_name": None,
        "selected_trip_id": None,
        "show_create_trip": False,
        "notice": None,
        "auth_mode": "login",
        # 로그인·여행 전환 뒤 이전 화면의 맨 아래 스크롤 위치를 이어받지 않도록
        # 다음 렌더링에서 브라우저의 메인 영역을 맨 위로 보낼지 기록한다.
        "scroll_main_to_top": False,
        # 검색 결과와 지도 표시 여부는 로컬 UI 상태일 뿐이다. 실제 선택 장소는
        # 백엔드가 일반 일정 데이터에 저장한다.
        "place_search_results": {},
        "visible_day_maps": {},
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def request_main_scroll_to_top() -> None:
    """다음 Streamlit 재실행 뒤 메인 화면을 맨 위로 보낸다."""

    st.session_state.scroll_main_to_top = True


def scroll_main_to_top_if_requested() -> None:
    """이전 화면 스크롤을 유지하는 브라우저·Streamlit 컨테이너를 모두 맨 위로 보낸다."""

    if not st.session_state.pop("scroll_main_to_top", False):
        return

    # Streamlit의 재실행은 브라우저 스크롤을 보존할 수 있다. srcdoc 컴포넌트에서
    # 부모 문서의 일반 스크롤과 Streamlit 메인 컨테이너를 함께 초기화한다. DOM
    # 구조가 버전별로 조금 달라도 후보 중 존재하는 대상만 안전하게 처리한다.
    components.html(
        """
        <script>
          (() => {
            try {
              const parentWindow = window.parent;
              const documentRoot = parentWindow.document;
              const scrollToTop = () => {
                // 화면 마지막의 채팅 입력칸이 포커스를 가져가며 아래로 이동시키지
                // 않도록, 로그인·여행 전환 때만 현재 포커스를 해제한다.
                documentRoot.activeElement?.blur();
                parentWindow.scrollTo({ top: 0, left: 0, behavior: "auto" });
                const targets = [
                  documentRoot.scrollingElement,
                  documentRoot.documentElement,
                  documentRoot.body,
                  documentRoot.querySelector('[data-testid="stMain"]'),
                  documentRoot.querySelector('[data-testid="stAppViewContainer"]'),
                ];
                targets.forEach((target) => {
                  if (!target) return;
                  target.scrollTop = 0;
                  if (typeof target.scrollTo === "function") {
                    target.scrollTo({ top: 0, left: 0, behavior: "auto" });
                  }
                });
              };
              scrollToTop();
              parentWindow.requestAnimationFrame(scrollToTop);
              parentWindow.requestAnimationFrame(() => parentWindow.requestAnimationFrame(scrollToTop));
              parentWindow.setTimeout(scrollToTop, 200);
              parentWindow.setTimeout(scrollToTop, 300);
            } catch (_) {
              // 스크롤 초기화 실패가 로그인·여행 화면을 막으면 안 된다.
            }
          })();
        </script>
        """,
        height=0,
        scrolling=False,
    )


def debug_auto_login() -> None:
    """디버그 모드가 켜져 있으면 로컬 Streamlit 세션당 한 번 로그인한다."""

    # ``common``은 import될 때 먼저 .env를 읽는다. 새로 추가한 로컬 DEBUG_* 값이
    # 다음 Streamlit 재실행에서 적용되도록 여기서 한 번 더 읽는다.
    _load_env()

    if (
        st.session_state.access_token
        or st.session_state.get("debug_auto_login_attempted")
        or os.getenv("DEBUG_AUTO_LOGIN", "").lower() != "true"
    ):
        return

    # 로컬 로그인 정보가 틀렸을 때 모든 Streamlit 재실행마다 다시 시도하지 않는다.
    st.session_state.debug_auto_login_attempted = True
    email = os.getenv("DEBUG_EMAIL", "").strip()
    password = os.getenv("DEBUG_PASSWORD", "")
    if not email or not password:
        st.session_state.notice = "디버그 자동 로그인 정보를 .env에서 찾지 못했습니다."
        return

    time_module.sleep(1)  # 개발 중 로그인 화면을 잠깐 확인하고 싶을 때만 유지한다.
    try:
        result = api("POST", "/auth/login", json={"email": email, "password": password})
    except ApiError as error:
        st.session_state.notice = f"디버그 자동 로그인 실패: {error}"
        return

    st.session_state.access_token = result["access_token"]
    st.session_state.user_email = result["email"]
    st.session_state.user_name = None
    request_main_scroll_to_top()


def sign_out(notice: str | None = None) -> None:
    """현재 계정 상태를 비우고 필요하면 안내 문구를 남긴 뒤 다시 실행한다."""
    st.session_state.access_token = None
    st.session_state.user_email = None
    st.session_state.user_name = None
    st.session_state.selected_trip_id = None
    st.session_state.show_create_trip = False
    st.session_state.place_search_results = {}
    st.session_state.visible_day_maps = {}
    st.session_state.notice = notice
    st.rerun()


def travel_timezone(timezone_name: object) -> object:
    """Windows에 IANA tzdata 패키지가 없어도 여행 시간대를 반환한다.

    일반적인 프로젝트 동기화는 ``tzdata``를 설치하므로 완전한 IANA 시간대 규칙을
    사용한다. 대체 값은 흔한 서울·도쿄 실습 흐름을 바로 쓸 수 있게 하는 최후의
    고정 오프셋 수단일 뿐이다.
    """

    name = str(timezone_name or "Asia/Seoul").strip() or "Asia/Seoul"
    try:
        return ZoneInfo(name)
    except Exception:
        offset_hours = {
            "Asia/Seoul": 9,
            "Asia/Tokyo": 9,
            "Europe/Paris": 1,
            "America/New_York": -5,
        }.get(name, 9)
        return timezone(timedelta(hours=offset_hours), name=name)

def formatted_dates(trip: dict) -> str:
    """날짜가 선택 사항인 여행의 읽기 쉬운 기간 라벨을 반환한다."""
    start, end = trip.get("start_date"), trip.get("end_date")
    if not start or not end:
        return "여행 기간 미정"
    return f"{start} ~ {end}"

def compact_trip_dates(trip: dict) -> str:
    """사이드바에서 여행 제목 옆에 들어갈 짧은 날짜 범위를 반환한다."""

    start, end = trip.get("start_date"), trip.get("end_date")
    if not start or not end:
        return "기간 미정"
    try:
        start_date = date.fromisoformat(str(start)[:10])
        end_date = date.fromisoformat(str(end)[:10])
    except ValueError:
        return "기간 미정"

    if start_date.year != end_date.year:
        return f"{start_date:%y.%m.%d}–{end_date:%y.%m.%d}"
    if start_date == end_date:
        return f"{start_date.month}/{start_date.day}"
    return f"{start_date.month}/{start_date.day}–{end_date.month}/{end_date.day}"


def trip_activity_sort_key(trip: dict) -> tuple[str, str]:
    """생성 시각을 대체값으로 쓰는 안정적인 최신 활동순 정렬 키를 반환한다."""

    return (
        str(trip.get("updated_at") or trip.get("created_at") or ""),
        str(trip.get("id") or ""),
    )


def sidebar_profile() -> tuple[str, str]:
    """간결한 사이드바 계정 카드에 쓸 저장된 프로필 이름과 이메일을 반환한다."""

    email = st.session_state.user_email or ""
    cached_name = st.session_state.user_name
    if cached_name:
        return cached_name, email

    try:
        result = api("GET", "/me", headers=auth_headers())
    except SessionExpired:
        # 애플리케이션 최상위 처리기가 만료된 로그인 상태를 비워야 한다.
        raise
    except ApiError:
        # 아직 프로필 행이 생성되지 않았어도 여행 목록은 계속 사용할 수 있다.
        result = {}

    profile = result.get("profile") or {}
    display_name = profile.get("username") or email.split("@", 1)[0] or "여행자"
    st.session_state.user_name = display_name
    return display_name, email

def render_login() -> None:
    """비로그인 카드를 그리고 현재 인증 화면을 선택해 표시한다."""
    if st.session_state.notice:
        st.warning(st.session_state.notice)

    _, card_column, _ = st.columns([1, 1.25, 1])
    with card_column:
        st.markdown('<div class="brand">TripMate</div>', unsafe_allow_html=True)
        if st.session_state.auth_mode == "password_reset":
            render_password_reset()
        else:
            render_sign_in_or_up()
        st.markdown("</div>", unsafe_allow_html=True)

def render_sign_in_or_up() -> None:
    """공용 로그인·회원가입 양식을 그리고 입력한 인증 정보를 제출한다."""
    is_signup = st.session_state.auth_mode == "signup"
    st.subheader("회원가입" if is_signup else "여행을 시작해 볼까요?")
    st.caption(
        "이름, 여행, 일정은 내 계정에 안전하게 저장됩니다."
        if is_signup
        else "로그인하면 나의 여행과 일정이 저장됩니다."
    )

    with st.form("auth_form"):
        username = ""
        if is_signup:
            username = st.text_input("사용자 이름", placeholder="예: 홍길동")
        email = st.text_input("이메일", placeholder="you@example.com")
        password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button(
            "가입하고 여행 시작하기" if is_signup else "로그인",
            use_container_width=True,
            type="primary",
        )

    if submitted:
        if not email or not password or (is_signup and not username.strip()):
            st.error(
                "이름, 이메일, 비밀번호를 모두 입력하세요."
                if is_signup
                else "이메일과 비밀번호를 입력하세요."
            )
        else:
            payload = {"email": email, "password": password}
            if is_signup:
                payload["username"] = username.strip()
            try:
                result = api(
                    "POST", "/auth/signup" if is_signup else "/auth/login", json=payload
                )
            except ApiError as error:
                st.error(str(error))
            else:
                if not result.get("access_token"):
                    st.info("회원가입이 완료되었습니다. 이메일 인증 후 로그인해 주세요.")
                else:
                    st.session_state.access_token = result["access_token"]
                    st.session_state.user_email = result["email"]
                    # 새 회원가입은 입력한 이름을 이미 알고 있고, 일반 로그인은
                    # 사이드바를 처음 그릴 때 저장된 프로필 이름을 불러온다.
                    st.session_state.user_name = username.strip() if is_signup else None
                    st.session_state.notice = None
                    request_main_scroll_to_top()
                    st.rerun()

    if st.button(
        "이미 계정이 있어요 · 로그인" if is_signup else "계정이 없어요 · 회원가입",
        use_container_width=True,
    ):
        st.session_state.auth_mode = "login" if is_signup else "signup"
        st.rerun()

    if st.button("비밀번호를 잊으셨나요?", use_container_width=True):
        st.session_state.auth_mode = "password_reset"
        st.rerun()

def render_password_reset() -> None:
    """실습용 본인 확인 비밀번호 재설정 양식과 이동 버튼을 그린다."""
    st.subheader("비밀번호 재설정")
    st.caption("가입할 때 입력한 사용자 이름과 이메일이 일치하면 새 비밀번호를 저장합니다.")
    st.info("실습용 기능입니다. 실제 서비스에서는 이메일 인증으로 본인 확인이 필요합니다.")

    with st.form("password_reset_form"):
        username = st.text_input("사용자 이름", placeholder="가입할 때 입력한 사용자 이름")
        email = st.text_input("이메일 (아이디)", placeholder="you@example.com")
        new_password = st.text_input("새 비밀번호", type="password")
        confirm_password = st.text_input("새 비밀번호 확인", type="password")
        submitted = st.form_submit_button("새 비밀번호 저장", use_container_width=True, type="primary")

    if submitted:
        if not username.strip() or not email or not new_password or not confirm_password:
            st.error("사용자 이름, 이메일, 새 비밀번호를 모두 입력하세요.")
        elif new_password != confirm_password:
            st.error("새 비밀번호가 서로 다릅니다.")
        else:
            try:
                result = api(
                    "POST",
                    "/auth/password-reset/demo",
                    json={
                        "username": username.strip(),
                        "email": email,
                        "new_password": new_password,
                    },
                )
            except ApiError as error:
                st.error(str(error))
            else:
                st.session_state.auth_mode = "login"
                st.session_state.notice = result["message"]
                st.rerun()

    if st.button("로그인으로 돌아가기", use_container_width=True):
        st.session_state.auth_mode = "login"
        st.rerun()

def render_create_trip_form(form_key: str) -> None:
    """여행과 첫 AI 일정 초안을 만드는 양식을 그리고 제출한다."""
    with st.form(form_key, clear_on_submit=True):
        title = st.text_input("여행 이름", placeholder="예: 봄날의 도쿄 여행")
        destination = st.text_input("여행지", placeholder="예: 도쿄, 일본")
        today = date.today()
        selected_dates = st.date_input(
            "여행 기간",
            value=(today, today + timedelta(days=3)),
            format="YYYY-MM-DD",
        )
        timezone = st.selectbox("여행지 시간대", ["Asia/Seoul", "Asia/Tokyo", "Europe/Paris", "America/New_York"])
        submitted = st.form_submit_button("새 여행 만들기", use_container_width=True, type="primary")

    if not submitted:
        return
    if not title.strip() or not destination.strip():
        st.error("여행 이름과 여행지를 입력하세요.")
        return
    if not isinstance(selected_dates, tuple) or len(selected_dates) != 2:
        st.error("시작일과 종료일을 모두 선택하세요.")
        return

    try:
        # 백엔드는 Gemini 초안을 만든 뒤 Google Places의 실제 장소까지 확인한다.
        # 둘 중 하나라도 실패하면 여행이 생성되지 않으므로, 성공 응답을 받은 뒤에만
        # 선택된 여행 ID와 화면 상태를 바꾼다.
        with st.spinner("AI가 DAY별 실제 장소 일정을 만들고 있어요..."):
            created = api(
                "POST",
                "/me/trips",
                json={
                    "title": title.strip(),
                    "destination": destination.strip(),
                    "timezone": timezone,
                    "start_date": selected_dates[0].isoformat(),
                    "end_date": selected_dates[1].isoformat(),
                },
                headers=auth_headers(),
            )
    except ApiError as error:
        st.error(str(error))
        return

    st.session_state.selected_trip_id = created["trip"]["id"]
    st.session_state.show_create_trip = False
    request_main_scroll_to_top()
    count = int(created.get("initial_itinerary_count") or 0)
    st.success(f"새 여행과 Google 장소 기반 AI 일정 {count}개를 만들었어요.")
    st.rerun()

def render_sidebar_trip(trip: dict) -> None:
    """세로 중앙 핀을 겹쳐 놓은 전체 너비 여행 버튼 하나를 그린다."""

    trip_id = trip["id"]
    is_pinned = trip.get("pinned_order") is not None
    active = trip_id == st.session_state.selected_trip_id
    requested_pinned = is_pinned

    with st.container(key=f"sidebar_trip_row_{trip_id}", border=False):
        # 버튼 안에 다른 버튼을 중첩하지 않고 왼쪽의 작은 제어 요소로 핀을 여행
        # 버튼 위에 배치할 수 있도록, 여행 버튼을 먼저 그린다.
        if st.button(
            trip["title"],
            key=f"sidebar_trip_select_{trip_id}",
            use_container_width=True,
            type="primary" if active else "secondary",
        ):
            st.session_state.selected_trip_id = trip_id
            st.session_state.show_create_trip = False
            request_main_scroll_to_top()
            st.rerun()

        pin_label = ":material/bookmark:" if is_pinned else ":material/bookmark_border:"
        if st.button(
            pin_label,
            key=f"sidebar_trip_pin_{trip_id}",
            type="primary" if is_pinned else "secondary",
            # help="고정을 해제합니다." if is_pinned else "여행 목록 상단에 고정합니다.",
        ):
            requested_pinned = not is_pinned

    if requested_pinned == is_pinned:
        return
    try:
        api(
            "PATCH",
            f"/trips/{trip_id}/pin",
            json={"pinned": requested_pinned},
            headers=auth_headers(),
        )
    except SessionExpired:
        # 애플리케이션 최상위 처리기가 만료된 로그인 상태를 비우도록 한다.
        raise
    except ApiError as error:
        st.error(str(error))
        return
    st.rerun()

def render_sidebar(trips: list[dict]) -> None:
    """여행 그룹·여행 총개수·하단 고정 프로필 팝오버를 그린다."""

    display_name, email = sidebar_profile()
    initial = escape(display_name[:1].upper() or "여")
    safe_name = escape(display_name)
    safe_email = escape(email)
    pinned_trips = sorted(
        (trip for trip in trips if trip.get("pinned_order") is not None),
        key=lambda trip: trip["pinned_order"],
    )
    # API도 최신 수정순을 요청하지만, 나중의 API 호출이 정렬되지 않은 목록을
    # 반환하더라도 사이드바가 올바르게 보이도록 여기서 한 번 더 정렬한다.
    previous_trips = sorted(
        (trip for trip in trips if trip.get("pinned_order") is None),
        key=trip_activity_sort_key,
        reverse=True,
    )

    with st.sidebar:
        # 하나의 flex 열을 사용해 두 번째 사이드바 스크롤 영역을 만들지 않고도
        # 프로필이 ``margin-top: auto``로 최하단에 머물 수 있게 한다.
        with st.container(key="sidebar-layout", border=False):
            # 고정된 여행과 이전 여행 모두 사용자가 저장한 여행 수에 포함된다.
            st.markdown(
                '<div class="sidebar-brand"><span class="sidebar-brand-mark">◉</span>TripMate</div>',
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:.85rem'></div>", unsafe_allow_html=True)
            if st.button("＋ 새 여행 만들기", use_container_width=True, type="primary"):
                st.session_state.show_create_trip = True
                st.rerun()

            # st.markdown("<div class='sidebar-section-label'>나의 여행</div>", unsafe_allow_html=True)
            # CSS는 Streamlit의 초기 높이와 관계없이 이 영역만 스크롤되게 하고,
            # 하단 고정 프로필 바로 위까지 늘어나게 한다.
            with st.container(key="sidebar-trip-list", height=390, border=False):
                if pinned_trips:
                    st.caption("고정된 여행")
                    for trip in pinned_trips:
                        render_sidebar_trip(trip)

                if previous_trips:
                    # if pinned_trips:
                    #     st.divider()
                    st.caption("이전 여행")
                    for trip in previous_trips:
                        render_sidebar_trip(trip)

                if not trips:
                    st.caption("아직 만든 여행이 없어요.\n위 버튼으로 첫 여행을 시작하세요.")

            with st.container(key="sidebar-profile", border=False):
                # st.divider()
                # 팝오버를 사용하면 다른 페이지로 이동하지 않고 계정 영역을 열기 전까지
                # 로그아웃 버튼을 사이드바에서 숨길 수 있다.
                with st.popover(
                    # Streamlit은 위젯 라벨을 스스로 이스케이프한다. ``safe_name``은
                    # 아래 팝오버 안에서 렌더링할 HTML 전용이다.
                    f"{display_name} · 내 프로필",
                    key="sidebar_profile_popover",
                    use_container_width=True,
                ):
                    st.caption("내 정보")
                    avatar_column, profile_column, role_column = st.columns(
                        [0.55, 1.8, 1.15], gap="small"
                    )
                    with avatar_column:
                        st.markdown(
                            f'<span class="sidebar-avatar">{initial}</span>',
                            unsafe_allow_html=True,
                        )
                    with profile_column:
                        st.markdown(
                            f'<div class="sidebar-profile-name">{safe_name}</div>'
                            f'<div class="sidebar-profile-email">{safe_email}</div>',
                            unsafe_allow_html=True,
                        )
                    with role_column:
                        st.caption("일반 사용자")

                    st.button(
                        "⚙ 설정 (준비 중)",
                        key="profile_settings_placeholder",
                        use_container_width=True,
                        disabled=True,
                    )
                    if st.button(
                        "로그아웃",
                        key="profile_popover_sign_out",
                        use_container_width=True,
                    ):
                        sign_out()


def item_time_text(item: dict) -> str:
    """간결한 표시에 맞게 일정 항목의 시작·종료 시각을 형식화한다."""
    start, end = item.get("start_at"), item.get("end_at")
    if not start:
        return "시간 미정"
    start_text = str(start).replace("T", " ")[:16]
    end_text = str(end).replace("T", " ")[:16] if end else ""
    return f"{start_text} – {end_text}" if end_text else start_text


def add_itinerary_item(trip: dict, day: dict) -> None:
    """일정 항목 양식을 그리고 제출한 항목을 여행 일차에 추가한다."""
    with st.expander("＋ 이 일차에 일정 직접 추가"):
        with st.form(f"item_form_{day['id']}", clear_on_submit=True):
            title = st.text_input("일정 이름", placeholder="예: 하네다 공항 도착")
            item_type = st.selectbox(
                "일정 종류",
                ["place", "cafe", "restaurant", "hotel", "flight", "train", "transit", "activity", "note"],
                format_func=lambda value: {
                    "place": "장소", "cafe": "카페", "restaurant": "식당", "hotel": "호텔",
                    "flight": "비행기", "train": "기차", "transit": "교통", "activity": "활동", "note": "메모",
                }[value],
            )
            start_time = st.time_input("시작 시각", value=time(9, 0))
            stay_minutes = st.number_input("예상 머무는 시간(분)", min_value=0, max_value=1440, value=60, step=10)
            fixed = st.checkbox("예약·항공편처럼 시간이 고정된 일정입니다")
            notes = st.text_input("메모", placeholder="선택 사항")
            submitted = st.form_submit_button("일정 추가", use_container_width=True, type="primary")

        if not submitted:
            return
        if not title.strip():
            st.error("일정 이름을 입력하세요.")
            return
        try:
            travel_date = date.fromisoformat(day["travel_date"])
            trip_timezone = travel_timezone(trip.get("timezone"))
            starts_at = datetime.combine(travel_date, start_time).replace(tzinfo=trip_timezone)
            ends_at = starts_at + timedelta(minutes=int(stay_minutes))
            api(
                "POST",
                f"/trips/{trip['id']}/itinerary-items",
                json={
                    "trip_day_id": day["id"],
                    "item_type": item_type,
                    "source": "manual_entry",
                    "title": title.strip(),
                    "start_at": starts_at.isoformat(),
                    "end_at": ends_at.isoformat(),
                    "estimated_stay_minutes": int(stay_minutes),
                    "is_fixed": fixed,
                    "notes": notes.strip() or None,
                },
                headers=auth_headers(),
            )
        except (ApiError, ValueError) as error:
            st.error(str(error))
            return
        st.rerun()


def _day_map_state_key(trip: dict, day: dict) -> str:
    """특정 여행 일차에 사용할 세션 상태 키 하나를 반환한다."""

    return f"{trip['id']}:{day['id']}"


def _place_rating_text(place: dict) -> str:
    """선택적인 Google 평점 필드를 장소 카드의 짧은 한 줄로 형식화한다."""

    rating = place.get("google_rating")
    count = place.get("google_rating_count")
    if rating is None:
        return "Google 평점 정보 없음"
    suffix = f" · 리뷰 {int(count):,}개" if isinstance(count, (int, float)) else ""
    return f"★ {float(rating):.1f}{suffix}"


def _safe_google_maps_url(value: object) -> str | None:
    """Google Maps로 연결되는 HTTPS 주소만 화면의 외부 링크로 허용한다."""

    if not isinstance(value, str):
        return None
    url = value.strip()
    if not url:
        return None

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    is_google_maps_host = (
        host in {"google.com", "maps.app.goo.gl"} or host.endswith(".google.com")
    )
    if parsed.scheme != "https" or not is_google_maps_host:
        return None
    return url


def render_cached_google_place_info(item: dict) -> None:
    """일정 카드가 연 팝오버 안에 캐시 Google 장소와 지도를 그린다."""

    place = item.get("place")
    if not isinstance(place, dict):
        return

    place_name = str(place.get("display_name") or item.get("title") or "Google 장소")
    address = str(place.get("formatted_address") or "").strip()
    st.markdown(f"**{escape(place_name)}**")

    try:
        map_data = {
            "markers": [
                {
                    "sequence": 1,
                    "title": place_name,
                    "address": address,
                    "latitude": float(place["latitude"]),
                    "longitude": float(place["longitude"]),
                }
            ]
        }
    except (KeyError, TypeError, ValueError):
        st.caption("이 장소에는 지도 미리보기에 필요한 좌표가 없습니다.")
    else:
        # DAY 전체 지도와 같은 Maps JavaScript API를 재사용한다. 별도 장소 정보
        # 버튼 없이 일정 카드를 누른 경우에만 작고 독립된 지도 iframe을 만든다.
        render_interactive_google_map(
            map_data,
            height=240,
            missing_key_message=(
                "지도 미리보기에는 frontend/.env의 GOOGLE_MAPS_API_KEY가 필요합니다."
            ),
        )

    if address:
        st.caption(address)
    if place.get("google_rating") is not None:
        st.caption(_place_rating_text(place))

    if maps_url := _safe_google_maps_url(place.get("google_maps_uri")):
        st.link_button("Google 지도에서 크게 보기", maps_url, use_container_width=True)
    else:
        st.caption("Google 지도 링크 정보가 없습니다.")


def render_itinerary_item_card(item: dict) -> None:
    """장소 연결 여부와 관계없이 기존 일정 카드 모양을 일정하게 그린다."""

    st.markdown(
        f'''<div class="item-card">
            <b>{escape(str(item.get('title') or '일정'))}</b>
            <div class="item-meta">{escape(str(item.get('item_type') or 'place'))} · {escape(item_time_text(item))}</div>
        </div>''',
        unsafe_allow_html=True,
    )


def _route_duration_text(seconds: object) -> str:
    """Routes API 이동 시간을 간결한 한국어 형태로 표시한다."""

    try:
        minutes = max(0, round(float(seconds) / 60))
    except (TypeError, ValueError):
        return "시간 정보 없음"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}시간 {minutes}분" if hours else f"약 {minutes}분"


def render_interactive_google_map(
    map_data: dict,
    *,
    height: int = 420,
    missing_key_message: str | None = None,
) -> bool:
    """저장된 DAY 마커와 Routes 폴리라인을 인터랙티브 Google 지도에 그린다.

    작은 HTML/JavaScript 블록은 Streamlit 컴포넌트 iframe 안에 격리된다.
    보호된 백엔드에서 공개 좌표와 경로 도형만 받아 오며, 직접 인증된 TripMate API를
    호출하지는 않는다.
    """

    if not GOOGLE_MAPS_API_KEY:
        message = missing_key_message or (
            "인터랙티브 지도를 보려면 frontend/.env 또는 Streamlit Cloud Secrets에 "
            "GOOGLE_MAPS_API_KEY를 입력하세요."
        )
        if missing_key_message:
            st.caption(message)
        else:
            st.info(message)
        return False

    markers: list[dict] = []
    for marker in map_data.get("markers") or []:
        try:
            markers.append(
                {
                    "sequence": int(marker["sequence"]),
                    "title": str(marker.get("title") or "장소"),
                    "address": str(marker.get("address") or ""),
                    "position": {
                        "lat": float(marker["latitude"]),
                        "lng": float(marker["longitude"]),
                    },
                }
            )
        except (KeyError, TypeError, ValueError):
            # 잘못된 행 하나 때문에 지도 컴포넌트 전체가 비어서는 안 된다.
            continue

    if not markers:
        st.info("지도에 표시할 좌표가 있는 장소가 아직 없습니다.")
        return False

    route = map_data.get("route") or {}
    component_data = {
        "markers": markers,
        "encodedPolyline": str(route.get("encoded_polyline") or ""),
    }
    # JSON은 script 요소 안에 들어간다. 저장된 장소 제목이 script를 닫거나 마크업을
    # 주입할 수 없도록 HTML에서 의미 있는 문자를 이스케이프한다.
    component_json = (
        json.dumps(component_data, ensure_ascii=False, allow_nan=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    script_url = (
        "https://maps.googleapis.com/maps/api/js?"
        f"key={quote(GOOGLE_MAPS_API_KEY, safe='')}"
        "&libraries=geometry&language=ko&region=KR&v=weekly"
        "&loading=async&callback=initTripMateMap"
    )

    components.html(
        f"""
        <!doctype html>
        <html lang="ko">
        <head>
          <meta charset="utf-8" />
          <style>
            html, body, #tripmate-map {{ height: 100%; margin: 0; padding: 0; }}
            #tripmate-map {{ border-radius: 12px; overflow: hidden; }}
            #tripmate-map-error {{
              display: none; height: 100%; box-sizing: border-box; padding: 1rem;
              color: #a12b2b; background: #fff1f1; border-radius: 12px;
              font: 14px/1.5 sans-serif;
            }}
          </style>
        </head>
        <body>
          <div id="tripmate-map"></div>
          <div id="tripmate-map-error"></div>
          <script>
            const tripmateData = {component_json};

            function showMapError(message) {{
              document.getElementById("tripmate-map").style.display = "none";
              const errorBox = document.getElementById("tripmate-map-error");
              errorBox.textContent = message;
              errorBox.style.display = "block";
            }}

            window.gm_authFailure = function() {{
              showMapError("Google 지도 키를 확인하거나 Maps JavaScript API 데모 키를 입력하세요.");
            }};

            window.initTripMateMap = function() {{
              if (!window.google || !google.maps || !tripmateData.markers.length) {{
                showMapError("Google 지도를 시작하지 못했습니다.");
                return;
              }}

              const map = new google.maps.Map(document.getElementById("tripmate-map"), {{
                center: tripmateData.markers[0].position,
                zoom: 12,
                mapTypeControl: false,
                streetViewControl: false,
                fullscreenControl: true,
                zoomControl: true,
              }});
              const bounds = new google.maps.LatLngBounds();
              const infoWindow = new google.maps.InfoWindow();

              tripmateData.markers.forEach((item) => {{
                const marker = new google.maps.Marker({{
                  position: item.position,
                  map,
                  title: item.title,
                  label: {{ text: String(item.sequence), color: "#ffffff", fontWeight: "700" }},
                }});
                marker.addListener("click", () => {{
                  const content = document.createElement("div");
                  const title = document.createElement("strong");
                  title.textContent = `${{item.sequence}}. ${{item.title}}`;
                  content.appendChild(title);
                  if (item.address) {{
                    const address = document.createElement("div");
                    address.style.color = "#61708a";
                    address.style.marginTop = "4px";
                    address.textContent = item.address;
                    content.appendChild(address);
                  }}
                  infoWindow.setContent(content);
                  infoWindow.open({{ map, anchor: marker }});
                }});
                bounds.extend(item.position);
              }});

              if (tripmateData.encodedPolyline && google.maps.geometry?.encoding) {{
                try {{
                  const path = google.maps.geometry.encoding.decodePath(tripmateData.encodedPolyline);
                  new google.maps.Polyline({{
                    path,
                    geodesic: true,
                    strokeColor: "#3169e8",
                    strokeOpacity: 0.9,
                    strokeWeight: 5,
                    map,
                  }});
                }} catch (error) {{
                  console.warn("TripMate route polyline could not be drawn.", error);
                }}
              }}

              if (tripmateData.markers.length === 1) {{
                map.setCenter(tripmateData.markers[0].position);
                map.setZoom(15);
              }} else {{
                map.fitBounds(bounds, 48);
              }}
            }};
          </script>
          <script async defer src="{escape(script_url, quote=True)}"
                  onerror="showMapError('Google 지도 스크립트를 불러오지 못했습니다.');"></script>
        </body>
        </html>
        """,
        height=height,
        scrolling=False,
    )
    return True


def render_google_place_planner(trip: dict, day: dict) -> None:
    """Google Places를 검색하고 선택 장소를 저장한 뒤 인터랙티브 지도 동선을 보여 준다.

    Google 검색에서 의도적으로 선택한 장소만 안정적인 장소 ID와 좌표를 함께
    저장한다. 직접 입력했거나 AI가 초안으로 만든 제목을 지도상의 실제 장소로
    잘못 판단하지 않도록 하기 위해서다.
    """

    state_key = _day_map_state_key(trip, day)
    search_state = st.session_state.place_search_results
    map_state = st.session_state.visible_day_maps

    # 모든 DAY에서 지도·검색 영역을 보이게 한다. 지도 자체는 좌표가 있는 실제
    # Google 장소가 저장된 뒤에만 그릴 수 있다.
    with st.expander("Google 장소 검색 · 지도 동선", expanded=True):
        st.caption("검색한 장소를 이 DAY에 넣으면 지도 마커와 실제 Google Routes 동선에 반영됩니다.")
        search_column, action_column = st.columns([4, 1])
        with search_column:
            query = st.text_input(
                "장소 검색",
                placeholder="예: 시부야 카페, 라멘, 도쿄 타워",
                key=f"place_search_query_{state_key}",
                label_visibility="collapsed",
            )
        with action_column:
            search_clicked = st.button("검색", key=f"place_search_button_{state_key}", use_container_width=True)

        if search_clicked:
            if not query.strip():
                st.warning("찾고 싶은 장소나 종류를 입력하세요.")
            else:
                try:
                    with st.spinner("Google 장소를 찾고 있어요..."):
                        search_state[state_key] = api(
                            "GET",
                            f"/trips/{trip['id']}/days/{day['id']}/places/search",
                            params={"query": query.strip()},
                            headers=auth_headers(),
                        )
                except ApiError as error:
                    st.error(str(error))
                else:
                    st.rerun()

        search_result = search_state.get(state_key) or {}
        places = search_result.get("places") or []
        if places:
            st.caption(f"‘{search_result.get('query', query)}’ 검색 결과")
            schedule_columns = st.columns(2)
            with schedule_columns[0]:
                selected_time = st.time_input(
                    "일정 시작 시각",
                    value=time(10, 0),
                    key=f"google_place_time_{state_key}",
                )
            with schedule_columns[1]:
                stay_minutes = st.number_input(
                    "예상 머무는 시간(분)",
                    min_value=0,
                    max_value=1440,
                    value=60,
                    step=10,
                    key=f"google_place_stay_{state_key}",
                )

            for place in places:
                google_place_id = str(place.get("google_place_id") or "").strip()
                if not google_place_id:
                    continue
                with st.container(border=True):
                    st.markdown(f"**{escape(str(place.get('display_name') or '이름 없는 장소'))}**")
                    address = str(place.get("formatted_address") or "주소 정보 없음")
                    st.caption(f"{address} · {_place_rating_text(place)}")
                    if st.button(
                        "이 DAY에 추가",
                        key=f"add_google_place_{state_key}_{google_place_id}",
                        use_container_width=True,
                    ):
                        try:
                            travel_date = date.fromisoformat(str(day["travel_date"]))
                            trip_timezone = travel_timezone(trip.get("timezone"))
                            starts_at = datetime.combine(travel_date, selected_time).replace(
                                tzinfo=trip_timezone
                            )
                            with st.spinner("선택한 장소를 일정에 넣고 있어요..."):
                                api(
                                    "POST",
                                    f"/trips/{trip['id']}/days/{day['id']}/google-places",
                                    json={
                                        "google_place_id": google_place_id,
                                        "start_at": starts_at.isoformat(),
                                        "estimated_stay_minutes": int(stay_minutes),
                                        "travel_mode": "walk",
                                    },
                                    headers=auth_headers(),
                                )
                        except (ApiError, ValueError) as error:
                            st.error(str(error))
                        else:
                            # 저장된 일정으로 대시보드가 다시 실행되는 즉시 새 마커와
                            # 순서가 정해진 동선을 표시한다.
                            map_state[state_key] = True
                            st.rerun()

        # Google 검색으로 저장한 장소는 안정적인 좌표가 있으므로 브라우저 새로고침으로
        # Streamlit 상태가 비워진 뒤에도 지도를 자동 표시한다. 직접 입력한 항목과 AI
        # 초안 항목은 실제 좌표를 추측하면 잘못된 장소가 표시될 수 있어 포함하지 않는다.
        has_mappable_place = any(item.get("place_id") for item in day.get("items", []))
        show_map = map_state.get(state_key, has_mappable_place)

        if not has_mappable_place:
            st.info("지도에 표시할 장소를 Google 장소 검색에서 1개 이상 추가해 주세요.")
            return

        button_text = "지도·동선 새로고침" if show_map else "지도와 이동 동선 보기"
        if st.button(button_text, key=f"show_day_map_{state_key}", use_container_width=True):
            map_state[state_key] = True
            st.rerun()

        if not show_map:
            return

        mode = st.selectbox(
            "이동 수단",
            ["walk", "transit", "drive", "bicycle"],
            format_func=lambda value: {
                "walk": "도보",
                "transit": "대중교통",
                "drive": "자동차",
                "bicycle": "자전거",
            }[value],
            key=f"day_map_mode_{state_key}",
        )
        try:
            with st.spinner("지도와 Google Routes 동선을 만들고 있어요..."):
                map_data = api(
                    "GET",
                    f"/trips/{trip['id']}/days/{day['id']}/map",
                    params={"travel_mode": mode},
                    headers=auth_headers(),
                )
        except ApiError as error:
            st.info(str(error))
            return

        markers = map_data.get("markers") or []
        if markers:
            marker_order = " → ".join(
                f"{marker.get('sequence')}. {marker.get('title')}" for marker in markers
            )
            st.caption(f"동선 순서: {marker_order}")
        if route := map_data.get("route"):
            distance_km = float(route.get("distance_meters", 0)) / 1000
            mode_label = {
                "walk": "도보",
                "transit": "대중교통",
                "drive": "자동차",
                "bicycle": "자전거",
            }[mode]
            st.success(
                f"{_route_duration_text(route.get('duration_seconds'))} · {distance_km:.1f}km · "
                f"{mode_label}"
            )
        elif len(markers) == 1:
            st.caption("장소가 하나라 이동 동선은 아직 없습니다.")
        if route_warning := map_data.get("route_warning"):
            st.warning(f"마커는 표시했지만 Routes 동선을 만들지 못했습니다: {route_warning}")

        if render_interactive_google_map(map_data):
            st.caption(
                "Google 지도 · 마커를 클릭하면 장소 정보를 볼 수 있고, "
                "지도를 확대하거나 이동할 수 있습니다."
            )


def render_day(trip: dict, day: dict) -> None:
    """일정 항목과 제어 요소를 포함한 여행 일차 하나를 그린다."""
    heading = day.get("title") or f"DAY {day['day_number']}"
    st.markdown(f'<div class="day-title">{escape(heading)}</div>', unsafe_allow_html=True)
    st.caption(f"{day['travel_date']} · {day.get('area') or '지역 미정'}")

    items = day.get("items", [])
    if not items:
        st.info("아직 일정이 없습니다. 아래에서 직접 추가해 보세요.")
    for item in items:
        main_col, action_col = st.columns([9, 1])
        with main_col:
            if isinstance(item.get("place"), dict):
                # 위치 버튼은 별도 열을 차지하지 않고 카드 안쪽에 겹쳐 보인다.
                with st.container(key=f"itinerary_item_row_{item['id']}", border=False):
                    render_itinerary_item_card(item)
                    with st.container(
                        key=f"itinerary_place_info_{item['id']}", border=False
                    ):
                        place_popover = st.popover(
                            "정보",
                            key=f"itinerary_place_popover_{item['id']}",
                            type="tertiary",
                            help="Google 장소 정보",
                            on_change="rerun",
                        )
                        if place_popover.open:
                            with place_popover:
                                render_cached_google_place_info(item)
            else:
                render_itinerary_item_card(item)
        with action_col:
            with st.container(key=f"itinerary_delete_{item['id']}", border=False):
                if st.button("삭제", key=f"delete_{item['id']}"):
                    try:
                        api(
                            "DELETE",
                            f"/trips/{trip['id']}/itinerary-items/{item['id']}",
                            headers=auth_headers(),
                        )
                    except ApiError as error:
                        st.error(str(error))
                    else:
                        st.rerun()
    add_itinerary_item(trip, day)
    render_google_place_planner(trip, day)

def render_trip_dates_editor(trip: dict) -> None:
    """대시보드의 기간 카드 안에 여행 기간 선택기를 직접 그린다."""

    start_value = trip.get("start_date")
    end_value = trip.get("end_date")
    if start_value and end_value:
        start_date = date.fromisoformat(start_value)
        end_date = date.fromisoformat(end_value)
    else:
        start_date = date.today()
        end_date = start_date

    st.markdown('<div class="stat-label">여행 기간</div>', unsafe_allow_html=True)
    with st.form(f"trip_dates_form_{trip['id']}"):
        selected_dates = st.date_input(
            "날짜 선택",
            value=(start_date, end_date),
            format="YYYY-MM-DD",
        )
        submitted = st.form_submit_button(
            "날짜 변경",
            use_container_width=True,
            type="primary",
        )

    if not submitted:
        return
    if not isinstance(selected_dates, tuple) or len(selected_dates) != 2:
        st.error("시작일과 종료일을 모두 선택하세요.")
        return

    try:
        api(
            "PATCH",
            f"/trips/{trip['id']}/dates",
            json={
                "start_date": selected_dates[0].isoformat(),
                "end_date": selected_dates[1].isoformat(),
            },
            headers=auth_headers(),
        )
    except ApiError as error:
        st.error(str(error))
        return
    st.rerun()

def render_chat(trip: dict) -> None:
    """여행의 채팅 기록을 표시하고 여행 도우미에게 새 질문을 보낸다."""
    st.divider()
    st.subheader("✦ TripMate AI와 여행 이야기하기")
    st.caption("여행지, 일정 아이디어, 준비물을 물어보세요. AI 답변은 이 여행에만 저장됩니다.")
    try:
        messages = api("GET", f"/trips/{trip['id']}/messages", headers=auth_headers())
    except ApiError as error:
        st.error(str(error))
        return

    chat_box = st.container(height=340)
    with chat_box:
        if not messages:
            st.caption("예: ‘도쿄 3박 4일 일정의 첫날에 무엇을 하면 좋을까?’")
        for message in messages:
            if message["role"] == "system":
                continue
            with st.chat_message(message["role"]):
                st.write(message["content"])

    prompt = st.chat_input("TripMate에게 물어보세요")
    if prompt:
        # 현재 질문은 위에서 불러온 기록에 아직 없으므로 서버가 AI 답변을 스트리밍하는
        # 동안 즉시 그려 준다.
        with chat_box:
            with st.chat_message("user"):
                st.write(prompt)

            with st.chat_message("assistant"):
                try:
                    st.write_stream(
                        stream_answer(
                            f"/trips/{trip['id']}/chat",
                            {"content": prompt},
                            headers=auth_headers(),
                        )
                    )
                except SessionExpired:
                    # 애플리케이션 최상위 처리기가 만료된 세션을 비우도록 한다.
                    raise
                except ApiError as error:
                    st.error(str(error))
                    return

        # 백엔드는 스트림이 끝난 뒤 완성된 AI 메시지를 저장한다. 저장된 대화가 이
        # 임시 화면을 대체하도록 그때만 다시 실행한다.
        st.rerun()

def render_dashboard(trip_id: str) -> None:
    """선택한 여행의 요약·일정·채팅 영역을 불러와 그린다."""
    dashboard = api("GET", f"/trips/{trip_id}/dashboard", headers=auth_headers())
    trip, days = dashboard["trip"], dashboard["days"]
    item_count = sum(len(day.get("items", [])) for day in days)

    st.markdown(
        f'''<div class="hero">
            <div class="eyebrow" style="color:#cbd9ff">MY TRAVEL</div>
            <h1>{escape(trip['title'])}</h1>
            <p>{escape(trip.get('destination') or '여행지 미정')} · {escape(formatted_dates(trip))}</p>
        </div>''',
        unsafe_allow_html=True,
    )

    stat_columns = st.columns(3)
    with stat_columns[0]:
        with st.container(border=True):
            render_trip_dates_editor(trip)

    stats = [
        ("여행 일차", f"{len(days)}일"),
        ("등록한 일정", f"{item_count}개"),
    ]
    for column, (label, value) in zip(stat_columns[1:], stats):
        with column:
            st.markdown(
                f'<div class="stat"><div class="stat-label">{escape(label)}</div><div class="stat-value">{escape(value)}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)
    if not days:
        st.info("여행 기간을 정하면 DAY별 일정표가 자동으로 만들어집니다.")
    else:
        tabs = st.tabs([f"DAY {day['day_number']}" for day in days])
        for tab, day in zip(tabs, days):
            with tab:
                render_day(trip, day)

    render_chat(trip)

def render_signed_in() -> None:
    """현재 사용자의 여행을 불러오고 알맞은 로그인 상태 화면을 그린다."""
    trips = api("GET", "/me/trips", headers=auth_headers())
    if trips and st.session_state.selected_trip_id not in {trip["id"] for trip in trips}:
        st.session_state.selected_trip_id = trips[0]["id"]
        request_main_scroll_to_top()

    render_sidebar(trips)

    if st.session_state.show_create_trip:
        st.markdown('<div class="brand">새 여행 추가</div>', unsafe_allow_html=True)
        st.caption("여행 기간을 정하면 DAY별 AI 일정 초안이 자동으로 생성됩니다.")
        render_create_trip_form("create_trip")
        return

    if not trips:
        st.markdown('<div class="empty-card"><div class="brand">첫 여행을 만들어 보세요.</div><p>여행지와 기간을 정하면 일차별 AI 일정 초안이 준비됩니다.</p></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        render_create_trip_form("first_trip")
        return

    if st.session_state.selected_trip_id:
        render_dashboard(st.session_state.selected_trip_id)


# 어떤 화면을 그릴지 결정하기 전에 유지되는 UI 상태를 초기화한다.
initialize_session()
debug_auto_login()

# 세션 상태에 따라 화면을 분기하고 API 실패를 사용자용 메시지로 바꾼다.
try:
    if st.session_state.access_token:
        render_signed_in()
    else:
        render_login()
except SessionExpired as error:
    sign_out(str(error))
except ApiError as error:
    st.error(str(error))

# 채팅 입력칸까지 화면을 모두 그린 뒤에 실행해야, 마지막 입력칸의 자동 포커스가
# 로그인·여행 전환 직후 화면을 다시 아래로 내리는 일을 막을 수 있다.
scroll_main_to_top_if_requested()
