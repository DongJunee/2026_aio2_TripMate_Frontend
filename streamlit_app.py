import json
import os
from datetime import date, datetime, time, timedelta, timezone
from html import escape
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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

TRAVEL_PARTY_LABELS = {
    "unspecified": "아직 정하지 않았어요",
    "solo": "혼자",
    "couple": "커플",
    "friends": "친구와",
    "family": "가족과",
    "family_with_children": "아이 동반 가족",
    "with_parents": "부모님과",
    "senior_couple": "시니어 부부",
    "other": "기타",
}

INTENSITY_GUIDE = (
    "1 아주 여유롭게 · 2 여유롭게 · 3 보통 · 4 알차게 · 5 아주 알차게"
)
BUDGET_GUIDE = "1 최대한 절약 · 2 절약 · 3 보통 · 4 여유 있게 · 5 넉넉하게"

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
            min-width: 0 !important;
            max-width: 100% !important;
            overflow: hidden !important;
        }
        /* 여행 이름은 한 줄로 유지하고 사이드바 너비를 넘는 부분만 ...으로 줄인다. */
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_select_"] button {
            min-width: 0 !important;
            max-width: 100% !important;
            overflow: hidden !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_select_"] button p {
            width: 100% !important;
            min-width: 0 !important;
            overflow: hidden !important;
            white-space: nowrap !important;
            text-overflow: ellipsis !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_select_"] button[kind="secondary"]:hover { background: rgba(49, 51, 63, .06) !important; border-color: transparent !important; }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_select_"] button[kind="primary"] { background: #e5f2ff !important; border-color: #d2e8ff !important; border-left: 8px solid #3169e8 !important; color: #2872d8 !important; }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_select_"] button[kind="primary"] p { width: 100%; color: #2872d8 !important; font-weight: 700; text-align: left !important; }
        /* 테두리 북마크는 고정되지 않음을, 파란 채움 북마크는 현재 고정 상태를
           뜻한다. Streamlit의 회색 스위치를 대신한다. */
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_pin_"] button {
            position: relative;
            min-width: 2rem !important;
            min-height: 2rem !important;
            padding: 0 !important;
            border-radius: .55rem !important;
        }
        /* 아이콘 폰트의 FILL 지원 여부에 의존하지 않고 같은 북마크 도형을
           직접 그린다. 원래 라벨은 숨겨도 버튼 크기와 접근성 이름은 유지한다. */
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_pin_"] button > * {
            opacity: 0 !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_pin_"] button::after {
            content: "";
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 1.25rem;
            height: 1.25rem;
            pointer-events: none;
            background-color: currentColor;
            --pin-shape: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill-rule='evenodd' d='M7 3h10a2 2 0 0 1 2 2v16l-7-3-7 3V5a2 2 0 0 1 2-2Zm0 2v12.97l5-2.14 5 2.14V5Z'/%3E%3C/svg%3E");
            -webkit-mask: var(--pin-shape) center / contain no-repeat;
            mask: var(--pin-shape) center / contain no-repeat;
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
            /* primary는 고정 상태를 구분하는 표식으로만 사용한다. 버튼 바탕은
               그대로 두고 채워진 bookmark 아이콘에만 파란색을 적용한다. */
            background: transparent !important;
            border-color: transparent !important;
            color: #3169e8 !important;
            box-shadow: none !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_pin_"] button[kind="primary"]::after {
            /* 바깥 윤곽은 같고, 고정되면 내부의 빈 부분만 없앤다. */
            --pin-shape: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M7 3h10a2 2 0 0 1 2 2v16l-7-3-7 3V5a2 2 0 0 1 2-2Z'/%3E%3C/svg%3E");
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_pin_"] button[kind="primary"]:hover {
            background: #eef3fb !important;
            border-color: transparent !important;
            color: #3169e8 !important;
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
        /* 기본 Streamlit 사이드바 너비는 약 336px이다. 280px은 여행 이름을
           읽기 좋게 유지하면서 그 너비의 약 70%에 해당한다. */
        [data-testid="stSidebar"] {
            width: 280px !important;
            min-width: 280px !important;
            max-width: 280px !important;
            flex: 0 0 280px !important;
            overflow: hidden;
        }
        [data-testid="stSidebar"] > div:first-child {
            width: 280px !important;
            min-width: 280px !important;
            max-width: 280px !important;
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
          margin-top: 0 !important;
          text-align: center !important;
        }
        .empty-card { padding: 2.2rem; text-align: center; border: 1px dashed #c8d4eb; border-radius: 18px; background: white; }
        .login-wrap { max-width: 470px; margin: 8vh auto; }
        .login-card { padding: 2.7rem 2.25rem; border-radius: 24px; background: white; border: 1px solid #e3e9f6; box-shadow: 0 18px 45px rgba(37, 64, 120, .08); }
        /* 여행이 선택된 화면은 1920×1080에서 페이지 자체가 아니라 일정 목록만
           스크롤되도록 한 화면 높이에 맞춘다. 로그인·새 여행 화면에는 적용하지 않는다. */
        [data-testid="stMainBlockContainer"]:has(.st-key-trip_dashboard_shell) {
          height: 100dvh !important;
          max-width: none !important;
          padding-top: 15px !important;
          padding-right: 80px !important;
          padding-bottom: 15px !important;
          padding-left: 80px !important;
          overflow: hidden !important;
        }
        .st-key-trip_dashboard_shell { height: calc(100dvh - 16px); overflow: hidden; }
        .st-key-trip_dashboard_shell > div,
        .st-key-trip_dashboard_shell [data-testid="stHorizontalBlock"] { min-height: 0; }
        /* Windows 화면 배율이나 브라우저 줌에 따라 CSS 픽셀 높이가 달라져도
           실제 화면에서 일정·지도·채팅이 비슷한 비율을 차지하게 한다. */
        /* 일정 목록의 실제 높이와 스크롤은 render_compact_schedule()의
           st.container(height=...) 한 곳에서만 정한다. */
        /* 일정 카드와 이동 안내를 각각 Streamlit 요소로 그려도 기본 1rem 간격이
           두 번 생기지 않도록 이 스크롤 영역 안에서만 세로 간격을 줄인다. */
        .st-key-trip_dashboard_shell [class*="st-key-dashboard_schedule_"][data-testid="stVerticalBlock"],
        .st-key-trip_dashboard_shell [class*="st-key-dashboard_schedule_"] > [data-testid="stVerticalBlock"] {
          gap: 20px; !important;
          row-gap: 20px; !important;
        }
        .st-key-trip_dashboard_shell [class*="st-key-dashboard_schedule_"] [data-testid="stHorizontalBlock"] {
          gap: .45rem !important;
        }
        /* 지도 높이 */
        .st-key-trip_dashboard_shell iframe[title="streamlit_components.v1.components.html"] {
          height: 35dvh !important;
          min-height: 165px !important;
          max-height: 400px !important;
        }
        /* 오른쪽 채팅 높이 */
        .st-key-trip_dashboard_shell [class*="st-key-dashboard_chat_"] {
          height: 100dvh !important;
          min-height: 430px !important;
          max-height: 900px !important;
          overflow-y: auto !important;
        }
        .st-key-trip_dashboard_shell [class*="st-key-dashboard_day_"] button,
        .st-key-trip_dashboard_shell [class*="st-key-dashboard_day_previous_"] button,
        .st-key-trip_dashboard_shell [class*="st-key-dashboard_day_next_"] button {
          height: clamp(32px, 4.5dvh, 42px) !important;
          min-height: 0 !important;
          padding-top: .2rem !important;
          padding-bottom: .2rem !important;
        }
        .dashboard-panel { height: 100%; border: 1px solid #e1e7f0; border-radius: 16px; background: var(--secondary-background-color); }
        .dashboard-date-summary { display:flex; align-items:center; justify-content:space-between; gap:.75rem; height:clamp(36px, 5.5dvh, 52px); box-sizing:border-box; padding:.4rem .9rem; border:1px solid #e2e8f2; border-radius:12px; margin:.25rem 0 .4rem; }
        .dashboard-date-title { font-size:.98rem; font-weight:800; }
        .dashboard-badges { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:.35rem; }
        .dashboard-badge { padding:.22rem .55rem; border-radius:999px; background:#edf3ff; color:#315fca; font-size:.7rem; font-weight:700; white-space:nowrap; }
        /* 일정 한 줄 전체를 하나의 카드로 감싼다. 정보·삭제 버튼도 카드 안쪽에
           두고, 오른쪽 끝과 버튼 사이에는 20px의 여백을 남긴다. */
        .st-key-trip_dashboard_shell [class*="st-key-dashboard_item_row_"] {
          padding: .3rem 10px .3rem .8rem !important;
          border: 1px solid #dfe6f2;
          border-radius: 12px;
          background: var(--secondary-background-color);
        }
        /* 일정 내용은 위의 큰 카드 안에 들어가므로 별도 카드 테두리를 만들지 않는다. */
        .compact-item { padding:.25rem 0; border:0; border-radius:0; background:transparent; }
        .compact-item-time { color:#5276d8; font-size:.72rem; font-weight:800; }
        .compact-item-title { margin:.12rem 0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:.9rem; font-weight:800; }
        .compact-item-meta { color:#748198; font-size:.69rem; }
        /* 일정 카드 오른쪽 기능 버튼은 칼럼 비율과 관계없이 동일한 아이콘 크기를 쓴다. */
        .st-key-trip_dashboard_shell [class*="st-key-compact_move_"] button,
        .st-key-trip_dashboard_shell [class*="st-key-compact_time_"] button,
        .st-key-trip_dashboard_shell [class*="st-key-compact_place_"] button,
        .st-key-trip_dashboard_shell [class*="st-key-compact_delete_"] button {
          width: 30px !important;
          min-width: 30px !important;
          height: 30px !important;
          min-height: 30px !important;
          padding: 0 !important;
        }
        .route-leg { margin:.05rem 0 .05rem 1rem; color:#687790; font-size:.7rem; }
        .route-leg::before { content:"↓"; margin-right:.35rem; color:#4d78e5; }
        .dashboard-section-label { margin:.35rem 0 .25rem; font-size:.8rem; font-weight:800; }
        .route-summary { display:grid; grid-template-columns:1fr 1fr 1fr; gap:.5rem; padding:.6rem .75rem; border:1px solid #e1e7f0; border-radius:12px; }
        .route-summary span { display:block; color:#748198; font-size:.65rem; }
        .route-summary b { font-size:.82rem; }
        .trip-chat-title { margin:0; font-size:1.1rem; font-weight:850; }
        .trip-chip-row { display:flex; flex-wrap:wrap; gap:.35rem; margin:.55rem 0 .7rem; }
        .trip-chip { padding:.25rem .55rem; border-radius:999px; background:#eef3ff; color:#315fca; font-size:.68rem; font-weight:700; }
        .itinerary-change-status { margin:.15rem 0 .65rem; padding:.65rem .75rem; border:1px solid #d9e6ff; border-radius:12px; background:#f3f7ff; }
        .itinerary-change-status-title { color:#315fca; font-size:.74rem; font-weight:800; }
        .itinerary-change-status-message { margin-top:.16rem; font-size:.8rem; font-weight:700; }
        .itinerary-change-status-detail { margin-top:.1rem; color:#687790; font-size:.7rem; }
        .welcome-message { padding:.85rem 1rem; border-radius:14px; background:#f1f5ff; color:#243652; font-size:.82rem; line-height:1.55; }
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
        # 채팅에서 장소 추천을 요청했을 때, 현재 세션에서만 보여 줄 추천 카드다.
        # 실제로 선택한 장소만 itinerary_items에 저장한다.
        "chat_place_recommendations": {},
        # 여행별로 선택한 DAY와 4개씩 보이는 날짜 창의 시작 위치를 유지한다.
        "dashboard_selected_days": {},
        "dashboard_day_windows": {},
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
    st.session_state.chat_place_recommendations = {}
    st.session_state.notice = notice
    st.rerun()


def travel_timezone(timezone_name: object) -> object:
    """여행지의 IANA 시간대를 반환하며 서머타임 규칙까지 적용한다.

    일반적인 프로젝트 동기화는 ``tzdata``를 설치하므로 완전한 IANA 시간대 규칙을
    사용한다. 패키지가 없을 때는 서머타임이 없는 지원 지역만 고정 시차를 쓰고,
    그 밖의 지역을 임의로 서울 시간이나 겨울 시간으로 바꾸지 않는다.
    """

    name = str(timezone_name or "Asia/Seoul").strip() or "Asia/Seoul"
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        fixed_offsets = {
            "UTC": 0,
            "Asia/Seoul": 9,
            "Asia/Tokyo": 9,
            "Pacific/Honolulu": -10,
        }
        if name not in fixed_offsets:
            raise ValueError(
                "여행지 시간대 정보를 불러오지 못했습니다. tzdata 설치와 여행 시간대를 확인하세요."
            ) from error
        return timezone(timedelta(hours=fixed_offsets[name]), name=name)

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

# def render_login() -> None:
#     """비로그인 카드를 그리고 현재 인증 화면을 선택해 표시한다."""
#     if st.session_state.notice:
#         st.warning(st.session_state.notice)

#     _, card_column, _ = st.columns([1, 1.25, 1])
#     with card_column:
#         st.markdown('<div class="brand">TripMate</div>', unsafe_allow_html=True)
#         if st.session_state.auth_mode == "password_reset":
#             render_password_reset()
#         else:
#             render_sign_in_or_up()
#         st.markdown("</div>", unsafe_allow_html=True)

def render_login() -> None:
    """비로그인 화면을 왼쪽 이미지 + 오른쪽 로그인 영역으로 표시한다."""

    if st.session_state.notice:
        st.warning(st.session_state.notice)

    # 왼쪽 이미지 40% / 오른쪽 로그인 영역 60%
    left_column, right_column = st.columns(
        [2, 3],
        gap=None,
        vertical_alignment="top",
    )

    # 왼쪽 이미지
    with left_column:
        image_path = os.path.join(
            os.path.dirname(__file__),
            "assets",
            "login_image.png",
        )

        st.image(
            image_path,
            use_container_width=True,
        )

    # 오른쪽 로그인
    with right_column:

        # 로그인 폼의 최대 너비를 줄이기 위한 내부 컬럼
        _, login_column, _ = st.columns(
            [0.8, 2, 0.8]
        )

        with login_column:
            st.markdown(
                '<div class="brand">만나서 반가워요</div>',
                unsafe_allow_html=True,
            )

            if st.session_state.auth_mode == "password_reset":
                render_password_reset()
            else:
                render_sign_in_or_up()

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

def render_travel_preference_sliders(
    key_prefix: str, intensity: int = 3, budget: int = 3
) -> tuple[int, int]:
    """여행 강도와 상대적인 경비 수준을 1~5단계로 선택한다."""

    intensity_column, budget_column = st.columns(2)
    with intensity_column:
        selected_intensity = st.slider(
            "여행 강도",
            min_value=1,
            max_value=5,
            value=intensity,
            step=1,
            key=f"{key_prefix}_travel_intensity",
            help=(
                "일반 날짜에는 관광·활동을 강도와 같은 개수로 배치하고 점심·저녁을 추가해요. "
                "1단계는 호텔 휴식 2회, 2단계는 호텔 휴식 1회를 포함해요. "
                "마지막 날은 현지 18시 출국 가정을 우선하여 일정을 줄여요. "
                "관광·식당은 선택한 도시 안에서 추천하며, 체크인은 숙소 확인이 필요해요."
            ),
        )
        st.caption(INTENSITY_GUIDE)
    with budget_column:
        selected_budget = st.slider(
            "여행 경비 수준",
            min_value=1,
            max_value=5,
            value=budget,
            step=1,
            key=f"{key_prefix}_budget_level",
            help="실제 총예산 금액이 아닌, 장소와 식당을 추천할 때 참고할 소비 수준이에요.",
        )
        st.caption(BUDGET_GUIDE)

    # 양식 안의 슬라이더는 제출 전에는 재실행되지 않으므로, 선택값에 따라 바뀌는
    # 미리보기 대신 모든 단계에 적용되는 일정 수 규칙을 항상 같은 안내로 보여 준다.
    st.caption(
        "일반 날짜 관광·활동: 1~5단계 각각 1·2·3·4·5개 + 점심·저녁. "
        "호텔 휴식은 1단계 2회, 2단계 1회가 추가돼요. "
        "1~2단계는 오전에 여유 시간을 두어요. "
        "새 일정은 선택한 도시 안에서 추천하고, 마지막 날은 현지 18시 출국 기준으로 줄여요."
    )
    return selected_intensity, selected_budget


def open_create_trip_form() -> None:
    """새 여행 화면에 새로 진입할 때만 이전 입력을 비우고 화면을 연다."""

    if not st.session_state.get("show_create_trip", False):
        # 첫 여행 양식과 사이드바로 연 양식은 서로 다른 키를 사용한다. 위젯을
        # 그리기 전의 진입 시점에만 비워야 생성 처리·실패·일반 재실행 중 값이 유지된다.
        for form_key in ("create_trip", "first_trip"):
            for field in (
                "title", "destination", "dates", "travel_party", "travel_intensity", "budget_level"
            ):
                st.session_state.pop(f"{form_key}_{field}", None)
    st.session_state.show_create_trip = True


def render_create_trip_form(form_key: str) -> None:
    """여행과 첫 AI 일정 초안을 만드는 양식을 그리고 제출한다."""
    # 제출 직후에는 입력을 초기화하지 않고 API 완료 후에만 대시보드로 이동한다.
    with st.form(form_key, clear_on_submit=False):
        title = st.text_input(
            "여행 이름", placeholder="예: 봄날의 도쿄 여행", key=f"{form_key}_title"
        )
        destination = st.text_input(
            "여행지", placeholder="예: 도쿄, 일본", key=f"{form_key}_destination"
        )
        today = date.today()
        selected_dates = st.date_input(
            "여행 기간",
            value=(today, today + timedelta(days=3)),
            format="YYYY-MM-DD",
            key=f"{form_key}_dates",
        )
        travel_party = st.selectbox(
            "여행 인원 구성",
            options=list(TRAVEL_PARTY_LABELS),
            format_func=TRAVEL_PARTY_LABELS.get,
            key=f"{form_key}_travel_party",
        )
        travel_intensity, budget_level = render_travel_preference_sliders(form_key)
        st.caption("일정은 매일 여행지 현지 시간 오전 9시부터 시작해요.")
        st.caption(
            "마지막 날은 13시까지 관광·점심 → 13~15시 공항 이동 예비 시간 → "
            "15~18시 출국 수속 준비로 계획해요. 근교 도시 관광은 포함하지 않아요."
        )
        st.caption(
            "18시 출국은 기본 가정이에요. 공항·항공편은 아직 정해지지 않았고, "
            "이동 예비 2시간은 실제 경로를 계산한 시간이 아니므로 항공편에 맞춰 확인해 주세요."
        )
        submitted = st.form_submit_button("여행 만들기", use_container_width=True, type="primary")

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
                # 강도가 높은 여러 날의 일정은 실제 장소 검색도 많아 생성 요청만
                # 일반 화면 조회보다 오래 기다린다.
                timeout=180,
                json={
                    "title": title.strip(),
                    "destination": destination.strip(),
                    # 현지 시간대는 백엔드가 여행지를 기준으로 결정한다.
                    "start_date": selected_dates[0].isoformat(),
                    "end_date": selected_dates[1].isoformat(),
                    "travel_party": travel_party,
                    "travel_intensity": travel_intensity,
                    "budget_level": budget_level,
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
    st.success(f"새 여행과 식사·활동·휴식을 포함한 일정 {count}개를 만들었어요.")
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

        # 실제 표시는 위의 북마크 SVG가 담당하고, 이 라벨은 버튼 크기를 유지한다.
        pin_label = ":material/bookmark:"
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
                open_create_trip_form()
                # 버튼 클릭 자체가 재실행을 일으킨다. 여기서 다시 중단하면 아직
                # 그리지 않은 양식 위젯 상태가 정리될 수 있어 같은 실행에서 이어 그린다.

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


def item_time_text(item: dict, timezone_name: object) -> str:
    """DB의 UTC 시각을 해당 여행지의 현지 날짜·시각으로 바꾸어 표시한다."""
    start, end = item.get("start_at"), item.get("end_at")
    if not start:
        return "시간 미정"
    try:
        trip_timezone = travel_timezone(timezone_name)
    except ValueError:
        return "여행지 시간대 확인 필요"

    def local_time_text(value: object) -> str:
        """시차가 없는 기존 시각은 여행지 현지 시각으로 해석한다."""
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        # tzinfo가 없는 값에 astimezone을 바로 쓰면 실행 서버의 시간대가 섞인다.
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=trip_timezone)
        return parsed.astimezone(trip_timezone).strftime("%Y-%m-%d %H:%M")

    try:
        start_text = local_time_text(start)
        end_text = local_time_text(end) if end else ""
    except (TypeError, ValueError):
        return "시간 형식 확인 필요"
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


def render_itinerary_item_card(item: dict, timezone_name: object) -> None:
    """장소 연결 여부와 관계없이 기존 일정 카드 모양을 일정하게 그린다."""

    item_type = str(item.get("item_type") or "place")
    type_label = {"hotel": "숙소", "note": "안내"}.get(item_type, item_type)
    notes = str(item.get("notes") or "").strip()
    # 숙소 미정·체크인 확인 같은 안내도 카드에 표시하되 외부 텍스트를 HTML로
    # 실행하지 않는다. 실제 장소를 정하기 전에는 지도 정보 버튼이 생기지 않는다.
    notes_html = (
        f'<div class="item-meta">{escape(notes).replace(chr(10), "<br>")}</div>'
        if notes else ""
    )
    st.markdown(
        f'''<div class="item-card">
            <b>{escape(str(item.get('title') or '일정'))}</b>
            <div class="item-meta">{escape(type_label)} · {escape(item_time_text(item, timezone_name))}</div>
            {notes_html}
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
        "routeSegments": [
            str(segment.get("encoded_polyline") or "")
            for segment in map_data.get("route_segments") or []
            if segment.get("encoded_polyline")
        ],
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

              if (tripmateData.routeSegments?.length && google.maps.geometry?.encoding) {{
                tripmateData.routeSegments.forEach((encoded) => {{
                  try {{
                    new google.maps.Polyline({{
                      path: google.maps.geometry.encoding.decodePath(encoded),
                      geodesic: true,
                      strokeColor: "#3169e8",
                      strokeOpacity: 0.9,
                      strokeWeight: 5,
                      map,
                    }});
                  }} catch (error) {{
                    console.warn("TripMate route segment could not be drawn.", error);
                  }}
                }});
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
        main_col, action_col = st.columns([9, 1], vertical_alignment="center")
        with main_col:
            if isinstance(item.get("place"), dict):
                # 위치 버튼은 별도 열을 차지하지 않고 카드 안쪽에 겹쳐 보인다.
                with st.container(key=f"itinerary_item_row_{item['id']}", border=False):
                    render_itinerary_item_card(item, trip.get("timezone"))
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
                render_itinerary_item_card(item, trip.get("timezone"))
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

def render_trip_preferences_editor(trip: dict) -> None:
    """저장된 동행 구성을 표시하고 강도와 경비 수준만 변경하여 저장한다."""

    trip_id = str(trip["id"])
    party_label = TRAVEL_PARTY_LABELS.get(trip.get("travel_party"), "아직 정하지 않았어요")
    with st.container(border=True):
        st.markdown("#### 여행 설정")
        st.caption(f"여행 인원 구성 · {party_label}")
        if st.session_state.pop(f"trip_preferences_saved_{trip_id}", False):
            st.success("여행 설정을 저장했어요.")
        with st.form(f"trip_preferences_form_{trip_id}"):
            intensity, budget = render_travel_preference_sliders(
                f"trip_preferences_{trip_id}",
                intensity=int(trip.get("travel_intensity") or 3),
                budget=int(trip.get("budget_level") or 3),
            )
            st.caption(
                "설정을 저장해도 기존 일정은 자동으로 변경되지 않아요. "
                "바뀐 조건은 이후 AI 채팅의 추천에 반영돼요."
            )
            submitted = st.form_submit_button("여행 설정 저장", type="primary")
    if not submitted:
        return

    try:
        api(
            "PATCH",
            f"/trips/{trip_id}",
            json={"travel_intensity": intensity, "budget_level": budget},
            headers=auth_headers(),
        )
    except ApiError as error:
        st.error(str(error))
        return
    st.session_state[f"trip_preferences_saved_{trip_id}"] = True
    st.rerun()


def _dashboard_selected_day(trip: dict, days: list[dict]) -> dict:
    """여행별 DAY 선택값을 확인하고 4개짜리 날짜 탐색 범위 안에 유지한다."""

    trip_id = str(trip["id"])
    selected_by_trip = st.session_state.dashboard_selected_days
    selected_index = min(max(int(selected_by_trip.get(trip_id, 0)), 0), len(days) - 1)
    window_by_trip = st.session_state.dashboard_day_windows
    window_start = min(max(int(window_by_trip.get(trip_id, 0)), 0), max(0, len(days) - 4))

    # 여행 일수에 따라 버튼이 생겼다 사라지지 않도록 화살표 자리는 항상 유지한다.
    # 이동할 날짜가 없는 경우에는 숨기는 대신 비활성화한다.
    columns = st.columns([.45, 1, 1, 1, 1, .45])
    with columns[0]:
        if st.button("‹", key=f"dashboard_day_previous_{trip_id}", disabled=window_start == 0,
                     use_container_width=True):
            window_by_trip[trip_id] = window_start - 1
            st.rerun()
    day_columns = columns[1:5]

    visible = days[window_start : window_start + 4]
    weekdays = "월화수목금토일"
    for column, day in zip(day_columns, visible):
        index = days.index(day)
        try:
            value = date.fromisoformat(str(day["travel_date"]))
            label = f"{day['day_number']}일 {value.month}.{value.day}({weekdays[value.weekday()]})"
        except (KeyError, TypeError, ValueError):
            label = f"DAY {day.get('day_number', index + 1)}"
        with column:
            if st.button(label, key=f"dashboard_day_{trip_id}_{day['id']}",
                         type="primary" if index == selected_index else "secondary",
                         use_container_width=True):
                selected_by_trip[trip_id] = index
                st.rerun()

    with columns[5]:
        if st.button("›", key=f"dashboard_day_next_{trip_id}",
                     disabled=window_start + 4 >= len(days), use_container_width=True):
            window_by_trip[trip_id] = window_start + 1
            st.rerun()
    return days[selected_index]


def _local_datetime(value: object, timezone_name: object) -> datetime | None:
    """저장된 시각을 여행지 현지 datetime으로 바꾼다."""

    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        zone = travel_timezone(timezone_name)
        return (parsed.replace(tzinfo=zone) if parsed.tzinfo is None else parsed.astimezone(zone))
    except (TypeError, ValueError):
        return None


def _round_up_quarter(value: datetime) -> datetime:
    """도착 시각을 다음 15분 단위로 올려 자연스러운 일정 시작 시각을 만든다."""

    value = value.replace(second=0, microsecond=0)
    remainder = value.minute % 15
    return value if remainder == 0 else value + timedelta(minutes=15 - remainder)


def _adjusted_schedule(items: list[dict], legs: list[dict], timezone_name: object) -> list[tuple[dict, datetime | None, datetime | None, dict | None]]:
    """실제 이동시간을 반영하되 기존 시작 시각보다 이르게 당기지 않는다."""

    ordered = sorted(items, key=lambda item: (item.get("start_at") is None, str(item.get("start_at") or ""), int(item.get("sort_order") or 0)))
    leg_by_destination = {str(leg.get("to_itinerary_item_id")): leg for leg in legs}
    calculated_ends: dict[str, datetime] = {}
    result = []
    for item in ordered:
        start = _local_datetime(item.get("start_at"), timezone_name)
        end = _local_datetime(item.get("end_at"), timezone_name)
        duration = (end - start) if start and end else timedelta(minutes=int(item.get("estimated_stay_minutes") or 0))
        leg = leg_by_destination.get(str(item.get("id")))
        # 직접 시간 변경한 일정은 사용자가 정한 시각을 우선한다. 이동 시간이 길어도
        # 화면에서 임의로 늦추지 않고, 충돌 여부는 사용자가 확인·조정할 수 있게 한다.
        if start and not item.get("is_fixed") and leg and leg.get("status") == "ok":
            previous_end = calculated_ends.get(str(leg.get("from_itinerary_item_id")))
            if previous_end:
                arrival = _round_up_quarter(previous_end + timedelta(seconds=float(leg.get("duration_seconds") or 0)))
                start = max(start, arrival)
                end = start + duration
        if end:
            calculated_ends[str(item.get("id"))] = end
        result.append((item, start, end, leg))
    return result


def _travel_leg_text(leg: dict | None) -> str | None:
    """자동 선택한 이동 수단과 실제 소요시간을 일정 사이 한 줄로 표시한다."""

    if not leg:
        return None
    if leg.get("status") != "ok":
        return "이동 경로 확인 안 됨 · 총 시간에서 제외"
    labels = {"walk": "도보", "transit": "대중교통", "drive": "자동차", "bicycle": "자전거"}
    minutes = max(1, round(float(leg.get("duration_seconds") or 0) / 60))
    return f"{labels.get(leg.get('travel_mode'), '이동')} {minutes}분"


def render_compact_schedule(trip: dict, day: dict, route_plan: dict) -> None:
    """선택 DAY의 일정만 고정 높이 스크롤 영역에 그린다."""

    items = day.get("items") or []
    # CSS가 로드되기 전에도 너무 작게 보이지 않도록 기본 높이도 함께 맞춘다.
    with st.container(height=300, key=f"dashboard_schedule_{day['id']}", border=False):
        if not items:
            st.info("아직 일정이 없습니다.")
            return
        schedule_rows = _adjusted_schedule(
            items, route_plan.get("legs") or [], trip.get("timezone")
        )
        for index, (item, start, end, leg) in enumerate(schedule_rows):
            if leg_text := _travel_leg_text(leg):
                st.markdown(f'<div class="route-leg">{escape(leg_text)}</div>', unsafe_allow_html=True)
            place = item.get("place") if isinstance(item.get("place"), dict) else {}
            rating = _place_rating_text(place) if place else "장소 정보 없음"
            time_text = f"{start:%H:%M}–{end:%H:%M}" if start and end else "시간 미정"
            stay = item.get("estimated_stay_minutes")
            stay_text = f" · 체류 {int(stay)}분" if isinstance(stay, (int, float)) else ""
            # 일정 내용과 기능 버튼을 한 카드 안의 두 영역으로 배치한다. 버튼 수가
            # 늘어나도 actions 영역 안에서만 확장되게 해 일정 내용 폭을 안정적으로 둔다.
            with st.container(key=f"dashboard_item_row_{item['id']}", border=False):
                main, actions = st.columns(
                    [7.5, 2.5],
                    vertical_alignment="center",
                    gap="small",
                )
                with main:
                    st.markdown(
                        f'<div class="compact-item"><div class="compact-item-time">{escape(time_text)}</div>'
                        f'<div class="compact-item-title">{escape(str(item.get("title") or "일정"))}</div>'
                        f'<div class="compact-item-meta">{escape(rating + stay_text)}</div></div>',
                        unsafe_allow_html=True,
                    )
                with actions:
                    previous, next_item, time_edit, info, remove = st.columns(
                        5,
                        gap="small",
                        vertical_alignment="center",
                    )
                    with previous:
                        if st.button(
                            "↑",
                            key=f"compact_move_previous_{item['id']}",
                            help="이전 시간 칸의 장소와 교환",
                            disabled=index == 0,
                        ):
                            try:
                                api(
                                    "POST",
                                    f"/trips/{trip['id']}/itinerary-items/{item['id']}/swap-place",
                                    json={"direction": "previous"},
                                    headers=auth_headers(),
                                )
                            except ApiError as error:
                                st.error(str(error))
                            else:
                                st.rerun()
                    with next_item:
                        if st.button(
                            "↓",
                            key=f"compact_move_next_{item['id']}",
                            help="다음 시간 칸의 장소와 교환",
                            disabled=index == len(schedule_rows) - 1,
                        ):
                            try:
                                api(
                                    "POST",
                                    f"/trips/{trip['id']}/itinerary-items/{item['id']}/swap-place",
                                    json={"direction": "next"},
                                    headers=auth_headers(),
                                )
                            except ApiError as error:
                                st.error(str(error))
                            else:
                                st.rerun()
                    with time_edit:
                        # 값이 없는 기존 일정도 오전 9시부터 직접 시간을 정할 수 있다.
                        start_value = (
                            start.replace(tzinfo=None).time() if start else time(9, 0)
                        )
                        end_value = (
                            end.replace(tzinfo=None).time() if end else time(10, 0)
                        )
                        with st.popover(
                            "◷",
                            key=f"compact_time_{item['id']}",
                            help="시작·종료 시간 변경",
                        ):
                            changed_start = st.time_input(
                                "시작 시간",
                                value=start_value,
                                key=f"compact_time_start_{item['id']}",
                            )
                            changed_end = st.time_input(
                                "종료 시간",
                                value=end_value,
                                key=f"compact_time_end_{item['id']}",
                            )
                            if st.button(
                                "시간 변경하기",
                                key=f"compact_time_submit_{item['id']}",
                                use_container_width=True,
                            ):
                                if changed_end <= changed_start:
                                    st.error("종료 시간은 시작 시간보다 늦어야 합니다.")
                                else:
                                    try:
                                        api(
                                            "POST",
                                            f"/trips/{trip['id']}/itinerary-items/{item['id']}/time",
                                            json={
                                                "start_time": changed_start.isoformat(),
                                                "end_time": changed_end.isoformat(),
                                            },
                                            headers=auth_headers(),
                                        )
                                    except ApiError as error:
                                        st.error(str(error))
                                    else:
                                        st.rerun()
                    with info:
                        if place:
                            with st.popover("ⓘ", key=f"compact_place_{item['id']}", help="장소 정보"):
                                render_cached_google_place_info(item)
                    with remove:
                        if st.button("×", key=f"compact_delete_{item['id']}", help="일정 삭제"):
                            try:
                                api("DELETE", f"/trips/{trip['id']}/itinerary-items/{item['id']}", headers=auth_headers())
                            except ApiError as error:
                                st.error(str(error))
                            else:
                                st.rerun()


def _recommendation_query_from_message(message: str) -> str:
    """추천 요청 문장에서 Google Places 검색에 적합한 장소·종류 검색어를 만든다."""

    query = message.strip()
    for phrase in (
        "추천해 주세요",
        "추천해주세요",
        "추천 해주세요",
        "추천해줘",
        "추천 해줘",
        "추천 부탁해",
        "추천 부탁드려요",
        "추천",
    ):
        query = query.replace(phrase, " ")
    return " ".join(query.split()) or message.strip()


def _looks_like_place_recommendation(message: str) -> bool:
    """장소 추천 카드가 필요한 채팅 요청인지 가볍게 판별한다."""

    return "추천" in message and bool(_recommendation_query_from_message(message))


def _recommendation_default_time(day: dict, trip: dict) -> time:
    """현재 DAY의 마지막 일정 뒤 30분을 추천 장소의 기본 시작 시각으로 잡는다."""

    trip_timezone = travel_timezone(trip.get("timezone"))
    latest_end: datetime | None = None
    for item in day.get("items") or []:
        value = item.get("end_at")
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=trip_timezone)
            parsed = parsed.astimezone(trip_timezone)
        except (TypeError, ValueError):
            continue
        latest_end = max(latest_end, parsed) if latest_end else parsed
    if latest_end is None:
        return time(10, 0)
    suggested = latest_end + timedelta(minutes=30)
    # 15분 단위로 올려 사람이 읽기 좋은 시간으로 표시한다.
    rounded_minute = ((suggested.minute + 14) // 15) * 15
    if rounded_minute == 60:
        suggested += timedelta(hours=1)
        rounded_minute = 0
    return suggested.replace(minute=rounded_minute, second=0, microsecond=0).time()


def _add_chat_recommendation_to_day(
    trip: dict, day: dict, place: dict, start_time: time
) -> None:
    """추천 카드에서 고른 검증된 Google 장소를 현재 열어 둔 DAY에 추가한다."""

    google_place_id = str(place.get("google_place_id") or "").strip()
    if not google_place_id:
        st.error("장소 식별자를 찾지 못했습니다. 다시 추천을 받아 주세요.")
        return
    try:
        travel_date = date.fromisoformat(str(day["travel_date"]))
        starts_at = datetime.combine(travel_date, start_time).replace(
            tzinfo=travel_timezone(trip.get("timezone"))
        )
        api(
            "POST",
            f"/trips/{trip['id']}/days/{day['id']}/google-places",
            json={
                "google_place_id": google_place_id,
                "start_at": starts_at.isoformat(),
                "estimated_stay_minutes": 60,
                "travel_mode": "walk",
            },
            headers=auth_headers(),
        )
    except (ApiError, ValueError) as error:
        st.error(str(error))
        return
    st.session_state.chat_place_recommendations.pop(str(trip["id"]), None)
    st.success(f"{place.get('display_name') or '선택한 장소'}을 DAY {day['day_number']} 일정에 추가했어요.")
    st.rerun()


def _render_recommendation_place_option(
    trip: dict,
    day: dict,
    place: dict,
    *,
    key_prefix: str,
    start_time: time,
) -> None:
    """추천 카드 안의 Google 장소 한 개와 일정 추가 버튼을 그린다."""

    place_id = str(place.get("google_place_id") or "").strip()
    if not place_id:
        return
    with st.container(border=True):
        st.markdown(f"**{escape(str(place.get('display_name') or '이름 없는 장소'))}**")
        st.caption(
            f"{place.get('formatted_address') or '주소 정보 없음'} · {_place_rating_text(place)}"
        )
        if st.button(
            "이 일정에 추가",
            key=f"{key_prefix}_add_{place_id}",
            use_container_width=True,
        ):
            _add_chat_recommendation_to_day(trip, day, place, start_time)


def render_chat_place_recommendation_card(trip: dict, day: dict) -> None:
    """채팅 추천 요청의 Google 장소 2개와 직접 검색 선택지 하나를 표시한다."""

    state = st.session_state.chat_place_recommendations.get(str(trip["id"]))
    if not isinstance(state, dict):
        return

    query = str(state.get("query") or "").strip()
    if not query:
        return
    if "recommendations" not in state and not state.get("load_error"):
        try:
            with st.spinner("Google Places에서 추천 장소를 찾고 있어요..."):
                search = api(
                    "GET",
                    f"/trips/{trip['id']}/days/{day['id']}/places/search",
                    params={"query": query, "max_results": 2},
                    headers=auth_headers(),
                )
        except ApiError as error:
            state["load_error"] = str(error)
        else:
            state["recommendations"] = search.get("places") or []
        st.session_state.chat_place_recommendations[str(trip["id"])] = state

    with st.container(key=f"chat_place_recommendation_{trip['id']}", border=True):
        st.markdown("#### AI 장소 추천")
        st.caption(
            f"‘{query}’ 기준 Google Places 후보예요. 선택한 장소는 현재 열린 DAY {day['day_number']}에 추가됩니다."
        )
        selected_time = st.time_input(
            "일정 시작 시각",
            value=_recommendation_default_time(day, trip),
            key=f"chat_recommendation_time_{trip['id']}",
        )
        if state.get("load_error"):
            st.warning(str(state["load_error"]))
        else:
            recommendations = state.get("recommendations") or []
            if recommendations:
                recommendation_columns = st.columns(2)
                for column, place in zip(recommendation_columns, recommendations[:2]):
                    with column:
                        _render_recommendation_place_option(
                            trip,
                            day,
                            place,
                            key_prefix=f"chat_recommendation_{trip['id']}",
                            start_time=selected_time,
                        )
            else:
                st.info("추천 장소를 찾지 못했습니다. 아래에서 장소를 직접 검색해 보세요.")

        st.divider()
        st.caption("원하는 장소가 있으면 Google Places에서 직접 한 곳을 찾아 추가할 수 있어요.")
        search_column, button_column = st.columns([4, 1])
        with search_column:
            direct_query = st.text_input(
                "직접 장소 검색",
                placeholder="예: 난바 조용한 카페",
                key=f"chat_recommendation_search_{trip['id']}",
                label_visibility="collapsed",
            )
        with button_column:
            searched = st.button(
                "검색",
                key=f"chat_recommendation_search_button_{trip['id']}",
                use_container_width=True,
            )
        if searched:
            if not direct_query.strip():
                st.warning("찾고 싶은 장소나 종류를 입력하세요.")
            else:
                try:
                    with st.spinner("Google 장소를 찾고 있어요..."):
                        direct_search = api(
                            "GET",
                            f"/trips/{trip['id']}/days/{day['id']}/places/search",
                            params={"query": direct_query.strip(), "max_results": 1},
                            headers=auth_headers(),
                        )
                except ApiError as error:
                    st.error(str(error))
                else:
                    state["direct_place"] = (direct_search.get("places") or [None])[0]
                    st.session_state.chat_place_recommendations[str(trip["id"])] = state
                    st.rerun()
        if direct_place := state.get("direct_place"):
            st.caption("직접 검색 결과")
            _render_recommendation_place_option(
                trip,
                day,
                direct_place,
                key_prefix=f"chat_direct_place_{trip['id']}",
                start_time=selected_time,
            )


def render_itinerary_change_card(trip: dict, change: dict) -> None:
    """채팅 타임라인 안에 일정 변경 상태와 가능한 되돌리기 버튼을 그린다."""

    status_col, undo_col = st.columns([5, 1], vertical_alignment="center", gap="small")
    with status_col:
        st.markdown(
            '<div class="itinerary-change-status">'
            '<div class="itinerary-change-status-title">일정 변경 상태</div>'
            f'<div class="itinerary-change-status-message">{escape(str(change.get("message") or "일정이 변경되었습니다."))}</div>'
            f'<div class="itinerary-change-status-detail">{escape(str(change.get("detail") or ""))}</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with undo_col:
        if change.get("can_undo") and st.button(
            "되돌리기",
            key=f"undo_itinerary_change_{change['id']}",
            use_container_width=True,
        ):
            try:
                api(
                    "POST",
                    f"/trips/{trip['id']}/itinerary-changes/{change['id']}/undo",
                    headers=auth_headers(),
                )
            except ApiError as error:
                st.error(str(error))
            else:
                st.rerun()


def render_dashboard_chat(trip: dict, days: list[dict], selected_day: dict) -> None:
    """여행 요약과 첫 안내를 포함한 오른쪽 채팅 패널을 그린다."""

    day_count = len(days)
    nights = max(0, day_count - 1)
    party = TRAVEL_PARTY_LABELS.get(trip.get("travel_party"), "구성 미정")
    purpose_value = trip.get("travel_purpose") or "맞춤 여행"
    purpose = ", ".join(map(str, purpose_value)) if isinstance(purpose_value, list) else str(purpose_value)
    destination = str(trip.get("destination") or "여행지")
    st.markdown(f'<div class="trip-chat-title">{escape(str(trip.get("title") or "나의 여행"))}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="trip-chip-row">'
        f'<span class="trip-chip">{escape(destination)}</span>'
        f'<span class="trip-chip">{nights}박 {day_count}일</span>'
        f'<span class="trip-chip">{escape(party)}</span>'
        f'<span class="trip-chip">{escape(purpose)}</span></div>',
        unsafe_allow_html=True,
    )
    try:
        messages = api("GET", f"/trips/{trip['id']}/messages", headers=auth_headers())
    except ApiError as error:
        st.error(str(error))
        return
    try:
        # 변경 기록은 assistant 메시지로 저장하지 않고, 생성 시각만 기준으로 채팅
        # 메시지 사이에 카드 형태로 섞는다. 그래서 Gemini 토큰을 쓰지 않는다.
        changes = api(
            "GET",
            f"/trips/{trip['id']}/itinerary-changes",
            headers=auth_headers(),
        )
    except ApiError:
        # SQL 마이그레이션 전에도 기존 대화는 정상적으로 열리게 한다.
        changes = []

    timeline: list[tuple[str, int, str, dict]] = []
    for index, message in enumerate(messages):
        if message.get("role") != "system":
            timeline.append((str(message.get("created_at") or ""), index, "message", message))
    message_count = len(timeline)
    for index, change in enumerate(changes):
        timeline.append((str(change.get("created_at") or ""), message_count + index, "change", change))
    timeline.sort(key=lambda event: (event[0], event[1]))

    chat_box = st.container(height=700, key=f"dashboard_chat_{trip['id']}")
    with chat_box:
        if not messages:
            username = str(st.session_state.user_name or "여행자")
            st.markdown(
                f'<div class="welcome-message">안녕하세요! {escape(username)}님! '
                f'{escape(destination)} {nights}박 {day_count}일 ({escape(formatted_dates(trip))}) 맞춤 코스가 준비되었습니다. 🎉<br><br>'
                '아래 추천 일정을 살펴보시고 추가하고 싶은 가보고 싶은 곳이나, 제외하고 싶은 곳이 있다면 언제든 채팅으로 알려주세요!</div>',
                unsafe_allow_html=True,
            )
        for _, _, event_type, event in timeline:
            if event_type == "change":
                render_itinerary_change_card(trip, event)
            else:
                with st.chat_message(event["role"]):
                    st.write(event["content"])
        # 장소 추천 카드는 일반 채팅 메시지 다음에 보여 주되, 선택 시점에는 지금
        # 열어 둔 DAY를 사용한다. 그래서 날짜 탭을 바꾼 뒤 추가하면 그 DAY에 저장된다.
        render_chat_place_recommendation_card(trip, selected_day)
    prompt = st.chat_input("메시지를 입력하세요", key=f"dashboard_chat_input_{trip['id']}")
    if not prompt:
        return
    if _looks_like_place_recommendation(prompt):
        st.session_state.chat_place_recommendations[str(trip["id"])] = {
            "query": _recommendation_query_from_message(prompt),
        }
    with chat_box:
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            try:
                st.write_stream(stream_answer(f"/trips/{trip['id']}/chat", {"content": prompt}, headers=auth_headers()))
            except SessionExpired:
                raise
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
    """선택 여행을 일정·지도 왼쪽과 채팅 오른쪽의 고정 화면으로 그린다."""
    dashboard = api("GET", f"/trips/{trip_id}/dashboard", headers=auth_headers())
    trip, days = dashboard["trip"], dashboard["days"]
    if not days:
        st.info("여행 기간을 정하면 DAY별 일정표가 자동으로 만들어집니다.")
        return

    with st.container(key="trip_dashboard_shell", border=False):
        left, right = st.columns([1.4, 1], gap="large", vertical_alignment="top")
        with left:
            selected_day = _dashboard_selected_day(trip, days)
            try:
                route_plan = api(
                    "GET",
                    f"/trips/{trip['id']}/days/{selected_day['id']}/route-plan",
                    headers=auth_headers(),
                    timeout=90,
                )
            except ApiError as error:
                route_plan = {"markers": [], "legs": [], "route_segments": [], "route_error": str(error)}

            try:
                selected_date = date.fromisoformat(str(selected_day["travel_date"]))
                date_label = f"{selected_date.month}.{selected_date.day} ({'월화수목금토일'[selected_date.weekday()]})"
            except (KeyError, TypeError, ValueError):
                date_label = f"DAY {selected_day.get('day_number', '')}"
            weather = route_plan.get("weather") or {"label": "예보 확인 안 됨"}
            weather_text = str(weather.get("label") or "예보 확인 안 됨")
            if weather.get("status") == "ok" and weather.get("min_celsius") is not None:
                weather_text += f" {float(weather['min_celsius']):.0f}–{float(weather['max_celsius']):.0f}℃"
                if weather.get("precipitation_percent") is not None:
                    weather_text += f" · 비 {float(weather['precipitation_percent']):.0f}%"
            st.markdown(
                f'<div class="dashboard-date-summary"><div class="dashboard-date-title">{escape(date_label)}</div>'
                '<div class="dashboard-badges">'
                f'<span class="dashboard-badge">날씨 {escape(weather_text)}</span>'
                f'<span class="dashboard-badge">여행 강도 {int(trip.get("travel_intensity") or 3)}/5</span>'
                f'<span class="dashboard-badge">여행 경비 {int(trip.get("budget_level") or 3)}/5</span>'
                '</div></div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="dashboard-section-label">오늘의 일정</div>', unsafe_allow_html=True)
            render_compact_schedule(trip, selected_day, route_plan)
            st.markdown('<div class="dashboard-section-label">동선 지도</div>', unsafe_allow_html=True)
            if route_plan.get("markers"):
                render_interactive_google_map(
                    route_plan,
                    height=280,
                    missing_key_message="frontend의 GOOGLE_MAPS_API_KEY를 설정하면 지도가 표시됩니다.",
                )
            else:
                st.info(route_plan.get("route_error") or "지도에 표시할 장소 좌표가 없습니다.")

            total_seconds = float(route_plan.get("total_duration_seconds") or 0)
            total_distance = float(route_plan.get("total_distance_meters") or 0) / 1000
            unknown = int(route_plan.get("unknown_leg_count") or 0)
            summary_mode = "자동 선택"
            if unknown:
                summary_mode += f" · {unknown}구간 확인 안 됨"
            st.markdown(
                '<div class="route-summary">'
                f'<div><span>총 이동</span><b>{escape(_route_duration_text(total_seconds)) if total_seconds else "0분"}</b></div>'
                f'<div><span>거리</span><b>{total_distance:.1f}km</b></div>'
                f'<div><span>수단</span><b>{escape(summary_mode)}</b></div>'
                '</div>',
                unsafe_allow_html=True,
            )
        with right:
            render_dashboard_chat(trip, days, selected_day)

def render_signed_in() -> None:
    """현재 사용자의 여행을 불러오고 알맞은 로그인 상태 화면을 그린다."""
    trips = api("GET", "/me/trips", headers=auth_headers())
    if trips and st.session_state.selected_trip_id not in {trip["id"] for trip in trips}:
        st.session_state.selected_trip_id = trips[0]["id"]
        request_main_scroll_to_top()

    render_sidebar(trips)

    if st.session_state.show_create_trip:
        st.markdown('<div class="brand">여행 추가</div>', unsafe_allow_html=True)
        st.caption("여행 기간을 정하면 DAY별 AI 일정 초안이 자동으로 생성됩니다.")
        render_create_trip_form("create_trip")
        return

    if not trips:
        # st.markdown('<div class="brand">새 여행 추가</div>', unsafe_allow_html=True)
        # st.caption("여행 기간을 정하면 DAY별 AI 일정 초안이 자동으로 생성됩니다.")
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
