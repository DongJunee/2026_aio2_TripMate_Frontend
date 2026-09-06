from copy import deepcopy
from datetime import date

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="TripMate | AI Travel Concierge",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


DEFAULT_TRIPS = {
    "tokyo": {
        "name": "Tokyo",
        "country": "도쿄, 일본",
        "emoji": "🇯🇵",
        "travelers": "2명",
        "style": "맛집 · 쇼핑",
        "progress": 35,
        "start_date": date(2026, 5, 20),
        "end_date": date(2026, 5, 24),
    },
}


THEMES = {
    "기본": {
        "primary": "#FF6B6B",
        "background": "#FFFFFF",
    },
    "한국 🇰🇷": {
        "primary": "#CD2E3A",
        "background": "#F8F9FA",
    },
    "일본 🇯🇵": {
        "primary": "#BC002D",
        "background": "#FFF8F8",
    },
    "프랑스 🇫🇷": {
        "primary": "#0055A4",
        "background": "#F5F7FF",
    },
    "이탈리아 🇮🇹": {
        "primary": "#008C45",
        "background": "#F5FFF8",
    },
}


if "theme" not in st.session_state:
    st.session_state.theme = "기본"

selected_theme = THEMES[st.session_state.theme]


DEFAULT_ITINERARY = [
    {
        "day": 1,
        "date": "5/20 (화)",
        "title": "도쿄 도착 & 시부야 탐방",
        "area": "시부야",
        "theme": "city",
        "places": [
            {"id": "shibuya_crossing", "name": "하치코 광장", "icon": "🐕", "included": True, "lat": 35.6595, "lon": 139.7005},
            {"id": "shibuya_sky", "name": "시부야 스카이", "icon": "🌃", "included": True, "lat": 35.6585, "lon": 139.7020},
            {"id": "center_gai", "name": "센가이 거리", "icon": "🛍️", "included": True, "lat": 35.6604, "lon": 139.6995},
        ],
    },
    {
        "day": 2,
        "date": "5/21 (수)",
        "title": "아사쿠사 & 우에노 문화 탐방",
        "area": "아사쿠사",
        "theme": "temple",
        "places": [
            {"id": "sensoji", "name": "센소지", "icon": "⛩️", "included": True, "lat": 35.7148, "lon": 139.7967},
            {"id": "ueno_park", "name": "우에노 공원", "icon": "🌿", "included": True, "lat": 35.7156, "lon": 139.7745},
            {"id": "ameyoko", "name": "아메요코 쇼핑거리", "icon": "🧺", "included": True, "lat": 35.7098, "lon": 139.7748},
        ],
    },
    {
        "day": 3,
        "date": "5/22 (목)",
        "title": "신주쿠 & 하라주쿠 트렌드 투어",
        "area": "신주쿠",
        "theme": "tower",
        "places": [
            {"id": "meiji", "name": "메이지 신궁", "icon": "⛩️", "included": True, "lat": 35.6764, "lon": 139.6993},
            {"id": "takeshita", "name": "다케시타 거리", "icon": "👗", "included": True, "lat": 35.6710, "lon": 139.7030},
            {"id": "harajuku_cafe", "name": "하라주쿠 카페", "icon": "☕", "included": True, "lat": 35.6697, "lon": 139.7041},
            {"id": "omotesando", "name": "오모테산도", "icon": "🌿", "included": True, "lat": 35.6650, "lon": 139.7127},
        ],
    },
    {
        "day": 4,
        "date": "5/23 (금)",
        "title": "도쿄 근교 당일치기",
        "area": "하코네",
        "theme": "mountain",
        "places": [
            {"id": "hakone", "name": "하코네", "icon": "🗻", "included": True, "lat": 35.2323, "lon": 139.1069},
            {"id": "ropeway", "name": "로프웨이", "icon": "🚠", "included": True, "lat": 35.2457, "lon": 139.0218},
            {"id": "onsen", "name": "온천", "icon": "♨️", "included": True, "lat": 35.2314, "lon": 139.1022},
        ],
    },
    {
        "day": 5,
        "date": "5/24 (토)",
        "title": "여유로운 아침 & 귀국",
        "area": "신주쿠",
        "theme": "airport",
        "places": [
            {"id": "kinenkan", "name": "기념품 쇼핑", "icon": "🎁", "included": True, "lat": 35.6900, "lon": 139.7006},
            {"id": "brunch", "name": "브런치 카페", "icon": "🥐", "included": True, "lat": 35.6886, "lon": 139.7008},
            {"id": "airport", "name": "공항 이동", "icon": "✈️", "included": True, "lat": 35.7720, "lon": 140.3929},
        ],
    },
]


