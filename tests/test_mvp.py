"""서버 없이 돌아가는 최소 검사. python3 -m pytest -q tests/"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from app import jev_client, phi_guard, preprocess, render  # noqa: E402

PROTOS = jev_client.load_protocols()
ITEMS = [i for p in PROTOS.values() for i in p["items"]]


@pytest.mark.parametrize("bad", ["연락처 010-1234-5678", "메일 a@b.com", "2024-03-05 발병", "2024년 3월 5일부터",
                                 "주민 900101-1234567", "x" * 301])
def test_phi_guard_rejects(bad):
    with pytest.raises(ValueError):
        phi_guard.check_free_text(bad)


def test_phi_guard_allows_clinical_text():
    assert phi_guard.check_free_text("30분 전 시작된 가슴 압박감, SpO2 95%, 혈압 130/80")


def test_preprocess_never_leaks_raw_values():
    st = preprocess.to_state({"chief_complaint": "chest_pain", "age": 58, "sex": "M", "onset_minutes": 800,
                              "vitals": {"sbp": 85, "hr": 130, "spo2": 90}, "symptoms": "가슴 통증"})
    assert st["age_band"] == "50-64" and "age" not in st
    assert st["onset_over_12h"] is True
    assert st["vitals_flags"] == {"sbp_under_90": True, "sbp_over_180": False, "hr_over_120": True,
                                  "spo2_under_92": True, "temp_over_38": False}
    with pytest.raises(ValueError):
        preprocess.to_state({"chief_complaint": "chest_pain", "age": 30, "name": "홍길동"})


def _answers(p_all, choice="chest_pain"):
    a = {i["id"]: {"noul": p_all} for i in ITEMS}
    a["protocol"] = {"choice": choice, "confidence": 0.9}
    a["urgency"] = {"score": 2.4}
    return a


def test_red_flags_always_shown_even_at_zero_probability():
    plan = render.plan(_answers(0.0), ITEMS)
    shown = {i["id"] for i in plan["items"]}
    assert shown == {i["id"] for i in ITEMS if i["severity"] == "red_flag"}
    assert all(i["level"] == "shown" for i in plan["items"])


def test_high_probability_emphasizes_and_orders_red_flags_first():
    plan = render.plan(_answers(0.95), ITEMS)
    assert len(plan["items"]) == len(ITEMS)
    sevs = [i["severity"] for i in plan["items"]]
    assert sevs == sorted(sevs, key=lambda s: s != "red_flag")
    assert plan["items"][0]["level"] == "emphasized" and plan["urgency"] == "긴급"


def test_ui_text_has_no_forbidden_words_or_raw_probabilities():
    txt = render.to_text(render.plan(_answers(0.87), ITEMS), PROTOS)
    for w in ["진단", "판정", "안전", "0.87", "87%"]:
        assert w not in txt


def test_state_sent_to_jev_is_slimmed_and_pinned(monkeypatch):
    sent = []

    class R:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps({"model": "jev-1.13.0", "answers": _answers(0.5)}).encode()
    def fake_open(req, timeout):
        sent.append(json.loads(req.data)); return R()
    monkeypatch.setattr(jev_client.urllib.request, "urlopen", fake_open)
    jev_client.evaluate({"chief_complaint": "chest_pain", "age_band": "50-64", "sex": "M", "onset_over_12h": False,
                         "vitals_flags": {}, "symptoms": "x", "risk_factors": [], "extra_junk": 1}, PROTOS, ITEMS)
    head, body = sent
    assert head["model"] == body["model"] == "jev-1.13.0"
    assert set(head["state"]) == {"chief_complaint", "symptoms"} and set(body["state"]) == {"symptoms"}
    assert set(head["questions"]) == {"protocol", "urgency"} and "other" in head["questions"]["protocol"]["criteria"]
    assert set(body["questions"]) == {i["id"] for i in ITEMS if "state_flag" not in i and i["protocol_id"] == "chest_pain"}


def test_state_flag_items_answered_by_code(monkeypatch):
    class R:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps({"model": "jev-1.13.0", "answers": _answers(0.5)}).encode()
    monkeypatch.setattr(jev_client.urllib.request, "urlopen", lambda req, timeout: R())
    st = {"chief_complaint": "chest_pain", "onset_over_12h": True, "vitals_flags": {"sbp_under_90": True},
          "symptoms": "x", "risk_factors": [], "age_band": "50-64"}
    a = jev_client.evaluate(st, PROTOS, ITEMS)
    assert a["cp_rf_006"]["noul"] == 1.0 and a["cp_rt_005"]["noul"] == 1.0 and a["cp_rf_007"]["noul"] == 0.0
    st["risk_factors"] = ["diabetes"]
    a = jev_client.evaluate(st, PROTOS, ITEMS)
    assert a["cp_im_012"]["noul"] == 1.0 and a["cp_im_013"]["noul"] == 0.0


def test_only_chosen_protocol_items_asked_unless_uncertain(monkeypatch):
    calls = []

    def fake(state, questions):
        calls.append(questions)
        if "protocol" in questions:
            return {"protocol": {"choice": CHOICE, "confidence": CONF}, "urgency": {"score": 1.0}}
        return {k: {"noul": 0.1} for k in questions}
    monkeypatch.setattr(jev_client, "_post", fake)
    st = {"chief_complaint": "chest_pain", "symptoms": "x", "vitals_flags": {}, "risk_factors": [], "age_over_50": False}

    CHOICE, CONF = "chest_pain", 0.9
    a = jev_client.evaluate(st, PROTOS, ITEMS)
    p = render.plan(a, ITEMS)
    assert all(k.startswith("cp_") for k in calls[1]) and all(i["protocol_id"] == "chest_pain" for i in p["items"])
    assert {i["id"] for i in p["items"]} == {i["id"] for i in ITEMS if i["protocol_id"] == "chest_pain" and i["severity"] == "red_flag"}

    CHOICE, CONF, calls[:] = "other", 0.9, []
    p = render.plan(jev_client.evaluate(st, PROTOS, ITEMS), ITEMS)
    assert p["protocol_uncertain"]
    assert {i["id"] for i in p["items"]} == {i["id"] for i in ITEMS if i["severity"] == "red_flag"}


def test_checklist_validates_in_draft_mode():
    r = subprocess.run([sys.executable, "scripts/validate_checklist.py", "checklists/", "--allow-unverified"],
                       capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    assert r.returncode == 0, r.stdout


def test_eval_cases_reference_existing_items():
    ids = {i["id"] for i in ITEMS}
    for f in (Path(__file__).parent.parent / "eval/cases").glob("*.jsonl"):
        rows = [json.loads(l) for l in open(f)]
        assert len(rows) >= 30, f.name
        assert all(e in ids for r in rows for e in r["expected_items"]), f.name


def test_age_over_50_flag_answered_by_code(monkeypatch):
    class R:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps({"model": "jev-1.13.0", "answers": _answers(0.5, "headache")}).encode()
    monkeypatch.setattr(jev_client.urllib.request, "urlopen", lambda req, timeout: R())
    st = preprocess.to_state({"chief_complaint": "headache", "age": 67, "symptoms": "두통"})
    assert st["age_over_50"] is True and "age" not in st
    assert jev_client.evaluate(st, PROTOS, ITEMS)["hd_rf_008"]["noul"] == 1.0


def test_web_check_strips_probabilities_and_rejects_phi(monkeypatch):
    from app import web
    monkeypatch.setattr(web.jev_client, "evaluate", lambda *a: _answers(0.9))
    plan = web.check({"chief_complaint": "chest_pain", "age": 58, "symptoms": "가슴 통증"})
    assert plan["items"] and all("p" not in i for i in plan["items"])
    with pytest.raises(ValueError):
        web.check({"chief_complaint": "chest_pain", "age": 58, "symptoms": "a@b.com"})
