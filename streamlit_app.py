import json
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from html import escape
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st
import streamlit.components.v1 as components

# 백엔드 TripCreate.must_visit 의 max_length=5 와 같은 값이다.
# 화면에서 먼저 막지 않으면 사용자가 6번째를 고른 뒤 여행 만들기에서 422 를 받는다 — 고르는 순간에 알려 주는 편이 낫다.
MAX_MUST_VISIT = 5

from common import (
    GOOGLE_MAPS_API_KEY,
    ApiError,
    SessionExpired,
    _load_env,
    api,
    api_binary,
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
        /* 하단 프로필은 팝오버를 열지 않아도 계정 카드처럼 보이게 한다. */
        [data-testid="stSidebar"] .st-key-sidebar-profile {
            margin-top: auto !important;
            border-top: 1px solid rgba(112, 128, 157, .28);
        }
        [data-testid="stSidebar"] .st-key-sidebar-profile [data-testid="stPopoverButton"] {
            position: relative;
            width: 100% !important;
            min-height: 3.8rem !important;
            padding: .45rem .5rem .45rem 3.35rem !important;
            border: 0 !important;
            border-radius: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
            justify-content: flex-start !important;
            text-align: left !important;
        }
        [data-testid="stSidebar"] .st-key-sidebar-profile [data-testid="stPopoverButton"]:hover,
        [data-testid="stSidebar"] .st-key-sidebar-profile [data-testid="stPopoverButton"]:focus-visible {
            background: rgba(49, 51, 63, .06) !important;
            border: 0 !important;
            box-shadow: none !important;
        }
        [data-testid="stSidebar"] .st-key-sidebar-profile [data-testid="stPopoverButton"]::before {
            content: var(--sidebar-profile-initial, "여");
            position: absolute;
            top: 50%;
            left: .5rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 2.35rem;
            height: 2.35rem;
            transform: translateY(-50%);
            border-radius: 50%;
            background: #e5edff;
            color: #3169e8;
            font-size: 1.1rem;
            font-weight: 800;
        }
        [data-testid="stSidebar"] .st-key-sidebar-profile [data-testid="stPopoverButton"] p {
            width: 100% !important;
            margin: 0 !important;
            overflow: hidden !important;
            color: inherit !important;
            font-size: .95rem !important;
            font-weight: 800 !important;
            line-height: 1.2 !important;
            text-align: left !important;
            text-overflow: ellipsis !important;
            white-space: nowrap !important;
        }
        [data-testid="stSidebar"] .st-key-sidebar-profile [data-testid="stPopoverButton"] p::after {
            content: var(--sidebar-profile-email, "");
            display: block;
            margin-top: .12rem;
            overflow: hidden;
            color: inherit;
            font-size: .78rem;
            font-weight: 500;
            line-height: 1.2;
            opacity: .62;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        /* 팝오버 기본 화살표는 카드 안에서 보이지 않게 한다. */
        [data-testid="stSidebar"] .st-key-sidebar-profile [data-testid="stPopoverButton"] > div > div:last-child {
            display: none !important;
        }
        /* 여행 이름 버튼 오른쪽에 더보기 메뉴가 들어갈 공간을 확보한다. */
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_select_"] button {
            padding-right: 3rem !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_row_"] {
            position: relative;
            min-height: 2.5rem;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_actions_"] {
            position: absolute !important;
            top: 50%;
            right: .35rem;
            z-index: 3;
            width: 2.25rem !important;
            height: 2.25rem !important;
            transform: translateY(-50%);
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_actions_"] [data-testid="stPopoverButton"] {
            width: 2.25rem !important;
            min-width: 2.25rem !important;
            height: 2.25rem !important;
            min-height: 2.25rem !important;
            padding: 0 !important;
            border: 1px solid transparent !important;
            border-radius: .65rem !important;
            background: transparent !important;
            color: #42516a !important;
            box-shadow: none !important;
            justify-content: center !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_actions_"] [data-testid="stPopoverButton"]:hover {
            background: rgba(49, 51, 63, .06) !important;
            border-color: transparent !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_actions_"] [data-testid="stPopoverButton"] p {
            margin: 0 !important;
            color: inherit !important;
            font-size: 1.15rem !important;
            font-weight: 800 !important;
            line-height: 1 !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_actions_"] [data-testid="stPopoverButton"] > div > div:last-child {
            display: none !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_action_title_"] {
            padding: .15rem .25rem .55rem;
            color: #9aa7ba;
            font-size: .82rem;
            font-weight: 700;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_rename_"] button,
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_delete_"] button {
            justify-content: flex-start !important;
            border-color: transparent !important;
            box-shadow: none !important;
            font-weight: 750 !important;
            text-align: left !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_delete_"] button {
            color: #c53b35 !important;
            background: #fff2f1 !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_delete_"] button:hover {
            background: #ffe5e3 !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_title_edit_"] {
            margin-right: 3rem !important;
        }
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_title_edit_"] input {
            height: 2.5rem !important;
            min-height: 2.5rem !important;
            padding: .35rem .65rem !important;
            border: 1px solid #b8c9e5 !important;
            border-radius: .55rem !important;
            font-weight: 700 !important;
        }
        /* 이름을 입력하는 동안에는 고정 아이콘을 잠시 숨긴다. */
        [data-testid="stSidebar"] [class*="st-key-sidebar_trip_row_"]:has([class*="st-key-sidebar_trip_title_edit_"]) [class*="st-key-sidebar_trip_pin_"] {
            display: none !important;
        }
        /* 프로필 팝오버의 버튼 아래에 표시하는 보조 설명이다. */
        .profile-popover-meta {
            margin: -.75rem 0 .45rem 2.35rem;
            color: #a2aec2;
            font-size: .78rem;
            font-weight: 700;
            line-height: 1.15;
        }
        [class*="st-key-profile_popover_sign_out"] button {
            color: #c53b35 !important;
            background: transparent !important;
            border-color: transparent !important;
            box-shadow: none !important;
            font-weight: 800 !important;
        }
        [class*="st-key-profile_popover_sign_out"] button:hover {
            background: #fff2f1 !important;
            border-color: transparent !important;
        }
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
        [data-testid="stSidebar"] [data-testid="stLayoutWrapper"]:has(> .st-key-admin-sidebar-profile) {
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
            height: 100% !important;
            min-height: calc(100dvh - 2rem) !important;
        }
        [data-testid="stSidebar"] .st-key-sidebar-profile { margin-top: auto !important; }
        [data-testid="stSidebar"] .st-key-admin-sidebar-profile { margin-top: auto !important; }
        [data-testid="stSidebar"] .st-key-admin-sidebar-footer { margin-top: auto !important; }
        [data-testid="stSidebar"] .st-key-admin-console-sidebar-footer { margin-top: auto !important; }
        /* 운영 콘솔의 하단 전환 버튼과 프로필은 피그마처럼 항상 사이드바
           아래에 고정한다. 본문이 길어져도 이 영역이 위로 밀리지 않는다. */
        [data-testid="stSidebar"] .st-key-admin-sidebar-footer,
        [data-testid="stSidebar"] .st-key-admin-console-sidebar-footer {
            position: fixed !important;
            left: .75rem;
            bottom: .7rem;
            width: calc(280px - 1.5rem);
            z-index: 10;
        }
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
        .admin-access-denied { padding: 3rem 2rem; border: 1px solid #eadff8; border-radius: 20px; background: linear-gradient(135deg, #fbf8ff, #ffffff); text-align: center; }
        .admin-access-denied h1 { margin-bottom: .6rem; color: #432a77; }
        .admin-access-denied p { color: #726987; }
        .admin-kpi-card { padding: .75rem .85rem; border: 1px solid #e7def5; border-radius: 12px; background: #fff; }
        .admin-panel-title { margin: .25rem 0 .65rem; color: #3c2b58; font-size: 1rem; font-weight: 800; }
        .admin-console-brand { margin: .7rem 0 1.05rem; color: #fff; font-size: 1.05rem; font-weight: 800; }
        .admin-console-brand small { display: block; margin-top: .22rem; color: #b9aee1; font-size: .68rem; font-weight: 600; }
        .admin-console-description { margin-top: 1rem; padding: .85rem .8rem; border-radius: .7rem; background: rgba(255,255,255,.08); color: #c5bde0; font-size: .72rem; line-height: 1.55; }
        .admin-console-description strong { display: block; margin-bottom: .35rem; color: #f0ebff; font-size: .76rem; }
        [data-testid="stSidebar"] [class*="st-key-admin-nav-"] button { border-radius: .45rem !important; text-align: left !important; }
        [data-testid="stMain"] [class*="st-key-admin-tab-"] button {
            border-radius: 0 !important;
            border-width: 0 0 2px 0 !important;
            background: transparent !important;
            color: #766e88 !important;
            font-weight: 700 !important;
        }
        [data-testid="stMain"] [class*="st-key-admin-tab-"] button:hover {
            border-bottom-color: #7a4bd8 !important;
            color: #4a2b83 !important;
        }
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
          gap: 10px !important;
          row-gap: 5px !important;
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
        .dashboard-badge { padding:.22rem .55rem; border-radius:999px; background:#edf3ff; color:#315fca; font-size:.9rem; font-weight:700; white-space:nowrap; }
        /* 일정 한 줄 전체를 하나의 카드로 감싼다. 정보·삭제 버튼도 카드 안쪽에
           두고, 오른쪽 끝과 버튼 사이에는 20px의 여백을 남긴다. */
        .st-key-trip_dashboard_shell [class*="st-key-dashboard_item_row_"] {
          padding: 0 10px 0 0 !important;
          margin: .15rem 0 !important;
          border: 1px solid #dfe6f2;
          border-radius: 12px;
          background: var(--secondary-background-color);
          overflow: hidden;
        }
        /* 일정 내용은 시간 20%와 장소명 80%로 한 줄을 나눈다. 장소의 평점·체류
           정보는 우측 정보 버튼에서 확인하므로 이 카드에서는 중복해 표시하지 않는다. */
        .compact-item {
          display:grid;
          grid-template-columns:20% minmax(0, 1fr);
          height:80px;
          min-height:80px;
          border:0;
          background:transparent;
        }
        .compact-item-time {
          display:flex;
          align-items:center;
          justify-content:center;
          height:100%;
          box-sizing:border-box;
          padding:.0rem;
          background:#e5f2ff;
          color:#3169e8;
          font-size:1.0rem;
          font-weight:700;
          text-align:center;
          line-height:1;
        }
        .compact-item-title {
          display:flex;
          align-items:center;
          min-width:0;
          height:100%;
          box-sizing:border-box;
          padding:.0rem .8rem;
          overflow:hidden;
          text-overflow:ellipsis;
          white-space:nowrap;
          font-size:1.0rem;
          font-weight:700;
          line-height:1;
        }
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
        /* 카드 사이 이동 안내는 독립된 높이 안에서 세로 중앙에 정렬한다. 양쪽
           카드의 동일한 margin까지 포함하면, 안내 문구가 두 카드 간격 정중앙에 놓인다. */
        .route-leg {
          display:flex;
          align-items:center;
          box-sizing:border-box;
          height:1.6rem;
          margin:0;
          padding-left:1rem;
          color:#687790;
          font-size:.85rem;
          font-weight:650;
          transform: translateY(-8px);
        }
        .route-leg::before { content:"↓"; margin-right:.35rem; color:#4d78e5;}
        .dashboard-section-label { margin:.35rem 0 .25rem; font-size:.8rem; font-weight:800; }
        .route-summary { display:grid; grid-template-columns:1fr 1fr 1fr; gap:.5rem; padding:.6rem .75rem; border:1px solid #e1e7f0; border-radius:12px; }
        .route-summary span { display:block; color:#748198; font-size:.65rem; }
        .route-summary b { font-size:.82rem; }
        .trip-chat-title { margin:0; font-size:1.7rem; font-weight:850; }
        .trip-chip-row { display:flex; flex-wrap:wrap; gap:.35rem; margin:.55rem 0 .7rem; }
        .trip-chip { padding:.25rem .55rem; border-radius:999px; background:#eef3ff; color:#315fca; font-size:.9rem; font-weight:700; }
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
        "is_dashboard_admin": None,
        "current_view": "trip",
        # DB의 profiles.mate_type을 처음 읽기 전까지는 None으로 둔다. 그래야
        # 이전에 저장한 Mate 설정을 기본값으로 덮어쓰지 않는다.
        "mate_type": None,
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
        # 채팅으로 말한 숙소 후보만 현재 화면에 잠시 보관한다. 확정한 숙소는
        # 백엔드 trips.accommodation_place_id에 실제 Google 장소로 저장한다.
        "chat_accommodation_candidates": {},
        # 여행별로 선택한 DAY와 4개씩 보이는 날짜 창의 시작 위치를 유지한다.
        "dashboard_selected_days": {},
        "dashboard_day_windows": {},
        # [변경 사유] 여행 만들기 화면에서 고른 여행지와 '가고 싶은 장소'다.
        # 여행이 아직 없어 백엔드에 저장할 곳이 없으므로, POST /me/trips 에
        # 실을 때까지만 화면이 들고 있는다.
        # [변경 사유] 검색 결과를 None(아직 검색 안 함)과 [](결과 없음)로
        # 구분한다. 둘을 같은 []로 두면 화면을 열자마자 "찾지 못했어요"가 뜬다.
        "create_trip_destination": None,
        "create_trip_destination_results": None,
        "create_trip_must_visit": [],
        "create_trip_place_results": None,
        # 사이드바 여행 이름 수정·삭제 팝오버의 임시 UI 상태다.
        "sidebar_trip_editing_id": None,
        "sidebar_trip_pending_delete_id": None,
        "sidebar_trip_title_error": None,
        # [변경 사유] 일정표 다운로드 모달의 상태다. st.dialog 안은 위젯을 누를
        # 때마다 스크립트가 재실행되므로, 이미 받은 그림을 다시 받지 않도록
        # (trip_id, style) 로 캐시한다. 캐시하지 않으면 스타일 카드를 눌러 보는
        # 것만으로 20~40초짜리 이미지 생성이 다시 돌아간다.
        "export_dialog_trip_id": None,
        "export_style": "simple",
        "export_images": {},
        # [변경 사유] 모달이 뜨자마자 그리지 않는다. 이미지 생성은 20~40초가
        # 걸리고 요금도 나가는데, 사용자가 스타일을 고르기도 전에 시작하면
        # 고르는 동안 이미 다른 스타일을 그리고 있는 셈이 된다. 카드를 누른
        # 뒤에만 그리도록, 사용자가 실제로 고른 스타일을 여기에 담는다.
        "export_requested_style": None,
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
    st.session_state.mate_type = None
    request_main_scroll_to_top()


def sign_out(notice: str | None = None) -> None:
    """현재 계정 상태를 비우고 필요하면 안내 문구를 남긴 뒤 다시 실행한다."""
    st.session_state.access_token = None
    st.session_state.user_email = None
    st.session_state.user_name = None
    st.session_state.is_dashboard_admin = None
    st.session_state.current_view = "trip"
    st.session_state.mate_type = None
    st.session_state.selected_trip_id = None
    st.session_state.show_create_trip = False
    st.session_state.place_search_results = {}
    st.session_state.visible_day_maps = {}
    st.session_state.chat_place_recommendations = {}
    st.session_state.chat_accommodation_candidates = {}
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


MATE_TYPE_LABELS = {
    "assistant": "비서",
    "guide": "가이드",
    "senior": "어르신",
}


def sidebar_profile() -> tuple[str, str, str]:
    """사이드바 계정 카드에 쓸 이름·이메일·저장된 Mate 방식을 반환한다."""

    email = st.session_state.user_email or ""
    cached_name = st.session_state.user_name
    cached_mate_type = st.session_state.mate_type
    if cached_name and cached_mate_type:
        return cached_name, email, cached_mate_type

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
    mate_type = str(profile.get("mate_type") or "assistant")
    if mate_type not in MATE_TYPE_LABELS:
        mate_type = "assistant"

    st.session_state.user_name = display_name
    st.session_state.is_dashboard_admin = bool(result.get("is_dashboard_admin"))
    st.session_state.mate_type = mate_type
    return display_name, email,mate_type

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
                    st.session_state.mate_type = None
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
                st.session_state.pop(f"{form_key}_{field}", None)        # [변경 사유] 위 for 문은 위젯 키(create_trip_title 등)만 지운다.
        # 고른 여행지와 장소는 위젯이 아니라 우리가 만든 세션 값이라 따로 지워야
        # 한다. 안 지우면 이전에 만들다 만 여행의 선택이 새 양식에 남는다.
    st.session_state.create_trip_destination = None
    st.session_state.create_trip_destination_results = None
    st.session_state.create_trip_must_visit = []
    st.session_state.create_trip_place_results = None
    st.session_state.show_create_trip = True


def _city_name(city: dict) -> str:
    """화면에 보여 줄 도시 이름 한 개.

    [변경 사유] 백엔드가 label("도쿄")과 destination("도쿄도, 일본")을 나눠 준다.
    보내는 값은 Google 표기여야 생성 단계에서 도시를 다시 찾을 수 있고, 읽는 값은
    사람이 쓰는 이름이어야 고르기 쉽다. label 이 없는 응답도 그대로 동작하도록
    Google 이름으로 물러선다.
    """
    return str(city.get("label") or city.get("display_name") or "").strip()


def _city_caption(city: dict) -> str:
    """도시 이름에 나라를 붙인 한 줄. 같은 이름의 도시를 나라로 가른다."""
    name = _city_name(city)
    country = str(city.get("country") or "").strip()
    return f"{name}, {country}" if country else name


def render_destination_picker(form_key: str) -> None:
    """여행지를 검색해서 고르게 한다.

    [변경 사유] st.form 밖에 둔다. 양식 안의 위젯은 제출 전까지 재실행을
    일으키지 않아 검색 결과를 그릴 수 없고, 양식은 제출 버튼도 하나만 허용한다.

    [변경 사유] 자유 입력을 받지 않는다. 백엔드는 도시 범위를 하나로 좁히지
    못하면 여행 생성을 거절하는데, 그 판정이 Gemini 호출 뒤에 일어난다.
    여기서 확인된 도시만 고르게 하면 생성 시간을 다 기다린 뒤 422 를 받는 일이 없다.
    """

    picked = st.session_state.create_trip_destination
    if picked:
        chip_column, clear_column = st.columns([4, 1])
        with chip_column:
            st.success(f"여행지 · {_city_caption(picked)}")
        with clear_column:
            if st.button("변경", key=f"{form_key}_destination_clear", use_container_width=True):
                st.session_state.create_trip_destination = None
                st.session_state.create_trip_destination_results = None
                # [변경 사유] 여행지를 바꾸면 그 지역에서 고른 장소는 뜻을 잃는다.
                # 남겨 두면 도쿄 여행에 오사카 장소가 딸려 가고, 백엔드는 도시
                # 밖 장소를 거절하므로 사용자는 이유 없이 빠진 일정을 보게 된다.
                st.session_state.create_trip_must_visit = []
                st.session_state.create_trip_place_results = None
                st.rerun()
        return

    search_column, button_column = st.columns([4, 1])
    with search_column:
        query = st.text_input(
            "여행지",
            placeholder="예: 도쿄",
            key=f"{form_key}_destination_query",
            label_visibility="collapsed",
        )
    with button_column:
        searched = st.button(
            "검색", key=f"{form_key}_destination_search", use_container_width=True
        )

    if searched:
        # [변경 사유] 서버도 min_length=2 다. 여기서 먼저 막아 한 글자마다
        # 유료 Places 호출이 나가지 않게 한다.
        if len(query.strip()) < 2:
            st.warning("도시 이름을 두 글자 이상 입력하세요.")
        else:
            try:
                with st.spinner("도시를 찾고 있어요..."):
                    found = api(
                        "GET",
                        "/destinations/search",
                        params={"query": query.strip()},
                        headers=auth_headers(),
                    )
            except ApiError as error:
                st.error(str(error))
            else:
                st.session_state.create_trip_destination_results = found.get("destinations") or []
                st.rerun()

    results = st.session_state.create_trip_destination_results
    if results is None:
        return
    if not results:
        st.info("도시를 찾지 못했어요. 나라나 넓은 지역 대신 도시 이름을 입력해 보세요.")
        return

    st.caption("여행할 도시를 고르세요. 한 곳만 선택할 수 있어요.")
    for city in results:
        # [변경 사유] 보여 주는 것은 label 이고 보내는 것은 destination 이다.
        # 나라를 함께 붙이는 이유는 같은 이름의 도시가 여러 나라에 있을 때
        # 무엇을 고르는지 알 수 없기 때문이다.
        if st.button(
            _city_caption(city),
            key=f"{form_key}_destination_pick_{city['google_place_id']}",
            use_container_width=True,
        ):
            st.session_state.create_trip_destination = city
            st.session_state.create_trip_destination_results = None
            st.rerun()


def render_must_visit_picker(form_key: str) -> None:
    """고른 여행지 안에서만 '가고 싶은 장소'를 찾아 최대 5곳까지 담는다.

    [변경 사유] 여행지를 고르기 전에는 검색창을 잠근다. 지역 없이 '스타벅스'를
    찾으면 전 세계 결과가 나오고, 그중 무엇을 담아도 이 여행의 일정에 쓸 수 없다.
    백엔드도 destination 을 필수로 받지만, 화면에서 막아야 이유를 설명할 수 있다.

    [변경 사유] 검색은 선택 사항이다. 아무것도 담지 않아도 여행은 만들어진다 —
    여기서 막으면 장소를 아직 모르는 사용자가 여행을 시작할 수 없다.
    """

    picked_city = st.session_state.create_trip_destination
    if not picked_city:
        st.caption("여행지를 먼저 고르면 그 지역에서 찾아드려요.")
        return

    chosen = st.session_state.create_trip_must_visit
    if len(chosen) >= MAX_MUST_VISIT:
        st.caption(f"가고 싶은 장소는 {MAX_MUST_VISIT}곳까지 담을 수 있어요.")
    else:
        search_column, button_column = st.columns([4, 1])
        with search_column:
            query = st.text_input(
                "가고 싶은 장소",
                placeholder=f"{_city_name(picked_city)}에서 가고 싶은 곳",
                key=f"{form_key}_must_visit_query",
                label_visibility="collapsed",
            )
        with button_column:
            searched = st.button(
                "검색", key=f"{form_key}_must_visit_search", use_container_width=True
            )
        if searched:
            if not query.strip():
                st.warning("찾고 싶은 장소 이름을 입력하세요.")
            else:
                try:
                    with st.spinner("Google Places에서 장소를 찾고 있어요..."):
                        found = api(
                            "GET",
                            "/destinations/places/search",
                            params={
                                # [변경 사유] 검색 화면이 만든 문자열을 그대로 보낸다.
                                # 화면이 이름과 나라를 다시 조합하면 백엔드가 도시를
                                # 다시 못 찾을 수 있다.
                                "destination": picked_city["destination"],
                                "query": query.strip(),
                                "max_results": 5,
                            },
                            headers=auth_headers(),
                        )
                except ApiError as error:
                    st.error(str(error))
                else:
                    st.session_state.create_trip_place_results = found.get("places") or []
                    st.rerun()

    results = st.session_state.create_trip_place_results
    if results is not None and not results:
        st.caption("찾지 못했어요. 장소는 여행을 만든 뒤 대화에서 말해 주셔도 돼요.")

    picked_ids = {place["google_place_id"] for place in chosen}
    for place in results or []:
        place_id = str(place.get("google_place_id") or "").strip()
        if not place_id or place_id in picked_ids:
            continue
        with st.container(border=True):
            # [변경 사유] 이름만 쓰면 '스타벅스' 다섯 줄이 나란히 서서 어느
            # 지점인지 알 수 없다. 백엔드가 주소와 평점을 이미 주고 있다.
            st.markdown(f"**{escape(str(place.get('display_name') or '이름 없는 장소'))}**")
            st.caption(
                f"{place.get('formatted_address') or '주소 정보 없음'} · {_place_rating_text(place)}"
            )
            if len(chosen) < MAX_MUST_VISIT and st.button(
                "담기", key=f"{form_key}_must_visit_add_{place_id}", use_container_width=True
            ):
                # [변경 사유] google_place_id 를 함께 담는다. 이름만 보내면
                # 같은 이름의 다른 지점이 잡힐 수 있다.
                chosen.append({
                    "name": place.get("display_name") or "",
                    "google_place_id": place_id,
                })
                st.session_state.create_trip_place_results = None
                st.rerun()

    for index, place in enumerate(chosen):
        name_column, drop_column = st.columns([4, 1])
        with name_column:
            st.markdown(f"· {escape(str(place['name']))}")
        with drop_column:
            if st.button(
                "빼기", key=f"{form_key}_must_visit_drop_{index}", use_container_width=True
            ):
                st.session_state.create_trip_must_visit = [
                    item for position, item in enumerate(chosen) if position != index
                ]
                st.rerun()

def render_create_trip_form(form_key: str) -> None:
    """여행과 첫 AI 일정 초안을 만드는 양식을 그리고 제출한다."""
    # [변경 사유] 검색은 st.form 밖에서만 동작한다. 양식 안의 위젯은 제출 전까지
    # 재실행을 일으키지 않아 검색 결과를 그릴 수 없고, 양식은 제출 버튼도 하나만
    # 허용한다. 순서도 의미가 있다 — 장소 검색은 여행지가 정해져야 열린다.
    st.markdown("##### 어디로 가시나요")
    render_destination_picker(form_key)
    st.markdown("##### 가고 싶은 장소 (선택)")
    render_must_visit_picker(form_key)
    st.divider()

    # 제출 직후에는 입력을 초기화하지 않고 API 완료 후에만 대시보드로 이동한다.
    with st.form(form_key, clear_on_submit=False):
        title = st.text_input(
            "여행 이름", placeholder="예: 봄날의 도쿄 여행", key=f"{form_key}_title"
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
    # [변경 사유] destination 변수가 없어졌다. 고른 도시는 세션에 있다.
    picked_city = st.session_state.create_trip_destination
    if not title.strip() or not picked_city:
        st.error("여행 이름을 입력하고 여행지를 골라 주세요.")
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
                    # [변경 사유] 검색 결과가 준 문자열을 그대로 보낸다.
                    # 백엔드가 이 표기로 도시를 다시 찾으므로 화면에서 가공하지 않는다.
                    "destination": picked_city["destination"],
                    # 현지 시간대는 백엔드가 여행지를 기준으로 결정한다.
                    "start_date": selected_dates[0].isoformat(),
                    "end_date": selected_dates[1].isoformat(),
                    "travel_party": travel_party,
                    "travel_intensity": travel_intensity,
                    "budget_level": budget_level,
                    # [변경 사유] 비어 있어도 그대로 보낸다. 백엔드는
                    # default_factory=list 라 빈 배열을 정상으로 받는다.
                    "must_visit": st.session_state.create_trip_must_visit,
                },
                headers=auth_headers(),
            )
    except ApiError as error:
        st.error(str(error))
        return

    st.session_state.selected_trip_id = created["trip"]["id"]
    st.session_state.show_create_trip = False
    # [변경 사유] 위젯이 아닌 세션 값이라 show_create_trip 을 내려도 남는다.
    # 안 지우면 다음에 여행을 만들 때 지난번 선택이 그대로 보인다.
    st.session_state.create_trip_destination = None
    st.session_state.create_trip_destination_results = None
    st.session_state.create_trip_must_visit = []
    st.session_state.create_trip_place_results = None
    request_main_scroll_to_top()
    count = int(created.get("initial_itinerary_count") or 0)
    st.success(f"새 여행과 식사·활동·휴식을 포함한 일정 {count}개를 만들었어요.")
    st.rerun()

def save_sidebar_trip_title(trip_id: str, title_key: str) -> None:
    """입력창에서 확정한 여행 이름을 백엔드에 저장한다."""

    title = str(st.session_state.get(title_key) or "").strip()
    if not title:
        st.session_state.sidebar_trip_title_error = "여행 이름을 입력하세요."
        return

    try:
        api(
            "PATCH",
            f"/trips/{trip_id}",
            json={"title": title},
            headers=auth_headers(),
        )
    except SessionExpired:
        raise
    except ApiError as error:
        st.session_state.sidebar_trip_title_error = str(error)
        return

    st.session_state.sidebar_trip_editing_id = None
    st.session_state.pop(title_key, None)
    st.session_state.pop("sidebar_trip_title_error", None)


def render_sidebar_trip(trip: dict) -> None:
    """여행 이름·고정·더보기 동작을 한 줄에 배치한다."""

    trip_id = str(trip["id"])
    title = str(trip.get("title") or "이름 없는 여행")
    is_pinned = trip.get("pinned_order") is not None
    active = trip_id == str(st.session_state.get("selected_trip_id") or "")
    requested_pinned = is_pinned
    title_key = f"sidebar_trip_title_edit_{trip_id}"
    editing = str(st.session_state.get("sidebar_trip_editing_id") or "") == trip_id

    with st.container(key=f"sidebar_trip_row_{trip_id}", border=False):
        if editing:
            st.session_state.setdefault(title_key, title)
            st.text_input(
                "여행 이름",
                key=title_key,
                max_chars=100,
                label_visibility="collapsed",
                on_change=save_sidebar_trip_title,
                args=(trip_id, title_key),
            )
            if st.session_state.get("sidebar_trip_title_error"):
                st.caption(st.session_state.sidebar_trip_title_error)
        elif st.button(
            title,
            key=f"sidebar_trip_select_{trip_id}",
            use_container_width=True,
            type="primary" if active else "secondary",
        ):
            st.session_state.selected_trip_id = trip["id"]
            st.session_state.show_create_trip = False
            request_main_scroll_to_top()
            st.rerun()

        with st.popover(
            "⋯",
            key=f"sidebar_trip_actions_{trip_id}",
            use_container_width=True,
        ):
            with st.container(
                key=f"sidebar_trip_action_title_{trip_id}",
                border=False,
            ):
                st.markdown(escape(title), unsafe_allow_html=True)

            if st.button(
                "✎ 이름 바꾸기",
                key=f"sidebar_trip_rename_{trip_id}",
                use_container_width=True,
            ):
                st.session_state.sidebar_trip_editing_id = trip_id
                st.session_state[title_key] = title
                st.session_state.pop("sidebar_trip_title_error", None)
                st.rerun()

            if st.button(
                "🗑 여행 삭제",
                key=f"sidebar_trip_delete_{trip_id}",
                use_container_width=True,
            ):
                st.session_state.sidebar_trip_pending_delete_id = trip_id
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

def render_admin_sidebar_profile(display_name: str, email: str) -> None:
    """Render the compact profile menu used in the admin dashboard view."""

    initial = escape(display_name[:1].upper() or "?")
    safe_name = escape(display_name)
    safe_email = escape(email)
    with st.container(key="admin-sidebar-profile", border=False):
        with st.popover(
            f"{display_name} · 내 프로필",
            key="admin_sidebar_profile_popover",
            use_container_width=True,
        ):
            st.caption("내 프로필")
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
                st.caption("관리자")

            st.button(
                "⚙ 설정 (준비 중)",
                key="admin_profile_settings_placeholder",
                use_container_width=True,
                disabled=True,
            )


def render_admin_console_navigation(current_view: str) -> None:
    """피그마 운영 콘솔의 왼쪽 대시보드·사용자 관리 메뉴를 렌더링한다."""

    console_views = {"admin_console", "admin_feedback", "admin_system"}

    st.markdown(
        '<div class="admin-console-brand">운영 콘솔<small>TripMate Admin</small></div>',
        unsafe_allow_html=True,
    )
    if st.button(
        "▦  대시보드",
        use_container_width=True,
        type="primary" if current_view == "admin_dashboard" else "secondary",
        key="admin-nav-dashboard",
    ) and current_view != "admin_dashboard":
        st.session_state.current_view = "admin_dashboard"
        request_main_scroll_to_top()
        st.rerun()
    if st.button(
        "♧  사용자 관리",
        use_container_width=True,
        type="primary" if current_view in console_views else "secondary",
        key="admin-nav-users",
    ) and current_view != "admin_console":
        st.session_state.current_view = "admin_console"
        request_main_scroll_to_top()
        st.rerun()
    st.markdown(
        '<div class="admin-console-description"><strong>절대 규칙</strong>'
        '대시보드는 어떤 권한으로도 열람할 수 없습니다. 이 콘솔은 집계와 메타데이터만 다룹니다.</div>',
        unsafe_allow_html=True,
    )


def render_admin_console_tabs(current_view: str) -> None:
    """피그마 ADM-002·003·004의 본문 상단 가로 탭을 렌더링한다."""

    tab_specs = [
        ("ADM-002 사용자 관리", "admin_console", "admin-tab-users"),
        ("ADM-003 피드백·페이스", "admin_feedback", "admin-tab-feedback"),
        ("ADM-004 시스템 상태", "admin_system", "admin-tab-system"),
    ]
    st.markdown(
        '<div class="admin-console-breadcrumb">운영 콘솔&nbsp;&nbsp;›&nbsp;&nbsp;'
        '사용자 관리 · 피드백·페이스 · 시스템 상태</div>',
        unsafe_allow_html=True,
    )
    tab_columns = st.columns(3, gap="small")
    for column, (label, target_view, key) in zip(tab_columns, tab_specs):
        with column:
            if st.button(
                label,
                use_container_width=True,
                type="primary" if current_view == target_view else "secondary",
                key=key,
            ) and current_view != target_view:
                st.session_state.current_view = target_view
                request_main_scroll_to_top()
                st.rerun()


def render_admin_dashboard_filters() -> None:
    """피그마처럼 대시보드 본문 상단에 조회 조건을 배치한다."""

    start_column, end_column, refresh_column = st.columns([1, 1, .35], gap="small")
    with start_column:
        st.date_input("조회 시작일", value=date.today(), key="admin_dashboard_start_date")
    with end_column:
        st.date_input("조회 종료일", value=date.today(), key="admin_dashboard_end_date")
    with refresh_column:
        st.markdown("<div style='height:1.72rem'></div>", unsafe_allow_html=True)
        if st.button("↻", use_container_width=True, key="admin_dashboard_refresh"):
            st.rerun()

@st.dialog("Mate 설정")
def render_mate_settings_dialog(display_name: str, email: str, mate_type: str) -> None:
    """사이드바 계정 팝오버에서 여는 내 정보·AI 대화 방식 설정 모달이다.

    이메일은 Supabase Auth의 로그인 식별자라 여기서 바꾸지 않는다. 표시 이름과
    Mate 방식은 profiles 테이블에 저장하며, 여행이 하나도 없어도 사용할 수 있다.
    """

    st.caption("TripMate에서 표시할 이름과 AI 대화 방식을 관리합니다.")
    st.text_input("이메일", disabled=True, key="mate_settings_email")
    username = st.text_input(
        "Mate 이름",
        max_chars=30,
        key="mate_settings_username",
        help="여행 목록과 사이드바에 표시되는 이름입니다.",
    )
    selected_mate_type = st.radio(
        "Mate 방식",
        options=list(MATE_TYPE_LABELS),
        format_func=lambda value: MATE_TYPE_LABELS[value],
        horizontal=True,
        key="mate_settings_type",
        help="비서는 핵심 위주, 가이드는 설명과 제안 위주, 어르신 Mate는 쉬운 순서 설명 위주로 답합니다.",
    )
    st.caption("이메일과 비밀번호는 로그인 정보이므로 이 화면에서 변경하지 않습니다.")

    save_column, cancel_column = st.columns(2)
    if save_column.button("저장", type="primary", width="stretch", key="save_mate_settings"):
        cleaned_name = username.strip()
        if not cleaned_name:
            st.error("Mate 이름을 입력하세요.")
            return
        try:
            updated = api(
                "PATCH",
                "/me/profile",
                json={"username": cleaned_name, "mate_type": selected_mate_type},
                headers=auth_headers(),
            )
        except SessionExpired:
            raise
        except ApiError as error:
            st.error(str(error))
            return
        st.session_state.user_name = str(updated.get("username") or cleaned_name)
        st.session_state.mate_type = str(updated.get("mate_type") or selected_mate_type)
        st.rerun()
    if cancel_column.button("취소", width="stretch", key="cancel_mate_settings"):
        st.rerun()


@st.dialog("계정 관리")
def render_account_management_dialog(display_name: str, email: str) -> None:
    """로그인 계정 정보 확인과 현재 비밀번호 기반 비밀번호 변경 모달을 그린다."""

    st.caption("로그인 정보와 비밀번호를 관리합니다.")
    st.markdown(f"#### {escape(display_name)}")
    st.text_input("이메일", disabled=True, key="account_settings_email")
    st.caption("이메일은 Supabase Auth의 로그인 식별자이므로 이 화면에서 변경하지 않습니다.")

    st.divider()
    st.subheader("비밀번호 변경")
    st.caption("현재 비밀번호를 확인한 뒤, 6자 이상인 새 비밀번호로 변경합니다.")
    with st.form("account_password_change_form", clear_on_submit=True):
        current_password = st.text_input("현재 비밀번호", type="password")
        new_password = st.text_input("새 비밀번호", type="password")
        confirm_password = st.text_input("새 비밀번호 확인", type="password")
        submitted = st.form_submit_button("비밀번호 변경", type="primary", width="stretch")

    if submitted:
        if not current_password or not new_password or not confirm_password:
            st.error("현재 비밀번호와 새 비밀번호를 모두 입력하세요.")
            return
        if new_password != confirm_password:
            st.error("새 비밀번호가 서로 다릅니다.")
            return
        try:
            result = api(
                "POST",
                "/me/password",
                json={"current_password": current_password, "new_password": new_password},
                headers=auth_headers(),
            )
        except SessionExpired:
            raise
        except ApiError as error:
            st.error(str(error))
            return
        # 새 비밀번호가 실제로 저장됐는지 다음 로그인에서 확인하도록 현재 세션은 비운다.
        sign_out(str(result.get("message") or "비밀번호가 변경되었습니다. 새 비밀번호로 로그인하세요."))

    st.divider()
    with st.expander("회원 탈퇴", expanded=False):
        st.warning("회원 탈퇴는 계정과 연결된 여행·일정·채팅을 영구 삭제할 수 있는 작업입니다.")
        st.caption("실제 탈퇴 기능은 팀의 데이터 보관 정책과 별도 확인 절차가 정해진 뒤 제공합니다.")


@st.dialog("여행 삭제")
def render_delete_trip_dialog(trip: dict) -> None:
    """여행과 연결된 일정·대화를 삭제하기 전에 확인한다."""

    trip_id = str(trip["id"])
    title = str(trip.get("title") or "이름 없는 여행")
    st.markdown("### 이 여행을 삭제할까요?")
    st.markdown(
        f"**‘{escape(title)}’**의 일정과 대화가 함께 삭제되며 되돌릴 수 없습니다."
    )

    cancel_column, delete_column = st.columns(2)
    if cancel_column.button(
        "취소",
        key=f"cancel_delete_trip_{trip_id}",
        use_container_width=True,
    ):
        st.session_state.pop("sidebar_trip_pending_delete_id", None)
        st.rerun()
    if delete_column.button(
        "🗑 삭제",
        key=f"confirm_delete_trip_{trip_id}",
        use_container_width=True,
    ):
        try:
            api(
                "DELETE",
                f"/trips/{trip_id}",
                headers=auth_headers(),
            )
        except SessionExpired:
            raise
        except ApiError as error:
            st.error(str(error))
            return

        st.session_state.pop("sidebar_trip_pending_delete_id", None)
        st.session_state.sidebar_trip_editing_id = None
        st.session_state.pop("sidebar_trip_title_error", None)
        if str(st.session_state.get("selected_trip_id") or "") == trip_id:
            st.session_state.selected_trip_id = None
        st.rerun()


def render_sidebar(trips: list[dict]) -> None:
    """여행 그룹·여행 총개수·하단 고정 프로필 팝오버를 그린다."""

    display_name, email, mate_type = sidebar_profile()
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

    open_mate_settings = False
    open_account_management = False
    with st.sidebar:
        # 하나의 flex 열을 사용해 두 번째 사이드바 스크롤 영역을 만들지 않고도
        # 프로필이 ``margin-top: auto``로 최하단에 머물 수 있게 한다.
        with st.container(key="sidebar-layout", border=False):
            current_view = st.session_state.get("current_view")
            admin_views = {"admin_dashboard", "admin_console", "admin_feedback", "admin_system"}
            is_admin_dashboard_view = current_view == "admin_dashboard"
            is_admin_console_view = current_view == "admin_console"
            is_admin_view = current_view in admin_views
            if not is_admin_view:
                # 고정된 여행과 이전 여행 모두 사용자가 저장한 여행 수에 포함된다.
                st.markdown(
                    '<div class="sidebar-brand"><span class="sidebar-brand-mark">◉</span>TripMate</div>',
                    unsafe_allow_html=True,
                )
                st.markdown("<div style='height:.85rem'></div>", unsafe_allow_html=True)
            if not is_admin_view:
                if st.button("＋ 새 여행 만들기", use_container_width=True, type="primary"):
                    open_create_trip_form()
            # st.markdown("<div class='sidebar-section-label'>나의 여행</div>", unsafe_allow_html=True)
            # CSS는 Streamlit의 초기 높이와 관계없이 이 영역만 스크롤되게 하고,
            # 하단 고정 프로필 바로 위까지 늘어나게 한다.
            if is_admin_dashboard_view and st.session_state.get("is_dashboard_admin"):
                render_admin_console_navigation("admin_dashboard")
                with st.container(key="admin-sidebar-footer", border=False):
                    if st.button("여행 화면", use_container_width=True, key="admin_dashboard_to_trip"):
                        st.session_state.current_view = "trip"
                        st.rerun()
                    render_admin_sidebar_profile(display_name, email)
                return

            if is_admin_console_view and st.session_state.get("is_dashboard_admin"):
                render_admin_console_navigation("admin_console")
                with st.container(key="admin-console-sidebar-footer", border=False):
                    if st.button("여행 화면", use_container_width=True, key="console_to_trip"):
                        st.session_state.current_view = "trip"
                        st.rerun()
                    render_admin_sidebar_profile(display_name, email)
                return

            if is_admin_view and st.session_state.get("is_dashboard_admin"):
                render_admin_console_navigation(current_view)
                with st.container(key="admin-sidebar-footer", border=False):
                    if st.button("여행 화면", use_container_width=True, key="admin_to_trip"):
                        st.session_state.current_view = "trip"
                        st.rerun()
                    render_admin_sidebar_profile(display_name, email)
                return

            if is_admin_view:
                render_admin_sidebar_profile(display_name, email)
                return

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

            if st.session_state.get("is_dashboard_admin") and not is_admin_view:
                if st.button("운영 대시보드", use_container_width=True):
                    st.session_state.current_view = "admin_dashboard"
                    st.session_state.show_create_trip = False
                    request_main_scroll_to_top()
                    st.rerun()

            with st.container(key="sidebar-profile", border=False):
                # 이름과 이메일은 팝오버를 열지 않아도 프로필 버튼에 표시한다.
                profile_initial_css = json.dumps(
                    display_name[:1].upper() or "여", ensure_ascii=False
                ).replace("</", "<\\/")
                profile_email_css = json.dumps(
                    email or "", ensure_ascii=False
                ).replace("</", "<\\/")
                st.markdown(
                    "<style>"
                    "[data-testid=\"stSidebar\"] .st-key-sidebar-profile {"
                    f"--sidebar-profile-initial: {profile_initial_css};"
                    f"--sidebar-profile-email: {profile_email_css};"
                    "}</style>",
                    unsafe_allow_html=True,
                )
                # 팝오버를 사용하면 다른 페이지로 이동하지 않고 계정 영역을 열기 전까지
                # 로그아웃 버튼을 사이드바에서 숨길 수 있다.
                with st.popover(
                    display_name,
                    key="sidebar_profile_popover",
                    use_container_width=True,
                ):
                    st.caption("내 정보")
                    avatar_column, profile_column = st.columns(
                        [0.5, 2], gap="medium"
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

                    if st.button(
                        "⚙ Mate 설정",
                        key="profile_settings_placeholder",
                        use_container_width=True,
                        #disabled = True
                    ):
                        open_mate_settings = True
                    st.markdown(
                        f'<div class="profile-popover-meta">{escape(MATE_TYPE_LABELS[mate_type])}</div>',
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "♙ 계정 관리",
                        key="profile_account_management",
                        use_container_width=True,
                    ):
                        open_account_management = True
                    if st.session_state.is_dashboard_admin == True:
                        account_role = "관리자"
                    else:
                        account_role = "회원"
                    st.markdown(
                        f'<div class="profile-popover-meta">{account_role}</div>',
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "🚪 로그아웃",
                        key="profile_popover_sign_out",
                        use_container_width=True,
                    ):
                        sign_out()

    # dialog는 sidebar 컨테이너 바깥에서 열어 본문을 덮는 모달처럼 보이게 한다.
    if open_mate_settings:
        # 이전에 모달을 열었을 때 남은 위젯 값을 새 프로필 값으로 교체한다.
        # 아직 이번 실행에서 위젯을 그리지 않았으므로 안전하게 초기화할 수 있다.
        st.session_state.mate_settings_email = email
        st.session_state.mate_settings_username = display_name
        st.session_state.mate_settings_type = mate_type
        render_mate_settings_dialog(display_name, email, mate_type)
    if open_account_management:
        # 모달을 다시 열 때 이전 이메일 입력 상태가 남지 않도록 현재 로그인 계정으로
        # 교체한다. 비밀번호 입력은 form의 clear_on_submit으로 저장하지 않는다.
        st.session_state.account_settings_email = email
        render_account_management_dialog(display_name, email)

    pending_delete_id = str(
        st.session_state.get("sidebar_trip_pending_delete_id") or ""
    )
    if pending_delete_id:
        pending_trip = next(
            (trip for trip in trips if str(trip.get("id")) == pending_delete_id),
            None,
        )
        if pending_trip:
            render_delete_trip_dialog(pending_trip)
        else:
            st.session_state.pop("sidebar_trip_pending_delete_id", None)


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


def _extended_day_time(value: datetime, travel_date: object) -> str:
    """DAY 기준 다음 날 새벽을 24시 이후 표기로 바꿔 일정 흐름을 유지한다."""

    try:
        base_date = date.fromisoformat(str(travel_date))
    except (TypeError, ValueError):
        return value.strftime("%H:%M")
    # DAY 1의 다음 날 01:30은 25:30으로 보여 주어, 시간순 정렬을 보면서
    # 자정을 넘었다는 사실을 알 수 있다. 실제 DB 시각이나 날짜는 바꾸지 않는다.
    day_offset = (value.date() - base_date).days
    hour = value.hour + (24 * max(0, day_offset))
    return f"{hour:02d}:{value.minute:02d}"


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
            # 첫 일정 앞에는 이동 구간이 없다. 그 다음부터는 Routes 결과가 아직
            # 없어도 화살표 영역을 유지해 일정 카드의 흐름이 끊겨 보이지 않게 한다.
            if index > 0:
                leg_text = _travel_leg_text(leg) or ""
                st.markdown(
                    f'<div class="route-leg">{escape(leg_text)}</div>',
                    unsafe_allow_html=True,
                )
            place = item.get("place") if isinstance(item.get("place"), dict) else {}
            time_text = (
                f"{_extended_day_time(start, day.get('travel_date'))}–"
                f"{_extended_day_time(end, day.get('travel_date'))}"
                if start and end
                else "시간 미정"
            )
            place_name = str(place.get("display_name") or item.get("title") or "일정")
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
                        f'<div class="compact-item-title">{escape(place_name)}</div></div>',
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
    for phrase in (
        "갈 건데",
        "갈건데",
        "가려고",
        "가고 싶은데",
        "가고싶은데",
        "찾아줘",
        "알려줘",
        "어때",
    ):
        query = query.replace(phrase, " ")
    return " ".join(query.split()) or message.strip()


def _looks_like_place_recommendation(message: str) -> bool:
    """장소 추천 카드가 필요한 채팅 요청인지 가볍게 판별한다."""

    return "추천" in message and bool(_recommendation_query_from_message(message))


def _normalized_place_name(value: object) -> str:
    """한글·영문 장소명 비교에서 공백·대소문자 차이를 무시한다."""

    return "".join(str(value or "").casefold().split())


def _recommendation_request_from_message(message: str, day: dict) -> dict:
    """'A 이후 B 추천'을 B의 A 주변 검색과 A 제외 규칙으로 바꾼다."""

    cleaned = _recommendation_query_from_message(message)
    anchor_text = ""
    target_text = cleaned
    for marker in ("이후에", "이후", "다음에", "근처에", "근처", "주변에", "주변"):
        if marker not in cleaned:
            continue
        before, after = cleaned.split(marker, 1)
        before, after = before.strip(" ,.?!"), after.strip(" ,.?!")
        if before and after:
            anchor_text, target_text = before, after
            break

    request: dict[str, object] = {"query": target_text or cleaned}
    if not anchor_text:
        return request
    # 기준 장소가 현재 DAY에 없더라도, 검색 결과에서 같은 한글 이름이 다시
    # 추천되는 경우는 막는다.
    request["exclude_names"] = [anchor_text]

    # 기준 장소가 현재 DAY 일정에 있다면 이름만 검색어에 섞지 않고 실제 좌표로
    # Places 결과를 우선 정렬한다. 같은 장소가 후보로 돌아오는 것도 ID로 제외한다.
    anchor_normalized = _normalized_place_name(anchor_text)
    for item in day.get("items") or []:
        place = item.get("place") if isinstance(item.get("place"), dict) else {}
        names = (item.get("title"), place.get("display_name"))
        if not any(
            name
            and (
                anchor_normalized in _normalized_place_name(name)
                or _normalized_place_name(name) in anchor_normalized
            )
            for name in names
        ):
            continue
        request["exclude_place_ids"] = [str(place.get("google_place_id") or "")]
        request["exclude_names"] = list(
            {anchor_text, *(str(name) for name in names if name)}
        )
        try:
            request["near_latitude"] = float(place["latitude"])
            request["near_longitude"] = float(place["longitude"])
        except (KeyError, TypeError, ValueError):
            pass
        break

    # 좌표를 찾지 못해도 자연어 기준점을 남겨 Google Text Search가 주변 장소를
    # 이해할 기회를 준다. 좌표가 있으면 이 문구와 locationBias가 함께 적용된다.
    request["query"] = f"{target_text} {anchor_text} 근처"
    return request


def _is_reference_place(place: dict, state: dict) -> bool:
    """기준 장소가 추천 결과로 재등장하는 것을 장소 ID와 이름으로 막는다."""

    place_id = str(place.get("google_place_id") or "")
    if place_id and place_id in set(state.get("exclude_place_ids") or []):
        return True
    display_name = _normalized_place_name(place.get("display_name"))
    if not display_name:
        return False
    for name in state.get("exclude_names") or []:
        normalized = _normalized_place_name(name)
        if normalized and (normalized in display_name or display_name in normalized):
            return True
    return False


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
                "source": "ai_recommendation",
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
                search_params: dict[str, object] = {"query": query, "max_results": 6}
                if state.get("near_latitude") is not None and state.get("near_longitude") is not None:
                    search_params["near_latitude"] = state["near_latitude"]
                    search_params["near_longitude"] = state["near_longitude"]
                search = api(
                    "GET",
                    f"/trips/{trip['id']}/days/{day['id']}/places/search",
                    params=search_params,
                    headers=auth_headers(),
                )
        except ApiError as error:
            state["load_error"] = str(error)
        else:
            candidates = search.get("places") or []
            state["recommendations"] = [
                place for place in candidates if not _is_reference_place(place, state)
            ][:2]
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
                        direct_params: dict[str, object] = {
                            "query": direct_query.strip(),
                            "max_results": 1,
                        }
                        if state.get("near_latitude") is not None and state.get("near_longitude") is not None:
                            direct_params["near_latitude"] = state["near_latitude"]
                            direct_params["near_longitude"] = state["near_longitude"]
                        direct_search = api(
                            "GET",
                            f"/trips/{trip['id']}/days/{day['id']}/places/search",
                            params=direct_params,
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


def _accommodation_query_from_message(message: str) -> str | None:
    """'숙소는 아파치 호텔이야' 같은 확정 문장에서 숙소 검색어를 꺼낸다.

    '숙소 근처 카페 추천'처럼 숙소를 기준점으로만 언급한 일반 장소 추천은 기존
    추천 카드로 처리해야 하므로, 숙소 확정 어미가 있을 때만 이 함수를 통과한다.
    """

    match = re.search(
        r"(?:내|우리)?\s*(?:숙소|호텔)\s*(?:는|은|이|가)?\s*"
        r"(?P<query>.+?)\s*(?:이야|예요|이에요|입니다|으로\s*할게|로\s*할게|"
        r"으로\s*정할게|로\s*정할게)[.!?\s]*$",
        message.strip(),
    )
    if not match:
        return None
    query = match.group("query").strip(" \"'“”‘’.,!?")
    if not query or any(word in query for word in ("근처", "주변", "추천", "어때")):
        return None
    return query


def _save_chat_accommodation(trip: dict, place: dict) -> bool:
    """사용자가 선택했거나 단일 후보인 Google 장소를 여행 숙소로 확정한다."""

    google_place_id = str(place.get("google_place_id") or "").strip()
    if not google_place_id:
        st.error("숙소 장소 식별자를 찾지 못했습니다. 다시 검색해 주세요.")
        return False
    try:
        api(
            "POST",
            f"/trips/{trip['id']}/accommodation",
            json={"google_place_id": google_place_id},
            headers=auth_headers(),
        )
    except ApiError as error:
        st.error(str(error))
        return False
    return True


def _render_accommodation_place_option(
    trip: dict,
    place: dict,
    *,
    key_prefix: str,
) -> None:
    """숙소 확인 카드 안의 후보 한 개와 확정 버튼을 그린다."""

    place_id = str(place.get("google_place_id") or "").strip()
    if not place_id:
        return
    with st.container(border=True):
        st.markdown(f"**{escape(str(place.get('display_name') or '이름 없는 장소'))}**")
        st.caption(
            f"{place.get('formatted_address') or '주소 정보 없음'} · {_place_rating_text(place)}"
        )
        if st.button("이 숙소로 설정", key=f"{key_prefix}_{place_id}", use_container_width=True):
            if _save_chat_accommodation(trip, place):
                state = st.session_state.chat_accommodation_candidates.get(str(trip["id"]), {})
                state["saved_place"] = place
                st.session_state.chat_accommodation_candidates[str(trip["id"])] = state
                st.rerun()


def render_chat_accommodation_card(trip: dict) -> None:
    """채팅으로 말한 숙소의 단일 자동 저장 또는 두 후보 확인 카드를 그린다."""

    state = st.session_state.chat_accommodation_candidates.get(str(trip["id"]))
    if not isinstance(state, dict):
        return
    query = str(state.get("query") or "").strip()
    if not query:
        return

    if "candidates" not in state and not state.get("load_error"):
        try:
            with st.spinner("Google Places에서 숙소를 찾고 있어요..."):
                search = api(
                    "GET",
                    f"/trips/{trip['id']}/accommodation/places/search",
                    params={"query": query, "max_results": 3},
                    headers=auth_headers(),
                )
        except ApiError as error:
            state["load_error"] = str(error)
        else:
            state["candidates"] = search.get("places") or []
        st.session_state.chat_accommodation_candidates[str(trip["id"])] = state

    candidates = state.get("candidates") or []
    # 유일한 Google 후보는 사용자가 다시 고를 필요 없이 바로 숙소로 저장한다.
    # 요청이 실패한 경우에는 attempted 표시를 남겨 Streamlit 재실행마다 반복 저장하지
    # 않고 오류 문구를 보여 준다.
    if len(candidates) == 1 and not state.get("auto_save_attempted"):
        state["auto_save_attempted"] = True
        st.session_state.chat_accommodation_candidates[str(trip["id"])] = state
        if _save_chat_accommodation(trip, candidates[0]):
            state["saved_place"] = candidates[0]
            st.session_state.chat_accommodation_candidates[str(trip["id"])] = state
            st.rerun()

    with st.container(key=f"chat_accommodation_{trip['id']}", border=True):
        st.markdown("#### 숙소 확인")
        if saved_place := state.get("saved_place"):
            st.success(f"‘{saved_place.get('display_name') or query}’을(를) 이 여행의 숙소로 설정했어요.")
            return
        if state.get("load_error"):
            st.warning(str(state["load_error"]))
            return
        if not candidates:
            st.info("일치하는 숙소를 찾지 못했습니다. 아래에서 이름을 직접 검색해 주세요.")
        elif len(candidates) == 1:
            # 자동 저장 요청이 실패한 경우에만 이 안내가 보인다.
            st.warning("숙소 자동 설정에 실패했습니다. 아래에서 다시 검색해 주세요.")
        else:
            st.caption(f"‘{query}’ 검색 결과가 여러 개예요. 여기가 맞나요?")
            candidate_columns = st.columns(2)
            for column, place in zip(candidate_columns, candidates[:2]):
                with column:
                    _render_accommodation_place_option(
                        trip,
                        place,
                        key_prefix=f"chat_accommodation_candidate_{trip['id']}",
                    )

        st.divider()
        st.caption("원하는 숙소가 없으면 Google Places에서 직접 찾아 설정할 수 있어요.")
        search_col, button_col = st.columns([4, 1])
        with search_col:
            direct_query = st.text_input(
                "숙소 직접 검색",
                placeholder="예: 오사카 아파치 호텔",
                key=f"chat_accommodation_search_{trip['id']}",
                label_visibility="collapsed",
            )
        with button_col:
            searched = st.button(
                "검색",
                key=f"chat_accommodation_search_button_{trip['id']}",
                use_container_width=True,
            )
        if searched:
            if not direct_query.strip():
                st.warning("찾고 싶은 숙소 이름을 입력하세요.")
            else:
                try:
                    with st.spinner("Google Places에서 숙소를 찾고 있어요..."):
                        direct_search = api(
                            "GET",
                            f"/trips/{trip['id']}/accommodation/places/search",
                            params={"query": direct_query.strip(), "max_results": 3},
                            headers=auth_headers(),
                        )
                except ApiError as error:
                    st.error(str(error))
                else:
                    state["direct_places"] = direct_search.get("places") or []
                    st.session_state.chat_accommodation_candidates[str(trip["id"])] = state
                    st.rerun()
        direct_places = state.get("direct_places") or []
        if direct_places:
            st.caption("직접 검색 결과")
            direct_columns = st.columns(2)
            for column, place in zip(direct_columns, direct_places[:2]):
                with column:
                    _render_accommodation_place_option(
                        trip,
                        place,
                        key_prefix=f"chat_accommodation_direct_{trip['id']}",
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


def render_context_controls(trip: dict, messages: list[dict]) -> None:
    """해당 여행의 채팅 기록을 DB에서 영구 삭제하는 버튼을 표시한다."""

    reset_column, info_column = st.columns([1, 2.8], vertical_alignment="center")
    if reset_column.button("대화 전체 삭제", key=f"delete_chat_history_{trip['id']}"):
        try:
            api("POST", f"/trips/{trip['id']}/chat/reset-context", headers=auth_headers())
        except SessionExpired:
            raise
        except ApiError as error:
            st.error(str(error))
        else:
            st.rerun()
    info_column.caption("이 여행의 채팅 기록이 즉시 삭제되며 복구할 수 없습니다. 일정 정보는 유지됩니다.")


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
    #message_count = len(messages)
    for index, change in enumerate(changes):
        timeline.append((str(change.get("created_at") or ""), message_count + index, "change", change))
    timeline.sort(key=lambda event: (event[0], event[1]))

    chat_box = st.container(height=680, key=f"dashboard_chat_{trip['id']}")
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
            elif event.get("role") == "system":
                # 이전 버전이 남긴 맥락 구분선은 삭제 전까지 보이지 않게만 처리한다.
                continue
            else:
                with st.chat_message(event["role"]):
                    st.write(event["content"])
        # 숙소 후보는 일정 DAY에 추가하는 장소 추천과 달리 여행 전체에 연결된다.
        # 따라서 선택한 날짜 탭과 무관하게 채팅 타임라인 아래에 보인다.
        render_chat_accommodation_card(trip)
        # 장소 추천 카드는 일반 채팅 메시지 다음에 보여 주되, 선택 시점에는 지금
        # 열어 둔 DAY를 사용한다. 그래서 날짜 탭을 바꾼 뒤 추가하면 그 DAY에 저장된다.
        render_chat_place_recommendation_card(trip, selected_day)
    render_context_controls(trip, messages)
    prompt = st.chat_input("메시지를 입력하세요", key=f"dashboard_chat_input_{trip['id']}")
    if not prompt:
        return
    if accommodation_query := _accommodation_query_from_message(prompt):
        st.session_state.chat_accommodation_candidates[str(trip["id"])] = {
            "query": accommodation_query,
        }
    if _looks_like_place_recommendation(prompt):
        st.session_state.chat_place_recommendations[str(trip["id"])] = (
            _recommendation_request_from_message(prompt, selected_day)
        )
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

    render_context_controls(trip, messages)
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

# 서버가 받는 값은 simple / illustrated 두 가지다 (백엔드 style 파라미터).
# 화면 라벨만 우리말로 붙인다 - 값을 화면에서 새로 만들면 서버가 422 를 준다.
EXPORT_STYLES = {
    "simple": ("심플형", "흰 배경 · 구분선 · 텍스트 중심", "인쇄하거나 캘린더에 붙이기 좋아요"),
    "illustrated": ("일러스트형", "손그림 다이어리 · 아이콘 · 캐릭터", "SNS나 메신저로 공유하기 좋아요"),
}

# 기다리는 동안 갈아 끼우는 문구다.
#
# **남은 시간을 적지 않는다.** 일정 길이에 따라 20초에서 80초까지 벌어지는데,
# "20~40초" 라고 적어 두면 40초가 지난 순간부터는 안내가 아니라 거짓말이 된다.
# 무엇을 하고 있는지를 대신 보여 준다.
EXPORT_PROGRESS_PHRASES = (
    "여행의 설렘을 한 장에 담고 있어요",
    "가고 싶은 곳들을 한자리에 모으고 있어요",
    "복잡한 동선은 가볍게 정리하고 있어요",
    "여행지의 숨은 매력을 찾고 있어요",
    "여행 동선을 차근차근 그리고 있어요",
    "일정마다 작은 즐거움을 더하고 있어요",
    "우리 여행에 어울리는 색을 입히고 있어요",
)

# 문구를 갈아 끼우는 간격. 7개를 한 바퀴 도는 데 약 20초라, 가장 짧은 대기에도
# 서너 개는 보이고 가장 긴 대기에도 같은 문구가 연달아 보이지 않는다.
EXPORT_PROGRESS_INTERVAL_SECONDS = 2.8


# [변경 사유] 일반 호출(60초)보다 길게 잡는다. 서버가 이미지 모델을 부르는 데
# 한 번에 20~40초가 걸리고, 그림 없이 글만 돌아오면 한 번 더 건다. 여기서 먼저
# 끊기면 다 그린 그림을 버리고 "만들 수 없어요" 를 띄우게 된다.
EXPORT_TIMEOUT_SECONDS = 150


def _fetch_export_pages(trip_id: str, style: str) -> tuple[list[tuple[str, bytes]], str]:
    """일정표를 장별로 받아 온다. ([(파일명, PNG), ...], 실패사유) 를 돌려준다.

    서버는 장별 PNG 를 **ZIP 한 개**로 보낸다. 장마다 따로 요청하면 8일 여행에서
    네 번을 순차로 기다려 타임아웃이 먼저 난다. ZIP 은 전송 형식일 뿐이고,
    사용자에게는 장별 [저장] 버튼으로 보여 준다.

    파일 이름은 ZIP 안의 엔트리 이름을 그대로 쓴다. 화면에서 다시 조립하면
    서버와 같은 규칙을 두 곳에 두게 되고, 한쪽만 고치면 이름이 갈린다.

    실패해도 예외를 올리지 않는다 - 모달 안에서 예외가 나면 사용자는 취소
    버튼조차 못 누른다. 사유를 문장으로 돌려주고 화면이 텍스트 대체 수단을 연다.
    """

    cache = st.session_state.export_images
    cache_key = f"{trip_id}:{style}"
    if cache_key in cache:
        # 이미 받아 둔 것은 기다릴 이유가 없다 - 문구도 띄우지 않는다.
        return cache[cache_key], ""

    # auth_headers() 는 st.session_state 를 읽는다. 워커 스레드에서 부르면
    # 세션 컨텍스트가 없어 실패하므로 **메인 스레드에서 미리** 만들어 넘긴다.
    headers = auth_headers()

    import random
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FutureTimeout

    placeholder = st.empty()
    # 같은 여행을 두 번 받을 때 같은 문구로 시작하면 멈춘 것처럼 보인다.
    offset = random.randrange(len(EXPORT_PROGRESS_PHRASES))

    def show(step: int) -> None:
        phrase = EXPORT_PROGRESS_PHRASES[(offset + step) % len(EXPORT_PROGRESS_PHRASES)]
        placeholder.info(phrase, icon=":material/image:")

    # **다운로드는 워커 스레드가 한다.** 메인 스레드가 응답을 기다리면 화면이
    # 통째로 멈춰 문구를 갈아 끼울 수 없다. st.spinner 로는 실행 중에 문구를
    # 바꿀 수 없어서 st.empty() 자리를 직접 고쳐 쓴다.
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_download_export_pages, trip_id, style, headers)
        step = 0
        show(step)
        while True:
            try:
                pages, failure = future.result(timeout=EXPORT_PROGRESS_INTERVAL_SECONDS)
                break
            except FutureTimeout:
                step += 1
                show(step)
            except SessionExpired:
                # 로그인 만료는 최상위 화면 보호 로직이 처리해야 한다.
                placeholder.empty()
                raise

    placeholder.empty()
    if pages:
        cache[cache_key] = pages
    return pages, failure


def _download_export_pages(
    trip_id: str, style: str, headers: dict[str, str]
) -> tuple[list[tuple[str, bytes]], str]:
    """ZIP 을 받아 장별로 푼다. **세션 상태를 건드리지 않는다.**

    워커 스레드에서 도는 함수라 st.session_state 에 손대면 안 된다. 캐시 읽기와
    쓰기, 인증 헤더 만들기는 부르는 쪽(_fetch_export_pages)이 메인 스레드에서 한다.
    """

    try:
        response = api_binary(
            "GET",
            f"/trips/{trip_id}/itinerary/export",
            params={"style": style},
            headers=headers,
            timeout=EXPORT_TIMEOUT_SECONDS,
        )
    except SessionExpired:
        raise
    except ApiError as error:
        return [], str(error)

    import io
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            # 이름에 1of4 · 2of4 가 들어 있어 정렬하면 장 순서가 된다.
            pages = [(name, archive.read(name)) for name in sorted(archive.namelist())]
    except zipfile.BadZipFile:
        return [], "일정표 파일을 열 수 없어요. 잠시 후 다시 시도해 주세요."

    if not pages:
        return [], "일정표를 만들지 못했어요. 잠시 후 다시 시도해 주세요."
    return pages, ""


@st.dialog("일정표 다운로드")
def render_export_dialog(trip: dict) -> None:
    """스타일 선택 -> 다운로드 두 단계로 끝나는 모달이다 (시안 SCR-007).

    카드 전체가 버튼이다. 카드 안에 별도 버튼을 두면 카드 몸통은 눌러도 아무
    반응이 없는데, 카드처럼 생긴 것을 눌렀는데 아무 일이 없으면 사용자는 그것이
    못 누르는 것이라고 읽는다.
    """

    trip_id = str(trip["id"])
    st.caption("원하는 스타일을 고르면 그때 만들기 시작합니다.")

    style = str(st.session_state.export_style or "simple")
    requested = st.session_state.export_requested_style
    cache = st.session_state.export_images
    for column, (key, (name, first, second)) in zip(st.columns(2), EXPORT_STYLES.items()):
        chosen = key == requested
        # 색만으로 가르지 않는다 - 상태를 글자로도 알린다. 이미 만들어 둔 스타일은
        # 다시 눌러도 곧바로 나오므로, 그 사실을 미리 보여 준다.
        if chosen:
            badge = "  ·  ✓ 만들었어요"
        elif f"{trip_id}:{key}" in cache:
            badge = "  ·  만들어 둠"
        else:
            badge = ""
        label = f"**{name}**{badge}  \n{first}  \n{second}"
        with column:
            if st.button(
                label,
                key=f"export_style_{key}",
                use_container_width=True,
                type="primary" if chosen else "secondary",
            ):
                # 카드를 누른 이 순간이 "만들기" 다. 누르기 전에는 그리지 않는다.
                st.session_state.export_style = key
                st.session_state.export_requested_style = key
                st.rerun()

    st.divider()

    if requested is None:
        # 아직 아무것도 고르지 않았다. 무엇을 하면 되는지와, 얼마나 걸리는지를
        # 미리 알린다 - 눌렀는데 30초 동안 아무 설명이 없으면 멈춘 줄 안다.
        st.info("위에서 스타일을 고르면 일정표를 만듭니다. 잠시 기다려 주세요.",
                icon=":material/image:")
        if st.button("닫기", key="export_cancel", use_container_width=True):
            st.session_state.export_dialog_trip_id = None
            st.session_state.export_requested_style = None
            st.rerun()
        return

    # 대기 문구는 _fetch_export_pages 가 직접 갈아 끼운다 (st.spinner 는 실행
    # 중에 문구를 바꿀 수 없다). 캐시에 있으면 문구 없이 곧바로 돌아온다.
    pages, failure = _fetch_export_pages(trip_id, requested)

    if failure:
        st.warning(failure)

    if len(pages) > 1:
        # 여러 장이면 왜 나뉘었는지 한 줄로 알린다. 설명이 없으면 사용자는
        # 일정이 잘려 나간 줄 안다.
        st.caption(f"일정이 길어 {len(pages)}장으로 나눠 그렸어요. 장마다 저장하세요.")
        # 썸네일을 함께 보여 준다 - 버튼만 있으면 어느 장이 며칠치인지 알 수 없다.
        for row_start in range(0, len(pages), 2):
            for column, (page, (name, image)) in zip(
                st.columns(2),
                list(enumerate(pages, start=1))[row_start : row_start + 2],
            ):
                with column:
                    st.image(image, use_container_width=True)
                    st.download_button(
                        f"{page}장 저장",
                        data=image,
                        file_name=name,
                        mime="image/png",
                        type="primary",
                        use_container_width=True,
                        key=f"export_download_{page}",
                    )
        st.divider()

    cancel_column, save_column = st.columns(2)
    if cancel_column.button("닫기", key="export_close", use_container_width=True):
        st.session_state.export_dialog_trip_id = None
        st.session_state.export_requested_style = None
        st.rerun()
    if len(pages) == 1:
        # 한 장이면 위의 격자를 만들지 않고 [다운로드] 하나로 끝낸다.
        name, image = pages[0]
        with save_column:
            st.download_button(
                "다운로드",
                data=image,
                file_name=name,
                mime="image/png",
                type="primary",
                use_container_width=True,
                key="export_download",
            )


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
            # [변경 사유] 시안 SCR-005 의 상단 [일정표 다운로드] 자리다. DAY 탭
            # 줄 아래, "오늘의 일정" 위에 둔다 - 일정을 보고 나서 누르는 동작이라
            # 일정 위에 있는 편이 자연스럽다.
            _, export_column = st.columns([2.2, 1])
            if export_column.button(
                "일정표 다운로드",
                key=f"open_export_{trip['id']}",
                use_container_width=True,
            ):
                st.session_state.export_dialog_trip_id = str(trip["id"])
                # 지난번에 고른 것이 남아 있으면 모달이 열리자마자 다시 그린다.
                st.session_state.export_requested_style = None
                st.rerun()
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
                f'<span class="dashboard-badge">{escape(weather_text)}</span>'
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

    # dialog 는 컬럼 바깥에서 열어 본문을 덮는 모달처럼 보이게 한다
    # (사이드바가 이미 쓰는 규칙 - streamlit_app.py:1997 주석 참고).
    if str(st.session_state.get("export_dialog_trip_id") or "") == str(trip["id"]):
        render_export_dialog(trip)


def _admin_dashboard_period_params(start_date: date, end_date: date) -> dict[str, str]:
    """관리자 대시보드가 사용할 KST 기준 조회 기간을 만든다."""

    start_at = datetime.combine(start_date, time.min, tzinfo=ZoneInfo("Asia/Seoul"))
    end_at = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
        tzinfo=ZoneInfo("Asia/Seoul"),
    )
    return {"start_at": start_at.isoformat(), "end_at": end_at.isoformat()}


def _admin_dashboard_metric_value(value: int | float | None, suffix: str = "") -> str:
    return f"{value or 0}{suffix}"


def _render_admin_dashboard_figma(summary: dict, error_items: list[dict]) -> None:
    """피그마의 KPI·차트·오류 모니터링 구성을 Streamlit 기본 기능으로 표현한다."""

    kpis = summary.get("kpis", {})
    with st.container(border=True):
        st.markdown('<div class="admin-panel-title">운영 현황</div>', unsafe_allow_html=True)
        cards = st.columns(5)
        card_values = [
            ("신규 가입자", kpis.get("user_signup_count", 0), ""),
            ("전체 요청", kpis.get("total_requests", 0), ""),
            ("성공 · 실패", f"{kpis.get('success_count', 0)} · {kpis.get('failure_count', 0)}", ""),
            ("에러율", kpis.get("error_rate_percent", 0), "%"),
            ("평균 응답시간", kpis.get("average_latency_ms", 0), " ms"),
        ]
        for column, (label, value, suffix) in zip(cards, card_values):
            with column:
                st.metric(label, _admin_dashboard_metric_value(value, suffix))

    hourly = summary.get("hourly_requests", [])
    chart_column, status_column = st.columns([1.55, 1], gap="medium")
    with chart_column:
        with st.container(border=True):
            st.markdown('<div class="admin-panel-title">시간별 요청량</div>', unsafe_allow_html=True)
            if hourly:
                st.bar_chart(
                    {
                        "성공": [item.get("success_count", 0) for item in hourly],
                        "실패": [item.get("failure_count", 0) for item in hourly],
                    },
                    height=250,
                )
            else:
                st.info("선택한 기간에 요청 로그가 없습니다.")
    with status_column:
        with st.container(border=True):
            st.markdown('<div class="admin-panel-title">성공 · 실패 현황</div>', unsafe_allow_html=True)
            success_count = int(kpis.get("success_count", 0) or 0)
            failure_count = int(kpis.get("failure_count", 0) or 0)
            total_count = success_count + failure_count
            success_ratio = success_count / total_count if total_count else 0
            st.metric("성공률", f"{success_ratio * 100:.1f}%")
            st.progress(success_ratio, text=f"성공 {success_count}건 / 실패 {failure_count}건")
            st.caption("요청 상태 코드 200~399를 성공으로 집계합니다.")

    error_counts: dict[str, int] = {}
    for item in error_items:
        label = str(item.get("error_type") or item.get("endpoint") or "알 수 없는 오류")
        error_counts[label] = error_counts.get(label, 0) + 1
    top_errors = sorted(error_counts.items(), key=lambda pair: (-pair[1], pair[0]))[:3]
    endpoint_column, error_column = st.columns([1.35, 1], gap="medium")
    with endpoint_column:
        with st.container(border=True):
            st.markdown('<div class="admin-panel-title">엔드포인트별 이용량</div>', unsafe_allow_html=True)
            endpoint_rows = [
                {
                    "엔드포인트": item.get("endpoint"),
                    "요청": item.get("request_count", 0),
                    "사용자": item.get("unique_user_count", 0),
                    "평균 응답(ms)": item.get("average_latency_ms", 0),
                    "에러율(%)": item.get("error_rate_percent", 0),
                }
                for item in summary.get("endpoint_usage", [])[:10]
            ]
            if endpoint_rows:
                st.dataframe(endpoint_rows, use_container_width=True, hide_index=True)
            else:
                st.info("엔드포인트 사용량이 없습니다.")
    with error_column:
        with st.container(border=True):
            st.markdown('<div class="admin-panel-title">오류 TOP 3</div>', unsafe_allow_html=True)
            if top_errors:
                for rank, (label, count) in enumerate(top_errors, start=1):
                    st.write(f"{rank}. {label}  ·  {count}건")
            else:
                st.success("오류가 없습니다.")

    llm_summary = summary.get("llm_summary", [])
    with st.container(border=True):
        st.markdown('<div class="admin-panel-title">LLM 요청 요약</div>', unsafe_allow_html=True)
        if llm_summary:
            st.dataframe(
                [
                    {
                        "모델": item.get("model"),
                        "요청": item.get("request_count", 0),
                        "실패": item.get("failure_count", 0),
                        "에러율(%)": item.get("error_rate_percent", 0),
                        "평균 응답(ms)": item.get("average_latency_ms", 0),
                    }
                    for item in llm_summary
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("선택한 기간에 LLM 요청 로그가 없습니다.")


def render_admin_access_denied() -> None:
    """관리자 인증이 없는 사용자가 직접 접근했을 때의 ADM-005 화면."""

    st.markdown(
        """
        <div class="admin-access-denied">
            <div class="eyebrow">TripMate_13_ADM-005</div>
            <h1>접근이 거부되었습니다</h1>
            <p>관리자 권한이 있는 계정으로 로그인한 뒤 다시 시도해주세요.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _, button_column, _ = st.columns([1, 1, 1])
    with button_column:
        if st.button("여행 화면으로 돌아가기", use_container_width=True, key="access_denied_to_trip"):
            st.session_state.current_view = "trip"
            request_main_scroll_to_top()
            st.rerun()


def render_admin_dashboard() -> None:
    """로그인한 관리자 세션 안에서 운영 대시보드를 렌더링한다."""

    st.title("운영 대시보드")
    render_admin_dashboard_filters()
    start_date = st.session_state.get("admin_dashboard_start_date", date.today())
    end_date = st.session_state.get("admin_dashboard_end_date", date.today())

    if start_date > end_date:
        st.error("시작일은 종료일보다 늦을 수 없습니다.")
        return

    params = _admin_dashboard_period_params(start_date, end_date)
    try:
        headers = auth_headers()
        summary = api("GET", "/admin/dashboard/summary", params=params, headers=headers, timeout=30)
        errors = api(
            "GET",
            "/admin/dashboard/errors",
            params={**params, "limit": "100"},
            headers=headers,
            timeout=30,
        )
    except ApiError as error:
        st.error(str(error))
        return

    period = summary.get("period", {})
    st.caption(f"조회 기간: {period.get('start_at', '')} ~ {period.get('end_at', '')}")
    _render_admin_dashboard_figma(
        summary,
        errors.get("items", []) if isinstance(errors, dict) else [],
    )

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


def _render_admin_console_figma() -> None:
    """피그마 ADM-002의 사용자 목록·상세 2열 구성을 렌더링한다."""

    render_admin_console_tabs("admin_console")
    st.title("사용자 관리")
    st.caption("운영 콘솔 · TripMate Admin")
    search = st.text_input(
        "사용자 검색",
        placeholder="이름 또는 이메일을 입력하세요",
        key="admin_console_search",
    ).strip()
    try:
        result = api(
            "GET",
            "/admin/console/users",
            params={"search": search, "limit": 100},
            headers=auth_headers(),
            timeout=30,
        )
    except ApiError as error:
        st.error(str(error))
        return

    users = result.get("items", []) if isinstance(result, dict) else []
    st.caption(f"전체 사용자 {result.get('total', 0) if isinstance(result, dict) else 0}명")
    if not users:
        st.info("조건에 맞는 사용자가 없습니다.")
        return

    list_column, detail_column = st.columns([1, 1.35], gap="medium")
    with list_column:
        with st.container(border=True):
            st.markdown('<div class="admin-panel-title">사용자 목록</div>', unsafe_allow_html=True)
            st.dataframe(
                [
                    {
                        "사용자": item.get("username") or "-",
                        "이메일": item.get("email") or "-",
                        "가입일": item.get("created_at") or "-",
                    }
                    for item in users
                ],
                use_container_width=True,
                hide_index=True,
            )
            user_options = {str(item.get("id")): item for item in users if item.get("id")}
            selected_user_id = st.selectbox(
                "상세 조회 사용자",
                options=list(user_options),
                format_func=lambda user_id: (
                    f"{user_options[user_id].get('username') or '-'} · "
                    f"{user_options[user_id].get('email') or '-'}"
                ),
                key="admin_console_selected_user",
            )

    try:
        detail = api(
            "GET",
            f"/admin/console/users/{selected_user_id}",
            headers=auth_headers(),
            timeout=30,
        )
    except ApiError as error:
        st.error(str(error))
        return

    with detail_column:
        with st.container(border=True):
            st.markdown('<div class="admin-panel-title">사용자 상세</div>', unsafe_allow_html=True)
            st.markdown(f"**{detail.get('username') or '-'}**")
            st.caption(detail.get("email") or "-")
            detail_values = [
                ("여행 수", detail.get("trip_count", 0)),
                ("API 요청", detail.get("request_count", 0)),
                ("활동 로그", detail.get("activity_count", 0)),
            ]
            for label, value in detail_values:
                st.metric(label, value)
            trips = detail.get("trips", [])
            if trips:
                st.markdown("#### 여행 목록")
                st.dataframe(
                    [
                        {
                            "여행": item.get("title") or item.get("destination") or "-",
                            "기간": f"{item.get('start_date') or '-'} ~ {item.get('end_date') or '-'}",
                            "상태": item.get("status") or "-",
                        }
                        for item in trips
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("여행 기록이 없습니다.")

            st.markdown("#### 최근 활동")
            activities = detail.get("recent_activities", [])
            if activities:
                st.dataframe(activities[:8], use_container_width=True, hide_index=True)
            else:
                st.info("활동 로그가 없습니다.")

            st.markdown("#### 최근 API 요청")
            requests = detail.get("recent_requests", [])
            if requests:
                st.dataframe(requests[:8], use_container_width=True, hide_index=True)
            else:
                st.info("API 요청 로그가 없습니다.")


def render_admin_feedback() -> None:
    """피그마 ADM-003의 피드백·페이스 집계 전용 화면을 렌더링한다."""

    render_admin_console_tabs("admin_feedback")
    st.title("피드백 · 페이스")
    st.caption("ADM-003 · 집계 전용")
    try:
        summary = api(
            "GET",
            "/admin/console/feedback",
            headers=auth_headers(),
            timeout=30,
        )
    except ApiError as error:
        st.error(str(error))
        return

    cards = st.columns(4)
    card_values = [
        ("전체 피드백", summary.get("feedback_count", 0)),
        ("긍정 피드백", summary.get("positive_count", 0)),
        ("부정 피드백", summary.get("negative_count", 0)),
        ("페이스 기록", summary.get("pace_count", 0)),
    ]
    for column, (label, value) in zip(cards, card_values):
        with column:
            st.metric(label, value)

    feedback_breakdown = summary.get("feedback_breakdown", [])
    pace_breakdown = summary.get("pace_breakdown", [])
    feedback_column, pace_column = st.columns(2, gap="medium")
    with feedback_column:
        with st.container(border=True):
            st.markdown('<div class="admin-panel-title">피드백 집계</div>', unsafe_allow_html=True)
            if feedback_breakdown:
                st.bar_chart(
                    {"건수": [int(item.get("count", 0) or 0) for item in feedback_breakdown]},
                    height=220,
                )
                st.dataframe(
                    [
                        {"구분": item.get("label") or "기타", "건수": item.get("count", 0)}
                        for item in feedback_breakdown
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("수집된 피드백 로그가 없습니다.")
    with pace_column:
        with st.container(border=True):
            st.markdown('<div class="admin-panel-title">페이스 집계</div>', unsafe_allow_html=True)
            if pace_breakdown:
                st.bar_chart(
                    {"건수": [int(item.get("count", 0) or 0) for item in pace_breakdown]},
                    height=220,
                )
                st.dataframe(
                    [
                        {"페이스": item.get("label") or "기타", "건수": item.get("count", 0)}
                        for item in pace_breakdown
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("수집된 페이스 로그가 없습니다.")

    st.caption("원문과 개인 식별 정보는 표시하지 않고 집계 결과만 제공합니다.")


def render_admin_system_status() -> None:
    """피그마 ADM-004의 최근 1시간 시스템 상태 화면을 렌더링한다."""

    render_admin_console_tabs("admin_system")
    st.title("시스템 상태")
    st.caption("ADM-004 · 최근 1시간")
    try:
        status = api(
            "GET",
            "/admin/console/system-status",
            headers=auth_headers(),
            timeout=30,
        )
    except ApiError as error:
        st.error(str(error))
        return

    overview_columns = st.columns(4)
    overview_values = [
        ("전체 요청", status.get("total_requests", 0)),
        ("실패 요청", status.get("failure_count", 0)),
        ("에러율", f'{status.get("error_rate_percent", 0)}%'),
        ("조회 범위", "최근 1시간"),
    ]
    for column, (label, value) in zip(overview_columns, overview_values):
        with column:
            st.metric(label, value)

    services = status.get("services", [])
    if not services:
        st.info("시스템 상태 데이터가 없습니다.")
        return

    service_columns = st.columns(2, gap="medium")
    for index, service in enumerate(services):
        with service_columns[index % 2]:
            with st.container(border=True):
                service_name = service.get("service") or "서비스"
                service_status = service.get("status") or "데이터 없음"
                st.markdown(
                    f'<div class="admin-panel-title">{escape(str(service_name))}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"상태: **{service_status}**")
                metrics = st.columns(3)
                metric_values = [
                    ("요청", service.get("request_count", 0)),
                    ("실패율", f'{service.get("failure_rate_percent", 0)}%'),
                    ("P95 응답", f'{service.get("p95_latency_ms", 0)} ms'),
                ]
                for metric_column, (label, value) in zip(metrics, metric_values):
                    with metric_column:
                        st.metric(label, value)

    st.caption("api_request_logs 기준으로 최근 1시간의 서비스 요청 상태를 집계합니다.")


def render_admin_console() -> None:
    """로그인한 관리자 세션 안에서 운영콘솔 사용자 조회 화면을 렌더링한다."""

    st.title("사용자 관리")
    st.caption("운영 콘솔 · TripMate Admin")

    search = st.text_input(
        "사용자 검색",
        placeholder="이름 또는 이메일을 입력하세요",
        key="admin_console_search",
    ).strip()
    try:
        result = api(
            "GET",
            "/admin/console/users",
            params={"search": search, "limit": 100},
            headers=auth_headers(),
            timeout=30,
        )
    except ApiError as error:
        st.error(str(error))
        return

    users = result.get("items", []) if isinstance(result, dict) else []
    st.caption(f"전체 사용자 {result.get('total', 0) if isinstance(result, dict) else 0}명")
    if not users:
        st.info("조건에 맞는 사용자가 없습니다.")
        return

    with st.container(border=True):
        st.markdown('<div class="admin-panel-title">서비스 이용 현황</div>', unsafe_allow_html=True)
        overview_columns = st.columns(4)
        overview_values = [
            ("가입 사용자", result.get("total", 0)),
            ("전체 여행", sum(int(item.get("trip_count", 0) or 0) for item in users)),
            ("API 요청", sum(int(item.get("request_count", 0) or 0) for item in users)),
            ("사용자 활동", sum(int(item.get("activity_count", 0) or 0) for item in users)),
        ]
        for column, (label, value) in zip(overview_columns, overview_values):
            with column:
                st.metric(label, value)

    st.bar_chart(
        {
            "여행 수": [int(item.get("trip_count", 0) or 0) for item in users[:10]],
            "API 요청 수": [int(item.get("request_count", 0) or 0) for item in users[:10]],
        },
        height=180,
    )

    st.dataframe(
        [
            {
                "사용자명": item.get("username") or "-",
                "이메일": item.get("email") or "-",
                "가입일": item.get("created_at") or "-",
                "여행 수": item.get("trip_count", 0),
                "요청 수": item.get("request_count", 0),
                "최근 활동": item.get("last_active_at") or "-",
            }
            for item in users
        ],
        use_container_width=True,
        hide_index=True,
    )

    user_options = {str(item.get("id")): item for item in users if item.get("id")}
    selected_user_id = st.selectbox(
        "상세 조회 사용자",
        options=list(user_options),
        format_func=lambda user_id: (
            f"{user_options[user_id].get('username') or '-'} · "
            f"{user_options[user_id].get('email') or '-'}"
        ),
        key="admin_console_selected_user",
    )
    try:
        detail = api(
            "GET",
            f"/admin/console/users/{selected_user_id}",
            headers=auth_headers(),
            timeout=30,
        )
    except ApiError as error:
        st.error(str(error))
        return

    st.subheader("사용자 상세")
    detail_columns = st.columns(5)
    detail_values = [
        ("사용자명", detail.get("username") or "-"),
        ("이메일", detail.get("email") or "-"),
        ("가입일", detail.get("created_at") or "-"),
        ("여행 수", detail.get("trip_count", 0)),
        ("API 요청 수", detail.get("request_count", 0)),
    ]
    for column, (label, value) in zip(detail_columns, detail_values):
        with column:
            st.metric(label, value)

    left, right = st.columns(2)
    with left:
        st.markdown("#### 여행 목록")
        st.dataframe(detail.get("trips", []), use_container_width=True, hide_index=True)
    with right:
        st.markdown("#### 최근 활동 로그")
        activities = detail.get("recent_activities", [])
        if activities:
            st.dataframe(activities, use_container_width=True, hide_index=True)
        else:
            st.info("활동 로그가 없습니다.")

    st.markdown("#### 최근 API 요청")
    requests = detail.get("recent_requests", [])
    if requests:
        st.dataframe(requests, use_container_width=True, hide_index=True)
    else:
        st.info("API 요청 로그가 없습니다.")


def render_signed_in() -> None:
    """현재 사용자의 여행을 불러오고 알맞은 로그인 상태 화면을 그린다."""
    trips = api("GET", "/me/trips", headers=auth_headers())
    if trips and st.session_state.selected_trip_id not in {trip["id"] for trip in trips}:
        st.session_state.selected_trip_id = trips[0]["id"]
        request_main_scroll_to_top()

    render_sidebar(trips)

    admin_views = {"admin_dashboard", "admin_console", "admin_feedback", "admin_system"}
    if st.session_state.get("current_view") in admin_views and not st.session_state.get("is_dashboard_admin"):
        render_admin_access_denied()
        return

    if st.session_state.get("current_view") == "admin_dashboard":
        render_admin_dashboard()
        return

    if st.session_state.get("current_view") == "admin_console":
        _render_admin_console_figma()
        return

    if st.session_state.get("current_view") == "admin_feedback":
        render_admin_feedback()
        return

    if st.session_state.get("current_view") == "admin_system":
        render_admin_system_status()
        return

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