st.markdown(
    """
    <style>
        :root { color-scheme: dark; }
        .stApp, [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 53% -20%, rgba(42, 89, 190, .20), transparent 31rem),
                linear-gradient(135deg, #04101f 0%, #071627 54%, #030b17 100%);
            color: #f6f8ff;
        }
        .block-container {
            max-width: 1740px;
            padding: 1.2rem 1.25rem 1.8rem;
        }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #061426 0%, #071b32 100%);
            border-right: 1px solid rgba(136, 170, 255, .17);
        }
        section[data-testid="stSidebar"] > div:first-child { padding-top: .7rem; }
        [data-testid="stSidebar"] .block-container { padding: 1rem .85rem; }
        h1, h2, h3, p, span, label { color: #f5f7ff; }
        [data-testid="stCaptionContainer"] { color: #96a4c7; }
        hr { border-color: rgba(139, 161, 213, .15); }
        .brand-kicker { color: #a8a0ff; font-size: 1.9rem; line-height: 1; }
        .brand-name { font-size: 2.15rem; font-weight: 800; letter-spacing: -.075rem; margin-top: .15rem; }
        .brand-sub { color: #a9aac8; font-size: .94rem; margin-top: -.25rem; letter-spacing: .015rem; }
        .eyebrow { color: #a893ff; font-size: .76rem; font-weight: 800; letter-spacing: .08rem; }
        .page-title { font-size: 2rem; font-weight: 800; letter-spacing: -.06rem; margin: .02rem 0; }
        .page-subtitle { color: #aebbd4; font-size: 1rem; margin-bottom: 1.15rem; }
        .date-pill {
            border: 1px solid rgba(92, 137, 255, .25); border-radius: 999px;
            background: rgba(16, 40, 78, .58); color: #d9e3ff; padding: .58rem 1rem;
            text-align: center; font-weight: 650; white-space: nowrap; margin-top: .4rem;
        }
        .summary-card {
            min-height: 112px; border-radius: 16px; padding: 1.1rem 1rem;
            background: linear-gradient(145deg, rgba(15, 38, 74, .91), rgba(8, 25, 50, .95));
            border: 1px solid rgba(111, 151, 235, .2); box-shadow: inset 0 1px rgba(255,255,255,.025);
        }
        .summary-icon {
            float: left; width: 3.55rem; height: 3.55rem; display: grid; place-items: center;
            margin: .05rem .85rem 0 0; border-radius: 13px; font-size: 1.65rem;
            background: linear-gradient(135deg, #0d62da, #253fab); box-shadow: 0 8px 22px rgba(15, 84, 220, .27);
        }
        .summary-icon.violet { background: linear-gradient(135deg, #7665f2, #513ba7); }
        .summary-label { color: #9eacc7; font-size: .72rem; font-weight: 750; letter-spacing: .07rem; padding-top: .1rem; }
        .summary-value { color: #f8faff; font-size: 1.07rem; font-weight: 780; margin-top: .28rem; }
        .summary-detail { color: #a3b0cd; font-size: .84rem; margin-top: .17rem; }
        .progress-track { height: .42rem; background: #223654; border-radius: 999px; overflow: hidden; margin-top: .62rem; }
        .progress-fill { height: 100%; border-radius: inherit; background: linear-gradient(90deg, #4576ff, #8b68ff); }
        .panel {
            border: 1px solid rgba(124, 158, 224, .25); border-radius: 17px;
            background: linear-gradient(155deg, rgba(8, 28, 55, .88), rgba(6, 20, 40, .92));
            box-shadow: inset 0 1px rgba(255,255,255,.028);
            padding: .85rem .9rem;
        }
        .panel-heading { display:flex; align-items:center; justify-content:space-between; font-size:1.12rem; font-weight:800; margin: .1rem .05rem .72rem; }
        .mini-action { color: #9db9ff; font-size: .78rem; font-weight: 700; padding: .42rem .64rem; border-radius: 9px; background: rgba(24, 57, 110, .5); }
        .timeline-row {
            position: relative; display: grid; grid-template-columns: 2.55rem 1fr 5.65rem; gap: .68rem;
            min-height: 6.58rem; padding: .72rem .42rem .65rem .04rem;
            border-top: 1px solid rgba(130, 156, 211, .11);
        }
        .timeline-row:first-of-type { border-top: none; }
        .timeline-row.selected { background: linear-gradient(90deg, rgba(57, 94, 210, .16), transparent 86%); border-radius: 12px; }
        .timeline-node { width: 2.14rem; height: 2.14rem; border-radius: 50%; display: grid; place-items:center; margin-top:.04rem; font-size: .94rem; font-weight:800; background: linear-gradient(145deg, #1f79ff, #2654c5); box-shadow: 0 6px 17px rgba(22, 92, 255, .32); }
        .timeline-node.violet { background: linear-gradient(145deg, #886eff, #5141bf); }
        .timeline-node.gray { background: #405172; }
        .timeline-line { position: absolute; left: 1.08rem; top: 3.1rem; bottom: -1.12rem; width: 2px; background: linear-gradient(#35558f, #223a63); }
        .timeline-row:last-child .timeline-line { display:none; }
        .day-label { color:#66a1ff; font-size:.82rem; font-weight:800; }
        .day-label.violet { color:#ab8bff; }
        .day-date { color:#9caac5; font-size:.77rem; margin-left:.55rem; }
        .day-title { font-size:.98rem; font-weight:740; margin:.33rem 0 .45rem; }
        .place-chip { display:inline-block; margin:0 .26rem .25rem 0; padding:.28rem .48rem; font-size:.71rem; color:#c6d2e9; border-radius:999px; background:rgba(39, 62, 102, .58); }
        .place-chip.focus { color:#efeaff; border:1px solid #8a69ff; background:rgba(106, 69, 194, .32); }
        .day-art { height:5.42rem; border-radius: 10px; display:grid; place-items:center; font-size:2rem; border:1px solid rgba(185, 208, 255,.12); }
        .day-art.city { background: linear-gradient(155deg, #985768, #3a67ad 58%, #102445); }
        .day-art.temple { background: linear-gradient(155deg, #dcb1ac, #a45834 48%, #2b3358); }
        .day-art.tower { background: linear-gradient(155deg, #8bb3e2, #826bc5 45%, #2d4b7e); }
        .day-art.mountain { background: linear-gradient(155deg, #9cd3f1, #4779b0 44%, #163c57); }
        .day-art.airport { background: linear-gradient(155deg, #ffc78c, #4e7da5 50%, #1b2d51); }
        .map-wrap { border-radius: 13px; overflow:hidden; border: 1px solid rgba(105, 139, 213,.14); background:#091a31; }
        .map-caption { padding:.65rem .72rem .35rem; color:#aebce1; font-size:.77rem; }
        .map-legend { display:grid; grid-template-columns:1fr 1fr; gap:.5rem; padding:.74rem .18rem .06rem; }
        .legend-item { color:#c8d6ef; font-size:.79rem; }
        .legend-dot { display:inline-grid; place-items:center; width:1.35rem; height:1.35rem; margin-right:.36rem; border-radius:50%; background:#286ff0; color:white; font-size:.69rem; font-weight:800; }
        .legend-dot.violet { background:#7458d5; }
        .editor-note { color:#a6b3cc; font-size:.81rem; margin:.12rem 0 .6rem; }
        .selected-place { padding:.72rem .8rem; border-radius:12px; background:rgba(75, 53, 147,.2); border:1px solid rgba(139, 101, 255,.5); color:#f1eeff; margin-top:.6rem; }
        .sidebar-trip {
            margin: .2rem 0 .8rem; padding: .85rem .8rem; border-radius:15px;
            border: 1px solid #286de1; background: linear-gradient(145deg, rgba(19,70,153,.5), rgba(11,36,76,.58));
        }
        .sidebar-trip-title { font-size:1rem; font-weight:780; }
        .sidebar-trip-detail { color:#aab8d2; font-size:.78rem; margin-top:.16rem; }
        .nav-item { color:#b8c4dc; padding:.72rem .55rem; margin-bottom:.14rem; border-radius:10px; font-weight:650; }
        .nav-item.active { color:#fff; background: linear-gradient(90deg, #225ed4, #1a47af); }
        .pace-card { margin-top:1.3rem; padding:1rem; border:1px solid rgba(117,150,213,.2); border-radius:16px; background: rgba(8, 28, 55,.7); }
        .pace-title { color:#e3e8fa; font-weight:750; font-size:.92rem; }
        .pace-detail { color:#aebbd5; font-size:.8rem; margin-top:.65rem; }
        .stButton > button { border: 1px solid rgba(124, 157, 221, .32); color:#deebff; background: rgba(21, 46, 85, .78); border-radius: 10px; font-weight: 700; min-height: 2.35rem; }
        .stButton > button:hover { border-color:#6f96ff; color:#fff; background:rgba(35,74,139,.85); }
        .stButton > button[kind="primary"] { border:none; background:linear-gradient(135deg, #206ee9, #403ec4); box-shadow:0 7px 18px rgba(25,87,224,.25); }
        [data-testid="stSidebar"] .stButton > button { text-align:left; padding-left:.8rem; }
        [data-testid="stDateInput"] input, [data-testid="stTextInput"] input {
            background:#0b2343 !important; color:#ecf3ff !important; border-color:rgba(130,159,226,.35) !important;
        }
        [data-testid="stChatMessage"] { background:transparent; padding:.25rem 0; }
        [data-testid="stChatMessageContent"] { background: rgba(18, 42, 77, .78); border:1px solid rgba(118,148,206,.18); border-radius:12px; color:#edf3ff; }
        div[data-testid="stChatInput"] textarea { background:#0a203e !important; color:#eef4ff !important; border:1px solid rgba(119,151,219,.31) !important; border-radius:14px !important; }
        div[data-testid="stChatInput"] { padding-top:.55rem; }
        .st-emotion-cache-1v0mbdj, [data-testid="stVerticalBlockBorderWrapper"] { border-color:rgba(124,158,224,.18); }
        @media (max-width: 1050px) {
            .page-title { font-size:1.65rem; }
            .day-art { display:none; }
            .timeline-row { grid-template-columns:2.35rem 1fr; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# 선택한 국가 테마는 다크 패널을 유지하면서, 화면 바탕과 강조 버튼에 적용합니다.
st.markdown(
    f"""
    <style>
        :root {{
            --travel-primary: {selected_theme["primary"]};
            --travel-background: {selected_theme["background"]};
        }}
        .stApp, [data-testid="stAppViewContainer"] {{
            background:
                radial-gradient(circle at 53% -20%, color-mix(in srgb, var(--travel-primary) 16%, transparent), transparent 31rem),
                var(--travel-background) !important;
        }}
        .stButton > button[kind="primary"] {{
            background: var(--travel-primary) !important;
        }}
        .page-title {{ color: #12213b; }}
        .page-subtitle {{ color: #51627f; }}
        .date-pill {{
            color: #1b2c48; background: rgba(255, 255, 255, .74);
            border-color: var(--travel-primary);
        }}
        .theme-caption {{
            color: var(--travel-primary); font-size: .75rem; font-weight: 800;
            letter-spacing: .06rem; margin: .3rem 0 .75rem;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)


def duration_text(start_date: date, end_date: date) -> str:
    total_nights = max((end_date - start_date).days, 0)
    return f"{total_nights}박 {total_nights + 1}일"


def date_text(start_date: date, end_date: date) -> str:
    return f"{start_date.month}월 {start_date.day}일 – {end_date.month}월 {end_date.day}일"


def get_day(day_number: int) -> dict:
    return next(day for day in st.session_state.itinerary if day["day"] == day_number)


def get_place(day: dict, place_id: str) -> dict:
    return next(place for place in day["places"] if place["id"] == place_id)


def select_day(day_number: int) -> None:
    st.session_state.selected_day = day_number
    selected = get_day(day_number)
    if st.session_state.selected_place not in {place["id"] for place in selected["places"]}:
        st.session_state.selected_place = selected["places"][0]["id"]


def move_selected_place(direction: int) -> None:
    day = get_day(st.session_state.selected_day)
    place_ids = [place["id"] for place in day["places"]]
    index = place_ids.index(st.session_state.selected_place)
    target = index + direction
    if 0 <= target < len(day["places"]):
        day["places"][index], day["places"][target] = day["places"][target], day["places"][index]
        moved = day["places"][target]
        direction_text = "앞" if direction < 0 else "뒤"
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"‘{moved['name']}’을(를) 한 칸 {direction_text}으로 옮겼어요. 지도 마커 순서도 함께 갱신했어요.",
            }
        )


def toggle_selected_place() -> None:
    day = get_day(st.session_state.selected_day)
    place = get_place(day, st.session_state.selected_place)
    place["included"] = not place["included"]
    action = "일정에 포함했어요" if place["included"] else "일정에서 제외했어요"
    st.session_state.messages.append({"role": "assistant", "content": f"‘{place['name']}’을(를) {action}."})


def append_chat_response(prompt: str) -> None:
    response = "좋아요. 원하는 분위기와 이동 시간을 고려해 일정에 반영할 수 있어요."
    prompt_lower = prompt.replace(" ", "")
    day_three = get_day(3)
    cafe_exists = any(place["id"] == "blue_bottle" for place in day_three["places"])

    if "카페" in prompt_lower and ("추가" in prompt_lower or "추천" in prompt_lower):
        if not cafe_exists:
            day_three["places"].append(
                {
                    "id": "blue_bottle",
                    "name": "블루보틀 하라주쿠",
                    "icon": "🫖",
                    "included": True,
                    "lat": 35.6688,
                    "lon": 139.7048,
                }
            )
            st.session_state.selected_day = 3
            st.session_state.selected_place = "blue_bottle"
            response = "DAY 3에 ‘블루보틀 하라주쿠’를 추가했어요. 아래 장소 카드에서 선택한 뒤 ← / → 버튼으로 동선을 조정해보세요."
        else:
            response = "DAY 3 카페 추천은 이미 일정에 반영되어 있어요. 장소를 선택해 순서를 바꾸거나 제외할 수 있어요."
    elif "교통" in prompt_lower or "이동" in prompt_lower:
        response = "현재 화면은 데모 이동 시간이에요. 나중에 Google Routes API를 연결하면 실제 도보·대중교통 시간으로 바꿀 수 있어요."
    elif "제외" in prompt_lower:
        response = "제외할 장소를 타임라인 아래에서 선택한 뒤 ‘일정에서 제외’를 눌러주세요. 지도에서도 바로 빠집니다."

    st.session_state.messages.append({"role": "assistant", "content": response})


if "trips" not in st.session_state:
    st.session_state.trips = deepcopy(DEFAULT_TRIPS)
if "itinerary" not in st.session_state:
    st.session_state.itinerary = deepcopy(DEFAULT_ITINERARY)
if "selected_trip" not in st.session_state:
    st.session_state.selected_trip = "tokyo"
if "selected_day" not in st.session_state:
    st.session_state.selected_day = 3
if "selected_place" not in st.session_state:
    st.session_state.selected_place = "harajuku_cafe"
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "안녕하세요! TripMate입니다. 도쿄 여행을 더 특별하게 만들어드릴게요. 무엇을 도와드릴까요?"},
        {"role": "user", "content": "DAY 3 일정에 추천 카페를 추가해줘."},
        {"role": "assistant", "content": "DAY 3 하라주쿠 주변에 들르기 좋은 카페를 일정에 넣어뒀어요. 선택 후 순서도 조정할 수 있어요."},
    ]


with st.sidebar:
    st.markdown('<div class="brand-kicker">✦</div><div class="brand-name">TripMate</div><div class="brand-sub">AI Travel Concierge</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    theme = st.selectbox(
        "국가 테마",
        list(THEMES),
        key="theme",
    )
    st.markdown(f'<div class="theme-caption">● {theme} 테마 적용 중</div>', unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">CURRENT TRIP</div>', unsafe_allow_html=True)

    for trip_key, trip_option in st.session_state.trips.items():
        active = trip_key == st.session_state.selected_trip
        button_type = "primary" if active else "secondary"
        if st.button(
            f"{trip_option['emoji']}  {trip_option['name']} · {duration_text(trip_option['start_date'], trip_option['end_date'])}",
            key=f"trip_{trip_key}",
            use_container_width=True,
            type=button_type,
        ):
            st.session_state.selected_trip = trip_key
            st.session_state.selected_day = 3
            st.session_state.selected_place = get_day(st.session_state.selected_day)["places"][0]["id"]

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="nav-item active">▣ &nbsp; 여행 일정</div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-item">⌖ &nbsp; 여행 지도</div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-item">▢ &nbsp; 맛집 · 쇼핑</div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-item">♡ &nbsp; 저장된 일정</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    current_trip = st.session_state.trips[st.session_state.selected_trip]
    selected_dates = st.date_input(
        "여행 기간",
        value=(current_trip["start_date"], current_trip["end_date"]),
        key=f"dates_{st.session_state.selected_trip}",
        format="YYYY-MM-DD",
    )
    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        current_trip["start_date"], current_trip["end_date"] = selected_dates

    st.markdown(
        f'''<div class="pace-card">
            <div class="pace-title">✦ 오늘의 페이스: <span style="color:#a28bff">여유롭게</span></div>
            <div class="progress-track"><div class="progress-fill" style="width:{current_trip['progress']}%"></div></div>
            <div class="pace-detail">전체 일정의 {current_trip['progress']}% 완료</div>
        </div>''',
        unsafe_allow_html=True,
    )


trip = st.session_state.trips[st.session_state.selected_trip]
duration = duration_text(trip["start_date"], trip["end_date"])
trip_dates = date_text(trip["start_date"], trip["end_date"])

title_col, date_col = st.columns([1, 0.42])
with title_col:
    st.markdown('<div class="eyebrow">✦ PERSONAL TRAVEL DASHBOARD</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-title">{trip["name"]} 여행을 환영합니다! ✨</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">설레는 여행, TripMate가 완벽한 여정을 도와드릴게요.</div>', unsafe_allow_html=True)
with date_col:
    st.markdown(f'<div class="date-pill">▣ &nbsp; {trip_dates} ({duration})</div>', unsafe_allow_html=True)

summary = [
    ("▣", "여행 기간", duration, trip_dates, ""),
    ("⌖", "여행 지역", trip["country"], "여행지", "violet"),
    ("▣", "방문 일정", "4개", "예약 및 방문지", ""),
    ("☑", "여정 진행률", f"{trip['progress']}%", "", "violet"),
]
summary_columns = st.columns(4, gap="small")
for column, (icon, label, value, detail, icon_class) in zip(summary_columns, summary):
    with column:
        progress_html = ""
        if label == "여정 진행률":
            progress_html = f'<div class="progress-track"><div class="progress-fill" style="width:{trip["progress"]}%"></div></div>'
        st.markdown(
            f'''<div class="summary-card">
                <div class="summary-icon {icon_class}">{icon}</div>
                <div class="summary-label">{label.upper()}</div>
                <div class="summary-value">{value}</div>
                <div class="summary-detail">{detail}</div>{progress_html}
            </div>''',
            unsafe_allow_html=True,
        )

st.markdown("<div style='height:.55rem'></div>", unsafe_allow_html=True)

timeline_col, map_col, chat_col = st.columns([1.08, 1.05, 0.82], gap="medium")

with timeline_col:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-heading"><span>여행 일정</span><span class="mini-action">일정 선택 ›</span></div>', unsafe_allow_html=True)

    for day in st.session_state.itinerary:
        selected_class = "selected" if day["day"] == st.session_state.selected_day else ""
        node_class = "violet" if day["day"] in (2, 4) else ("gray" if day["day"] == 5 else "")
        day_class = "violet" if day["day"] in (2, 4) else ""
        day_emoji = {1: "🌆", 2: "⛩️", 3: "🏙️", 4: "🗻", 5: "✈️"}[day["day"]]
        chips = "".join(
            f'<span class="place-chip {"focus" if place["id"] == st.session_state.selected_place and day["day"] == st.session_state.selected_day else ""}">{place["name"]}</span>'
            for place in day["places"] if place["included"]
        )
        st.markdown(
            f'''<div class="timeline-row {selected_class}">
                <div><div class="timeline-node {node_class}">{day["day"]}</div><div class="timeline-line"></div></div>
                <div>
                    <span class="day-label {day_class}">DAY {day["day"]}</span><span class="day-date">{day["date"]}</span>
                    <div class="day-title">{day["title"]}</div>
                    <div>{chips}</div>
                </div>
                <div class="day-art {day["theme"]}">{day_emoji}</div>
            </div>''',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)

    day_options = {f"DAY {item['day']} · {item['area']}": item["day"] for item in st.session_state.itinerary}
    current_day_label = next(label for label, number in day_options.items() if number == st.session_state.selected_day)
    picked_day = st.selectbox("편집할 일정", list(day_options), index=list(day_options).index(current_day_label), label_visibility="collapsed")
    if day_options[picked_day] != st.session_state.selected_day:
        select_day(day_options[picked_day])
        st.rerun()

    editing_day = get_day(st.session_state.selected_day)
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown(f'<div class="panel-heading"><span>DAY {editing_day["day"]} · 장소 순서</span><span class="mini-action">선택 후 이동</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="editor-note">장소를 선택한 뒤 이전 또는 다음 장소와 순서를 바꿔 동선을 조정하세요.</div>', unsafe_allow_html=True)
    place_columns = st.columns(min(len(editing_day["places"]), 4), gap="small")
    for index, place in enumerate(editing_day["places"]):
        with place_columns[index % len(place_columns)]:
            label = f"{'✓' if place['included'] else '×'} {place['icon']} {place['name']}"
            if st.button(label, key=f"place_{editing_day['day']}_{place['id']}", use_container_width=True, type="primary" if place["id"] == st.session_state.selected_place else "secondary"):
                st.session_state.selected_place = place["id"]
                st.rerun()

    selected_index = [place["id"] for place in editing_day["places"]].index(st.session_state.selected_place)
    selected_place = get_place(editing_day, st.session_state.selected_place)
    st.markdown(f'<div class="selected-place">선택됨 · {selected_place["icon"]} <b>{selected_place["name"]}</b> &nbsp; {"일정에 포함" if selected_place["included"] else "일정에서 제외됨"}</div>', unsafe_allow_html=True)
    move_left, move_right, include_toggle = st.columns([1, 1, 1.12], gap="small")
    with move_left:
        if st.button("← 이전 장소", key="move_left", use_container_width=True, disabled=selected_index == 0):
            move_selected_place(-1)
            st.rerun()
    with move_right:
        if st.button("다음 장소 →", key="move_right", use_container_width=True, disabled=selected_index == len(editing_day["places"]) - 1):
            move_selected_place(1)
            st.rerun()
    with include_toggle:
        toggle_label = "일정에서 제외" if selected_place["included"] else "일정에 포함"
        if st.button(toggle_label, key="toggle_include", use_container_width=True):
            toggle_selected_place()
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with map_col:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-heading"><span>여행 지도</span><span class="mini-action">DAY별 동선</span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="map-caption">DAY {editing_day["day"]} · {editing_day["area"]} 방문지 마커입니다. 장소 순서를 바꾸면 아래 목록과 마커 순서가 함께 바뀝니다.</div>', unsafe_allow_html=True)

    visible_places = [place for place in editing_day["places"] if place["included"]]
    map_data = pd.DataFrame(
        [
            {"lat": place["lat"], "lon": place["lon"], "size": 7500 + (len(visible_places) - index) * 1200}
            for index, place in enumerate(visible_places)
        ]
    )
    if not map_data.empty:
        st.markdown('<div class="map-wrap">', unsafe_allow_html=True)
        st.map(map_data, latitude="lat", longitude="lon", size="size", zoom=12, use_container_width=True, height=520)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("포함된 장소가 없어 지도에 표시할 마커가 없습니다.")

    legend_html = "".join(
        f'<div class="legend-item"><span class="legend-dot {"violet" if index % 2 else ""}">{index + 1}</span>{place["name"]}</div>'
        for index, place in enumerate(visible_places)
    )
    st.markdown(f'<div class="map-legend">{legend_html}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with chat_col:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-heading"><span>✦ &nbsp; AI Assistant</span><span class="mini-action">online</span></div>', unsafe_allow_html=True)
    st.caption("일정을 수정하거나 여행지·교통 정보를 물어보세요.")
    chat_box = st.container(height=670)
    with chat_box:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

    prompt = st.chat_input("메시지를 입력하세요...", key="travel_chat")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        append_chat_response(prompt)
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
