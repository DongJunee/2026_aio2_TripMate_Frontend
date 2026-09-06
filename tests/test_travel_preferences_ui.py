"""실제 화면 함수에 가짜 API를 연결하여 여행 조건 입력·저장 동작을 검증한다."""

import ast
from datetime import date, timedelta
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from streamlit.testing.v1 import AppTest


FRONTEND = Path(__file__).resolve().parents[1]
SCREEN_SOURCE = (FRONTEND / "streamlit_app.py").read_text(encoding="utf-8")


def screen_definitions(*names: str) -> str:
    """앱의 자동 로그인·서버 조회 없이 테스트할 실제 함수와 상수를 추출한다."""

    nodes = []
    for node in ast.parse(SCREEN_SOURCE).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in names for target in node.targets
        ):
            nodes.append(node)
    return ast.unparse(ast.Module(body=nodes, type_ignores=[]))


SHARED = """
import streamlit as st
from datetime import date, timedelta
from html import escape

class ApiError(Exception):
    pass

def auth_headers():
    return {}

def request_main_scroll_to_top():
    st.session_state.scroll_requested = True

st.session_state.setdefault("requests", [])
""" + screen_definitions(
    "TRAVEL_PARTY_LABELS", "INTENSITY_GUIDE", "BUDGET_GUIDE",
    "render_travel_preference_sliders", "render_create_trip_form",
    "render_trip_preferences_editor", "open_create_trip_form",
)

CREATE_APP = SHARED + """
def api(method, path, **kwargs):
    st.session_state.requests.append({"method": method, "path": path, **kwargs})
    return {"trip": {"id": "created-trip"}, "initial_itinerary_count": 6}

if st.session_state.get("selected_trip_id"):
    st.success("생성 완료")
else:
    render_create_trip_form("test_create")
"""

CREATE_NAVIGATION_APP = SHARED + "\n\n" + screen_definitions(
    "render_sidebar", "render_sidebar_trip"
) + """
st.session_state.setdefault("selected_trip_id", "existing-trip")
st.session_state.setdefault("show_create_trip", False)

def sidebar_profile():
    return "테스트 사용자", "test@example.com"

def trip_activity_sort_key(trip):
    return trip["id"]

def api(method, path, **kwargs):
    st.session_state.requests.append({"method": method, "path": path, **kwargs})
    st.session_state.values_during_request = {
        name: st.session_state[f"create_trip_{name}"]
        for name in ("title", "destination", "dates", "travel_party", "travel_intensity", "budget_level")
    }
    if st.session_state.get("create_fail", False):
        raise ApiError("여행 생성 실패 테스트")
    return {"trip": {"id": "created-trip"}, "initial_itinerary_count": 6}

render_sidebar([{"id": "existing-trip", "title": "기존 여행", "pinned_order": None}])
if st.session_state.show_create_trip:
    render_create_trip_form("create_trip")
else:
    st.success("대시보드")
"""

EDIT_APP = SHARED + """
st.session_state.setdefault("trips", {
    "a": {"id": "a", "travel_party": "family_with_children", "travel_intensity": 1, "budget_level": 5},
    "b": {"id": "b", "travel_party": "senior_couple", "travel_intensity": 5, "budget_level": 1},
})

def api(method, path, **kwargs):
    if st.session_state.get("fail_request"):
        raise ApiError("저장 실패 테스트")
    st.session_state.requests.append({"method": method, "path": path, **kwargs})
    trip_id = path.rsplit("/", 1)[-1]
    st.session_state.trips[trip_id].update(kwargs["json"])
    return st.session_state.trips[trip_id]

trip_id = st.selectbox("테스트 여행", ["a", "b"], key="test_trip")
st.checkbox("저장 실패 재현", key="fail_request")
render_trip_preferences_editor(st.session_state.trips[trip_id])
"""


