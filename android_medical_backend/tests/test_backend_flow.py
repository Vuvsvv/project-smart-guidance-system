from __future__ import annotations

import unittest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.schemas import RecommendationItem, TriageCase
from app.services import appointment_service, rag_triage_adapter
from app.services.appointment_service import detect_department_result, recommend_appointments
from app.services.case_store import get_case
from app.services.rule_engine import apply_user_message, evaluate_urgency, next_question_for
from app.services.script_service import build_navigation_script


class BackendFlowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_departments = appointment_service.fetch_active_departments
        self.original_rag_complete = rag_triage_adapter.complete_prompt
        self.original_rag_settings = rag_triage_adapter.get_settings
        appointment_service.fetch_active_departments = lambda: [
            {"parent_dept": "外科系", "child_dept": "一般骨科"},
            {"parent_dept": "一般內科", "child_dept": "一般內科"},
        ]

        async def fail_complete(_: str) -> str:
            raise RuntimeError("llm disabled in tests")

        rag_triage_adapter.complete_prompt = fail_complete

    def tearDown(self):
        appointment_service.fetch_active_departments = self.original_departments
        rag_triage_adapter.complete_prompt = self.original_rag_complete
        rag_triage_adapter.get_settings = self.original_rag_settings

    async def test_knee_pain_triage_case(self):
        case = TriageCase(case_id="case_knee")
        apply_user_message(case, "左膝痛2週，爬樓梯很吃力，沒有胸痛呼吸困難意識不清大量出血，週一上午可以看診")
        case.triage = evaluate_urgency(case)

        self.assertEqual(case.patient_input.body_part, "膝")
        self.assertEqual(case.triage.urgency_level, "medium")
        self.assertFalse(case.triage.need_more_info)
        self.assertTrue(case.triage.reasons)
        self.assertIn("body_part", case.patient_input.collected_fields)

    async def test_high_urgency_red_flag(self):
        case = TriageCase(case_id="case_high")
        apply_user_message(case, "突發胸痛而且呼吸困難")
        case.triage = evaluate_urgency(case)

        self.assertEqual(case.triage.urgency_score, 90)
        self.assertEqual(case.triage.urgency_level, "high")
        self.assertTrue(case.triage.warning_required)
        self.assertTrue(case.triage.is_final)
        self.assertTrue(case.triage.reasons)

    async def test_db_failure_falls_back_to_mock_schedule(self):
        original_create = db.create_db_connection
        db.create_db_connection = lambda: (_ for _ in ()).throw(RuntimeError("db down"))
        try:
            slots = db.fetch_available_slots("一般骨科", max_slots=2)
        finally:
            db.create_db_connection = original_create

        self.assertGreaterEqual(len(slots), 1)
        self.assertEqual(slots[0]["source"], "mock")

    async def test_db_empty_slots_falls_back_to_mock_schedule(self):
        original_fetch_db = db._fetch_available_slots_from_db
        db._fetch_available_slots_from_db = lambda *_, **__: []
        try:
            slots = db.fetch_available_slots("一般骨科", max_slots=2)
        finally:
            db._fetch_available_slots_from_db = original_fetch_db

        self.assertGreaterEqual(len(slots), 1)
        self.assertEqual(slots[0]["source"], "mock")

    async def test_ai_department_failure_uses_rule_based_department(self):
        case = TriageCase(case_id="case_ai_fail")
        apply_user_message(case, "膝蓋痛2週，爬樓梯吃力，週一上午")
        result = await detect_department_result(case)

        self.assertEqual(result.childDept, "一般骨科")
        self.assertGreaterEqual(result.confidence, 0.4)

    async def test_rag_adapter_department_uses_db_constrained_ai_result(self):
        class FakeSettings:
            google_api_key = "test-key"

        async def fake_complete(_: str) -> str:
            return """
            {
              "childDept": "一般骨科",
              "confidence": 0.88,
              "reason": ["膝蓋疼痛與爬樓梯困難符合骨科評估"]
            }
            """

        rag_triage_adapter.get_settings = lambda: FakeSettings()
        rag_triage_adapter.complete_prompt = fake_complete

        case = TriageCase(case_id="case_rag_dept")
        apply_user_message(case, "左膝痛2週，爬樓梯很吃力")
        result = await rag_triage_adapter.detect_department_with_ai(
            case,
            [
                {"parent_dept": "外科系", "child_dept": "一般骨科"},
                {"parent_dept": "一般內科", "child_dept": "一般內科"},
            ],
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.childDept, "一般骨科")
        self.assertEqual(result.parentDept, "外科系")
        self.assertGreaterEqual(result.confidence, 0.8)
        self.assertTrue(any("rag_demo adapter" in reason for reason in result.reason))

    async def test_rag_adapter_rejects_department_not_in_db_list(self):
        class FakeSettings:
            google_api_key = "test-key"

        async def fake_complete(_: str) -> str:
            return '{"childDept": "不存在科", "confidence": 0.99, "reason": ["AI invented a department"]}'

        rag_triage_adapter.get_settings = lambda: FakeSettings()
        rag_triage_adapter.complete_prompt = fake_complete

        case = TriageCase(case_id="case_rag_reject")
        apply_user_message(case, "左膝痛2週")
        result = await rag_triage_adapter.detect_department_with_ai(
            case,
            [{"parent_dept": "外科系", "child_dept": "一般骨科"}],
        )

        self.assertIsNone(result)

    async def test_rag_adapter_can_refine_patient_input_without_changing_schema(self):
        class FakeSettings:
            google_api_key = "test-key"

        async def fake_complete(_: str) -> str:
            return """
            {
              "patient_input": {
                "symptom": "左膝痛",
                "body_part": "膝",
                "duration": "2週",
                "severity": "中等",
                "onset": "漸進",
                "accompanying_symptoms": ["爬樓梯吃力"],
                "red_flags": []
              },
              "triage": {
                "urgency_score": 50,
                "urgency_level": "medium",
                "warning_required": false,
                "warning_message": null,
                "need_more_info": true,
                "next_question": "是否有紅腫熱痛或發燒？",
                "reasons": ["資料仍需確認伴隨症狀"],
                "is_final": false
              },
              "reply": "是否有紅腫熱痛或發燒？"
            }
            """

        rag_triage_adapter.get_settings = lambda: FakeSettings()
        rag_triage_adapter.complete_prompt = fake_complete

        case = TriageCase(case_id="case_rag_refine")
        apply_user_message(case, "膝蓋不舒服")
        suggestion = await rag_triage_adapter.refine_case_with_ai(case)

        self.assertIsNotNone(suggestion)
        self.assertEqual(case.patient_input.body_part, "膝")
        self.assertEqual(case.patient_input.duration, "2週")
        self.assertIn("爬樓梯吃力", case.patient_input.accompanying_symptoms)
        self.assertEqual(suggestion.triage.next_question, "是否有紅腫熱痛或發燒？")

    async def test_recommendations_are_capped_at_five_per_column(self):
        original_fetch = appointment_service.fetch_available_slots
        today = date.today()

        def fake_slots(*_, **__):
            return [
                {
                    "parent_dept": "外科系",
                    "child_dept": "一般骨科",
                    "doctor": f"測試醫師{i}",
                    "date": today + timedelta(days=i),
                    "session": "上午",
                    "slot": f"32{i:02d}診",
                }
                for i in range(8)
            ]

        appointment_service.fetch_available_slots = fake_slots
        try:
            case = TriageCase(case_id="case_recommend")
            apply_user_message(case, "左膝痛2週，爬樓梯很吃力，週一上午")
            case.department_result = await detect_department_result(case)
            result = await recommend_appointments(case)
        finally:
            appointment_service.fetch_available_slots = original_fetch

        self.assertGreaterEqual(len(result.recommendations.specialty_first), 1)
        self.assertLessEqual(len(result.recommendations.specialty_first), 5)
        self.assertGreaterEqual(len(result.recommendations.time_first), 1)
        self.assertLessEqual(len(result.recommendations.time_first), 5)
        self.assertEqual(result.recommendations.specialty_first[0].rank, 1)
        self.assertTrue(result.recommendations.specialty_first[0].is_best_match)
        self.assertLessEqual(result.total_count, 10)

    async def test_fallback_department_is_present(self):
        case = TriageCase(case_id="case_fallback")
        apply_user_message(case, "左膝痛2週，爬樓梯很吃力，週一上午")
        case.department_result = await detect_department_result(case)
        result = await recommend_appointments(case)

        self.assertTrue(result.fallback_departments)

    async def test_script_template_applies_recommendation(self):
        item = RecommendationItem(
            recommendation_id="rec_test",
            parentDept="外科系",
            childDept="一般骨科",
            doctor="邱方遙",
            date="2026-05-18",
            session="上午",
            slot="3209診",
            score=95,
            reasons=["專長最符合"],
        )

        steps = build_navigation_script(item)

        self.assertEqual(steps[0].action, "open_app")
        self.assertEqual(steps[4].target, "外科系")
        self.assertEqual(steps[5].target, "一般骨科")
        self.assertEqual(steps[8].target, "3209診邱方遙")
        self.assertEqual(steps[8].text, "3209診邱方遙")
        self.assertGreaterEqual(steps[8].retry, 1)

    async def test_incomplete_triage_case_is_rejected_by_recommend(self):
        client = TestClient(app)
        response = client.post(
            "/recommend",
            json={
                "triage_case": {
                    "case_id": "case_incomplete",
                    "patient_input": {"symptom": "膝蓋痛"},
                    "triage": {"need_more_info": True},
                    "conversation_state": {"stage": "collecting", "is_complete": False},
                }
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("請先完成 /chat", response.json()["detail"])

    async def test_completed_triage_waits_for_confirmation_before_recommend(self):
        client = TestClient(app)
        chat_response = client.post(
            "/chat",
            json={"message": "左膝痛2週，爬樓梯很吃力，沒有胸痛呼吸困難意識不清大量出血，週一上午可以看診"},
        )
        self.assertEqual(chat_response.status_code, 200)
        chat_data = chat_response.json()
        self.assertEqual(chat_data["conversation_state"]["stage"], "waiting_confirmation")
        self.assertTrue(chat_data["conversation_state"]["awaiting_confirmation"])
        self.assertFalse(chat_data["conversation_state"]["confirmed"])
        self.assertTrue(chat_data["triage_reasons"])

        recommend_response = client.post("/recommend", json={"case_id": chat_data["case_id"]})
        self.assertEqual(recommend_response.status_code, 400)
        self.assertIn("尚未確認", recommend_response.json()["detail"])

        confirm_response = client.post(
            "/chat",
            json={"case_id": chat_data["case_id"], "confirmed": True},
        )
        self.assertEqual(confirm_response.status_code, 200)
        confirm_data = confirm_response.json()
        self.assertEqual(confirm_data["conversation_state"]["stage"], "recommending")
        self.assertTrue(confirm_data["conversation_state"]["confirmed"])
        self.assertFalse(confirm_data["conversation_state"]["awaiting_confirmation"])

    async def test_short_red_flag_denial_does_not_repeat_red_flag_question(self):
        client = TestClient(app)
        first_response = client.post(
            "/chat",
            json={"message": "左膝痛2週，爬樓梯很吃力"},
        )
        self.assertEqual(first_response.status_code, 200)
        first_data = first_response.json()
        self.assertEqual(first_data["conversation_state"]["last_question_key"], "red_flags")

        second_response = client.post(
            "/chat",
            json={"case_id": first_data["case_id"], "message": "沒有"},
        )
        self.assertEqual(second_response.status_code, 200)
        second_data = second_response.json()

        patient_input = second_data["triage_case"]["patient_input"]
        self.assertTrue(patient_input["red_flags_checked"])
        self.assertEqual(patient_input["red_flags"], [])
        self.assertNotEqual(second_data["conversation_state"]["last_question_key"], "red_flags")
        self.assertNotIn("突發胸痛", second_data.get("next_question") or "")

    async def test_all_negative_red_flags_consumes_field_and_does_not_repeat(self):
        client = TestClient(app)
        first_response = client.post(
            "/chat",
            json={"message": "膝蓋痛一週，爬樓梯很吃力"},
        )
        self.assertEqual(first_response.status_code, 200)
        first_data = first_response.json()
        self.assertEqual(first_data["conversation_state"]["last_question_key"], "red_flags")

        second_response = client.post(
            "/chat",
            json={"case_id": first_data["case_id"], "message": "都沒有"},
        )
        self.assertEqual(second_response.status_code, 200)
        second_data = second_response.json()

        self.assertTrue(second_data["triage_case"]["patient_input"]["red_flags_checked"])
        self.assertEqual(second_data["triage_case"]["patient_input"]["red_flags"], [])
        self.assertIn("red_flags", second_data["conversation_state"]["consumed_fields"])
        self.assertNotEqual(second_data["conversation_state"]["last_question_key"], "red_flags")
        self.assertNotIn("突發胸痛", second_data.get("next_question") or "")

    async def test_detailed_red_flag_denial_reaches_waiting_confirmation(self):
        client = TestClient(app)
        response = client.post(
            "/chat",
            json={
                "message": "左膝痛2週，爬樓梯很吃力，沒有突發胸痛，沒有呼吸困難，沒有意識不清，沒有大量出血，沒有半邊無力或劇烈頭痛，週一上午可以看診"
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["conversation_state"]["stage"], "waiting_confirmation")
        self.assertFalse(data["needMoreInfo"])
        self.assertTrue(data["triage_case"]["patient_input"]["red_flags_checked"])
        self.assertEqual(data["triage_case"]["patient_input"]["red_flags"], [])
        self.assertIsNone(data["next_question"])

    async def test_ai_question_does_not_override_deterministic_red_flag_state(self):
        class FakeSettings:
            google_api_key = "test-key"

        async def fake_complete(_: str) -> str:
            return """
            {
              "patient_input": {
                "red_flags": []
              },
              "triage": {
                "urgency_score": 20,
                "urgency_level": "low",
                "warning_required": false,
                "warning_message": null,
                "need_more_info": true,
                "next_question": "請問是否有突發胸痛或呼吸困難？",
                "reasons": ["AI 建議再問紅旗"],
                "is_final": false
              },
              "reply": "請問是否有突發胸痛或呼吸困難？"
            }
            """

        rag_triage_adapter.get_settings = lambda: FakeSettings()
        rag_triage_adapter.complete_prompt = fake_complete

        client = TestClient(app)
        first_response = client.post(
            "/chat",
            json={"message": "左膝痛2週，爬樓梯很吃力"},
        )
        first_data = first_response.json()

        second_response = client.post(
            "/chat",
            json={"case_id": first_data["case_id"], "message": "沒有"},
        )
        self.assertEqual(second_response.status_code, 200)
        second_data = second_response.json()

        self.assertTrue(second_data["triage_case"]["patient_input"]["red_flags_checked"])
        self.assertNotEqual(second_data["conversation_state"]["last_question_key"], "red_flags")
        self.assertNotIn("突發胸痛", second_data.get("next_question") or "")

    async def test_all_available_answer_moves_from_days_to_sessions(self):
        client = TestClient(app)
        first_response = client.post(
            "/chat",
            json={"message": "左膝痛2週，爬樓梯很吃力，沒有胸痛呼吸困難意識不清大量出血"},
        )
        self.assertEqual(first_response.status_code, 200)
        first_data = first_response.json()
        self.assertEqual(first_data["conversation_state"]["last_question_key"], "preferred_days")

        second_response = client.post(
            "/chat",
            json={"case_id": first_data["case_id"], "message": "都有空"},
        )
        self.assertEqual(second_response.status_code, 200)
        second_data = second_response.json()

        availability = second_data["triage_case"]["availability"]
        self.assertEqual(
            availability["preferred_days"],
            ["週一", "週二", "週三", "週四", "週五", "週六", "週日"],
        )
        self.assertEqual(second_data["conversation_state"]["last_question_key"], "preferred_sessions")
        self.assertNotIn("哪幾天", second_data.get("next_question") or "")

    async def test_weekday_range_and_morning_session_reach_waiting_confirmation(self):
        client = TestClient(app)
        first_response = client.post(
            "/chat",
            json={"message": "左膝痛2週，爬樓梯很吃力，沒有胸痛呼吸困難意識不清大量出血"},
        )
        self.assertEqual(first_response.status_code, 200)
        first_data = first_response.json()

        days_response = client.post(
            "/chat",
            json={"case_id": first_data["case_id"], "message": "週一到週五可以"},
        )
        self.assertEqual(days_response.status_code, 200)
        days_data = days_response.json()
        self.assertEqual(days_data["conversation_state"]["last_question_key"], "preferred_sessions")
        self.assertEqual(
            days_data["triage_case"]["availability"]["preferred_days"],
            ["週一", "週二", "週三", "週四", "週五"],
        )

        session_response = client.post(
            "/chat",
            json={"case_id": first_data["case_id"], "message": "早上比較方便"},
        )
        self.assertEqual(session_response.status_code, 200)
        session_data = session_response.json()

        self.assertEqual(session_data["conversation_state"]["stage"], "waiting_confirmation")
        self.assertFalse(session_data["needMoreInfo"])
        self.assertEqual(session_data["triage_case"]["availability"]["preferred_sessions"], ["上午"])
        self.assertIsNone(session_data["next_question"])

    async def test_ai_question_does_not_override_deterministic_availability_state(self):
        class FakeSettings:
            google_api_key = "test-key"

        async def fake_complete(_: str) -> str:
            return """
            {
              "patient_input": {},
              "triage": {
                "urgency_score": 20,
                "urgency_level": "low",
                "warning_required": false,
                "warning_message": null,
                "need_more_info": true,
                "next_question": "請問你最近哪幾天有空就醫？",
                "reasons": ["AI 建議再問日期"],
                "is_final": false
              },
              "reply": "請問你最近哪幾天有空就醫？"
            }
            """

        rag_triage_adapter.get_settings = lambda: FakeSettings()
        rag_triage_adapter.complete_prompt = fake_complete

        client = TestClient(app)
        first_response = client.post(
            "/chat",
            json={"message": "左膝痛2週，爬樓梯很吃力，沒有胸痛呼吸困難意識不清大量出血"},
        )
        first_data = first_response.json()

        second_response = client.post(
            "/chat",
            json={"case_id": first_data["case_id"], "message": "我這幾天都有空"},
        )
        self.assertEqual(second_response.status_code, 200)
        second_data = second_response.json()

        self.assertEqual(second_data["conversation_state"]["last_question_key"], "preferred_sessions")
        self.assertNotIn("哪幾天", second_data.get("next_question") or "")

    async def test_uncertain_all_available_answer_does_not_loop(self):
        client = TestClient(app)
        first_response = client.post(
            "/chat",
            json={"message": "左膝痛2週，爬樓梯很吃力，沒有胸痛呼吸困難意識不清大量出血"},
        )
        first_data = first_response.json()
        self.assertEqual(first_data["conversation_state"]["last_question_key"], "preferred_days")

        second_response = client.post(
            "/chat",
            json={"case_id": first_data["case_id"], "message": "都可以吧"},
        )
        self.assertEqual(second_response.status_code, 200)
        second_data = second_response.json()

        self.assertEqual(second_data["conversation_state"]["last_question_key"], "preferred_sessions")
        self.assertEqual(
            second_data["triage_case"]["availability"]["preferred_days"],
            ["週一", "週二", "週三", "週四", "週五", "週六", "週日"],
        )
        self.assertGreaterEqual(
            second_data["conversation_state"]["field_confidence"]["preferred_days"],
            0.55,
        )

    async def test_mixed_availability_answer_consumes_days_and_does_not_loop(self):
        client = TestClient(app)
        first_response = client.post(
            "/chat",
            json={"message": "膝蓋痛1週，爬樓梯很吃力，沒有胸痛呼吸困難意識不清大量出血"},
        )
        self.assertEqual(first_response.status_code, 200)
        first_data = first_response.json()
        self.assertEqual(first_data["conversation_state"]["last_question_key"], "preferred_days")

        second_response = client.post(
            "/chat",
            json={"case_id": first_data["case_id"], "message": "都可以？我最近沒上班"},
        )
        self.assertEqual(second_response.status_code, 200)
        second_data = second_response.json()

        self.assertIn("preferred_days", second_data["conversation_state"]["consumed_fields"])
        self.assertEqual(second_data["conversation_state"]["field_statuses"]["preferred_days"], "available")
        self.assertEqual(
            second_data["triage_case"]["availability"]["preferred_days"],
            ["週一", "週二", "週三", "週四", "週五", "週六", "週日"],
        )
        self.assertNotIn("最近哪幾天", second_data.get("next_question") or "")

    async def test_unknown_answer_falls_back_after_two_attempts(self):
        client = TestClient(app)
        first_response = client.post(
            "/chat",
            json={"message": "左膝痛2週，沒有胸痛呼吸困難意識不清大量出血"},
        )
        first_data = first_response.json()
        self.assertEqual(first_data["conversation_state"]["last_question_key"], "severity")

        second_response = client.post(
            "/chat",
            json={"case_id": first_data["case_id"], "message": "不知道"},
        )
        second_data = second_response.json()
        self.assertEqual(second_data["conversation_state"]["last_question_key"], "severity")
        self.assertEqual(second_data["conversation_state"]["question_attempts"]["severity"], 2)

        third_response = client.post(
            "/chat",
            json={"case_id": first_data["case_id"], "message": "不知道"},
        )
        self.assertEqual(third_response.status_code, 200)
        third_data = third_response.json()

        self.assertEqual(third_data["triage_case"]["patient_input"]["severity"], "unknown")
        self.assertEqual(third_data["conversation_state"]["field_statuses"]["severity"], "unknown")
        self.assertEqual(third_data["conversation_state"]["question_attempts"]["severity"], 2)
        self.assertIn("severity", third_data["conversation_state"]["consumed_fields"])
        self.assertEqual(third_data["conversation_state"]["last_question_key"], "preferred_days")

    async def test_consumed_field_is_not_selected_by_next_question_for(self):
        case = TriageCase(case_id="case_consumed_gate")
        case.patient_input.symptom = "膝蓋痛"
        case.conversation_state.consumed_fields.append("red_flags")

        question = next_question_for(case)

        self.assertEqual(case.conversation_state.last_question_key, "body_part")
        self.assertNotIn("突發胸痛", question or "")

    async def test_mild_pain_with_work_capacity_is_normalized(self):
        case = TriageCase(case_id="case_mild_semantic")
        apply_user_message(case, "有點痛但能工作")

        normalized = case.patient_input.severity_normalized
        self.assertEqual(normalized.severity_level, "mild")
        self.assertFalse(normalized.functional_impact)
        self.assertFalse(normalized.sleep_impact)
        self.assertGreaterEqual(normalized.confidence, 0.7)

    async def test_sleep_impact_raises_severity_confidence(self):
        case = TriageCase(case_id="case_sleep_semantic")
        apply_user_message(case, "痛到睡不著")
        case.triage = evaluate_urgency(case)

        normalized = case.patient_input.severity_normalized
        self.assertEqual(normalized.severity_level, "severe")
        self.assertTrue(normalized.sleep_impact)
        self.assertGreaterEqual(normalized.confidence, 0.9)
        self.assertGreaterEqual(case.triage.urgency_score, 30)

    async def test_negated_red_flags_are_structured_and_do_not_loop(self):
        client = TestClient(app)
        first_response = client.post(
            "/chat",
            json={"message": "左膝痛2週"},
        )
        first_data = first_response.json()
        self.assertEqual(first_data["conversation_state"]["last_question_key"], "red_flags")

        second_response = client.post(
            "/chat",
            json={"case_id": first_data["case_id"], "message": "沒有胸痛也沒有呼吸困難"},
        )
        self.assertEqual(second_response.status_code, 200)
        second_data = second_response.json()

        self.assertTrue(second_data["triage_case"]["patient_input"]["red_flags_checked"])
        self.assertEqual(second_data["triage_case"]["patient_input"]["red_flags"], [])
        self.assertNotEqual(second_data["conversation_state"]["last_question_key"], "red_flags")
        self.assertEqual(second_data["conversation_state"]["field_statuses"]["red_flags"], "unavailable")

    async def test_ai_semantic_suggestion_does_not_override_deterministic_next_question(self):
        class FakeSettings:
            google_api_key = "test-key"

        async def fake_complete(_: str) -> str:
            return """
            {
              "semantic_extractions": [
                {
                  "field": "preferred_days",
                  "normalized_value": [],
                  "semantic_status": "unknown",
                  "confidence": 0.1,
                  "source_text": "AI wants to ask days again",
                  "needs_clarification": true,
                  "follow_up_reason": "AI suggests asking date"
                }
              ],
              "patient_input": {},
              "triage": {
                "urgency_score": 20,
                "urgency_level": "low",
                "warning_required": false,
                "warning_message": null,
                "need_more_info": true,
                "next_question": "請問你最近哪幾天有空就醫？",
                "reasons": ["AI 建議重問日期"],
                "is_final": false
              },
              "reply": "請問你最近哪幾天有空就醫？"
            }
            """

        rag_triage_adapter.get_settings = lambda: FakeSettings()
        rag_triage_adapter.complete_prompt = fake_complete

        client = TestClient(app)
        first_response = client.post(
            "/chat",
            json={"message": "左膝痛2週，爬樓梯很吃力，沒有胸痛呼吸困難意識不清大量出血"},
        )
        first_data = first_response.json()

        second_response = client.post(
            "/chat",
            json={"case_id": first_data["case_id"], "message": "都可以吧"},
        )
        self.assertEqual(second_response.status_code, 200)
        second_data = second_response.json()

        self.assertEqual(second_data["conversation_state"]["last_question_key"], "preferred_sessions")
        self.assertNotIn("哪幾天", second_data.get("next_question") or "")
        self.assertTrue(second_data["triage_case"]["semantic_extractions"])

    async def test_full_chat_recommend_generate_script_flow(self):
        client = TestClient(app)

        chat_response = client.post(
            "/chat",
            json={"message": "左膝痛2週，爬樓梯很吃力，沒有胸痛呼吸困難意識不清大量出血，週一上午可以看診"},
        )
        self.assertEqual(chat_response.status_code, 200)
        chat_data = chat_response.json()
        self.assertFalse(chat_data["triage"]["need_more_info"])
        self.assertTrue(chat_data["conversation_state"]["is_complete"])
        self.assertEqual(chat_data["conversation_state"]["stage"], "waiting_confirmation")

        confirm_response = client.post(
            "/chat",
            json={"case_id": chat_data["case_id"], "confirmed": True},
        )
        self.assertEqual(confirm_response.status_code, 200)

        recommend_response = client.post(
            "/recommend",
            json={"case_id": chat_data["case_id"]},
        )
        self.assertEqual(recommend_response.status_code, 200)
        recommend_data = recommend_response.json()
        specialty_first = recommend_data["recommendations"]["specialty_first"]
        time_first = recommend_data["recommendations"]["time_first"]
        self.assertGreaterEqual(len(specialty_first), 1)
        self.assertGreaterEqual(len(time_first), 1)

        script_response = client.post(
            "/generate_script",
            json={
                "case_id": chat_data["case_id"],
                "recommendation_id": specialty_first[0]["recommendation_id"],
            },
        )
        self.assertEqual(script_response.status_code, 200)
        script_data = script_response.json()
        self.assertEqual(script_data["script_id"], "vgh_booking_001")
        self.assertEqual(script_data["recommendation"]["recommendation_id"], specialty_first[0]["recommendation_id"])
        self.assertEqual(script_data["recommendation"]["doctor"], specialty_first[0]["doctor"])
        self.assertGreaterEqual(len(script_data["steps"]), 1)
        self.assertEqual(script_data["step_count"], len(script_data["steps"]))

        saved_case = get_case(chat_data["case_id"])
        self.assertIsNotNone(saved_case)
        self.assertEqual(saved_case.selected_recommendation_id, specialty_first[0]["recommendation_id"])
        self.assertEqual(saved_case.conversation_state.stage, "script_ready")


if __name__ == "__main__":
    unittest.main()