class TravelPreferencesUiTests(unittest.TestCase):
    def fill_creation_inputs(self, app):
        """모든 생성 입력을 기본값과 다르게 바꿔 초기화 여부를 확인한다."""

        selected_dates = (date(2030, 5, 10), date(2030, 5, 14))
        app.text_input[0].input("부모님과 도쿄")
        app.text_input[1].input("도쿄, 일본")
        app.date_input[0].set_value(selected_dates)
        app.selectbox[0].select("with_parents")
        app.slider[0].set_value(1)
        app.slider[1].set_value(5)
        return {
            "title": "부모님과 도쿄", "destination": "도쿄, 일본", "dates": selected_dates,
            "travel_party": "with_parents", "travel_intensity": 1, "budget_level": 5,
        }

    def assert_creation_inputs(self, app, expected):
        """텍스트·날짜·동행 구성·두 슬라이더가 모두 보존되었는지 확인한다."""

        self.assertEqual(app.text_input[0].value, expected["title"])
        self.assertEqual(app.text_input[1].value, expected["destination"])
        self.assertEqual(tuple(app.date_input[0].value), expected["dates"])
        self.assertEqual(app.selectbox[0].value, expected["travel_party"])
        self.assertEqual([slider.value for slider in app.slider], [expected["travel_intensity"], expected["budget_level"]])

    def test_failed_creation_keeps_all_inputs_during_request_and_after_failure(self):
        """제출 즉시 초기화하지 않고 생성 API 안과 실패 후에 모든 값을 유지한다."""

        app = AppTest.from_string(CREATE_NAVIGATION_APP).run()
        app.session_state["create_fail"] = True
        app.sidebar.button[0].click().run()
        expected = self.fill_creation_inputs(app)
        self.assertFalse(app.get("form")[0].proto.form.clear_on_submit)
        app.main.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertEqual(app.session_state["values_during_request"], expected)
        self.assert_creation_inputs(app, expected)
        self.assertTrue(app.session_state["show_create_trip"])
        self.assertEqual(app.session_state["selected_trip_id"], "existing-trip")

    def test_creation_rerun_and_already_open_sidebar_button_keep_inputs(self):
        """일반 재실행이나 이미 열린 생성 버튼 클릭은 작성 내용을 초기화하지 않는다."""

        app = AppTest.from_string(CREATE_NAVIGATION_APP).run()
        app.sidebar.button[0].click().run()
        expected = self.fill_creation_inputs(app)
        app.run()
        self.assert_creation_inputs(app, expected)
        app.sidebar.button[0].click().run()
        self.assertFalse(app.exception)
        self.assert_creation_inputs(app, expected)
        self.assertEqual(list(app.session_state["requests"]), [])

    def test_success_moves_to_dashboard_and_next_sidebar_entry_resets_inputs(self):
        """성공할 때까지 값을 유지하고 대시보드 이후 새 진입에서 기본값을 표시한다."""

        app = AppTest.from_string(CREATE_NAVIGATION_APP).run()
        app.sidebar.button[0].click().run()
        expected = self.fill_creation_inputs(app)
        app.main.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["values_during_request"], expected)
        self.assertFalse(app.session_state["show_create_trip"])
        self.assertEqual(app.session_state["selected_trip_id"], "created-trip")
        self.assertEqual(len(app.text_input), 0)
        app.sidebar.button[0].click().run()
        self.assertFalse(app.exception)
        self.assert_creation_inputs(app, {
            "title": "", "destination": "",
            "dates": (date.today(), date.today() + timedelta(days=3)),
            "travel_party": "unspecified", "travel_intensity": 3, "budget_level": 3,
        })

    def test_leaving_creation_and_reopening_starts_a_fresh_form(self):
        """다른 여행으로 이동했다가 새 여행 버튼으로 돌아오면 입력을 초기화한다."""

        app = AppTest.from_string(CREATE_NAVIGATION_APP).run()
        app.sidebar.button[0].click().run()
        self.fill_creation_inputs(app)
        app.run()
        app.sidebar.button(key="sidebar_trip_select_existing-trip").click().run()
        self.assertFalse(app.session_state["show_create_trip"])
        app.sidebar.button[0].click().run()
        self.assertFalse(app.exception)
        self.assert_creation_inputs(app, {
            "title": "", "destination": "",
            "dates": (date.today(), date.today() + timedelta(days=3)),
            "travel_party": "unspecified", "travel_intensity": 3, "budget_level": 3,
        })

    def test_create_defaults_and_empty_form_validation(self):
        """기본 단계가 3이며 빈 여행 이름으로는 API가 호출되지 않는다."""

        app = AppTest.from_string(CREATE_APP).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, "unspecified")
        self.assertEqual([slider.value for slider in app.slider], [3, 3])
        self.assertEqual(len(app.text_input), 2)
        self.assertEqual(len(app.date_input), 1)
        captions = " ".join(caption.value for caption in app.caption)
        self.assertIn("일반 날짜 관광·활동", captions)
        self.assertIn("근교 도시 관광은 포함하지", captions)
        self.assertIn("18시 출국은 기본 가정", captions)
        self.assertIn("실제 경로를 계산한 시간이 아니므로", captions)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(list(app.session_state["requests"]), [])
        self.assertTrue(app.error)

    def test_create_submits_party_intensity_budget_and_longer_timeout(self):
        """선택한 조건과 생성 전용 대기 시간을 POST 요청에 보낸다."""

        app = AppTest.from_string(CREATE_APP).run()
        app.text_input[0].input("가족 여행")
        app.text_input[1].input("도쿄")
        app.selectbox[0].select("family_with_children")
        app.slider[0].set_value(2)
        app.slider[1].set_value(4)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        request = app.session_state["requests"][0]
        self.assertEqual((request["method"], request["path"]), ("POST", "/me/trips"))
        self.assertEqual(request["json"]["travel_party"], "family_with_children")
        self.assertEqual(request["json"]["travel_intensity"], 2)
        self.assertEqual(request["json"]["budget_level"], 4)
        self.assertNotIn("timezone", request["json"])
        self.assertEqual(request["timeout"], 180)
        self.assertEqual(app.session_state["selected_trip_id"], "created-trip")

    def test_dashboard_waits_for_submit_and_keeps_saved_values(self):
        """슬라이더만 조작하면 저장하지 않고 제출 후에는 저장값을 다시 표시한다."""

        app = AppTest.from_string(EDIT_APP).run()
        self.assertEqual([slider.value for slider in app.slider], [1, 5])
        self.assertTrue(any("아이 동반 가족" in caption.value for caption in app.caption))
        app.slider[0].set_value(4)
        app.slider[1].set_value(2)
        app.run()
        self.assertEqual(list(app.session_state["requests"]), [])
        app.button[0].click().run()
        self.assertFalse(app.exception)
        request = app.session_state["requests"][0]
        self.assertEqual((request["method"], request["path"]), ("PATCH", "/trips/a"))
        self.assertEqual(request["json"], {"travel_intensity": 4, "budget_level": 2})
        self.assertEqual([slider.value for slider in app.slider], [4, 2])
        self.assertTrue(app.success)
        self.assertTrue(any("자동으로 변경되지" in caption.value for caption in app.caption))

    def test_dashboard_switching_trips_does_not_mix_slider_values(self):
        """다른 여행에는 그 여행에 저장된 강도와 경비가 표시된다."""

        app = AppTest.from_string(EDIT_APP).run()
        app.selectbox[0].select("b").run()
        self.assertFalse(app.exception)
        self.assertEqual([slider.value for slider in app.slider], [5, 1])
        app.slider[0].set_value(2)
        app.slider[1].set_value(4)
        app.button[0].click().run()
        self.assertEqual(app.session_state["requests"][0]["path"], "/trips/b")
        app.selectbox[0].select("a").run()
        self.assertEqual([slider.value for slider in app.slider], [1, 5])

    def test_failed_save_does_not_claim_success_or_replace_saved_settings(self):
        """API 실패 시 오류와 편집값을 유지하고 저장 성공으로 표시하지 않는다."""

        app = AppTest.from_string(EDIT_APP).run()
        app.checkbox[0].check().run()
        app.slider[0].set_value(4)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertFalse(app.success)
        self.assertEqual(app.session_state["trips"]["a"]["travel_intensity"], 1)
        self.assertEqual(app.slider[0].value, 4)

    def test_hotel_placeholder_notes_are_visible_and_html_escaped(self):
        """장소가 없는 숙소 안내도 보이고 안내문 HTML은 실행되지 않는다."""

        from html import escape

        mock_st = MagicMock()
        namespace = {"st": mock_st, "escape": escape, "item_time_text": lambda *_: "시간 미정"}
        exec(screen_definitions("render_itinerary_item_card"), namespace)
        namespace["render_itinerary_item_card"](
            {"title": "체크인", "item_type": "hotel", "notes": "숙소 확인 필요\n<script>x</script>"},
            "Asia/Tokyo",
        )
        html = mock_st.markdown.call_args.args[0]
        self.assertIn("숙소 확인 필요<br>&lt;script&gt;", html)
        self.assertIn("숙소 · 시간 미정", html)
        self.assertNotIn("<script>", html)

    def test_api_timeout_override_and_default(self):
        """기본 요청 대기 시간을 유지하면서 생성 요청에서만 대기 시간을 바꾼다."""

        source = (FRONTEND / "common.py").read_text(encoding="utf-8")
        api_node = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "api")
        mock_httpx = MagicMock()
        mock_httpx.request.return_value.status_code = 200
        namespace = {
            "httpx": mock_httpx, "BACKEND_URL": "https://test.invalid", "HTTP_TIMEOUT": 60,
            "ApiError": RuntimeError, "SessionExpired": RuntimeError,
        }
        exec(ast.unparse(api_node), namespace)
        namespace["api"]("GET", "/me/trips")
        self.assertEqual(mock_httpx.request.call_args.kwargs["timeout"], 60)
        namespace["api"]("POST", "/me/trips", timeout=180, json={"title": "여행"})
        self.assertEqual(mock_httpx.request.call_args.kwargs["timeout"], 180)
        self.assertEqual(mock_httpx.request.call_args.kwargs["json"], {"title": "여행"})


if __name__ == "__main__":
    unittest.main()
