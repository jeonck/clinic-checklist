"""system_one 단일 호출: 프로토콜 Choice + 긴급도 Score + 항목별 Noul, 전부 한 요청.

TYPESAFE_BASE_URL 기본값은 로컬 open-jev. 유료 API로 바꿀 때 env만 바꾼다.
"""
import hashlib
import json
import logging
import os
import urllib.request
from pathlib import Path

MODEL = "jev-1.13.0"  # 버전 고정. jev-latest 금지.
BASE_URL = os.environ.get("TYPESAFE_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.environ.get("TYPESAFE_API_KEY", "local")
URGENCY_LEVELS = ["Routine", "Soon (within hours)", "Urgent", "Immediate"]
LOW_CONFIDENCE_PROTOCOL = 0.50
log = logging.getLogger("jev")


def load_protocols(root=Path(__file__).parent.parent / "checklists", production=False) -> dict:
    protos = {}
    for f in sorted(root.glob("*.json")):
        p = json.loads(f.read_text(encoding="utf-8"))
        if production:  # 미검증 출처 항목은 배포 빌드에서 제외
            p["items"] = [i for i in p["items"] if i["source"]["verified_by"]]
        for i in p["items"]:
            i["protocol_id"] = p["protocol_id"]
        protos[p["protocol_id"]] = p
    return protos


def _post(state: dict, questions: dict) -> dict:
    body = json.dumps({"state": state, "model": MODEL, "questions": questions}).encode()
    req = urllib.request.Request(f"{BASE_URL}/v1/systemone", body,
                                 {"content-type": "application/json", "authorization": f"Bearer {API_KEY}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.load(r)
    # 로그: state 해시 + 모델 + 확률만. 원문은 남기지 않는다.
    log.info(json.dumps({
        "state_sha256": hashlib.sha256(body).hexdigest()[:16], "model": resp.get("model"),
        "p": {k: round(a.get("noul", a.get("score", 0)), 3) if isinstance(a.get("noul", a.get("score")), (int, float))
              else a.get("choice") for k, a in resp["answers"].items()},
    }))
    return resp["answers"]


def evaluate(state: dict, protocols: dict, items: list) -> dict:
    # 요청 2개: 프로토콜/긴급도는 주호소가 필요하고, Noul은 증상 외 필드가 들어가면 FP가 2배로 뛴다
    # (2026-09-21 로컬 gemma-3-4b 평가). 질문 단위 비용이라 요청 분할의 지연 비용은 거의 0.
    answers = _post({"chief_complaint": state["chief_complaint"], "symptoms": state["symptoms"]}, {
        "protocol": {"type": "choice",
                     "instructions": "Which clinical presentation best matches the chief complaint",
                     "criteria": {**{k: p["choice_description"] for k, p in protocols.items()},
                                  "other": "None of the listed presentations"}},
        "urgency": {"type": "score",
                    "instructions": "How urgently this patient needs physician evaluation",
                    "criteria": URGENCY_LEVELS},
    })
    # 선택된 프로토콜의 항목만 묻는다. 프로토콜이 불확실하면 모든 프로토콜의 red flag를 묻는다 (clinical-safety §1).
    proto = answers["protocol"]
    uncertain = proto["choice"] not in protocols or proto["confidence"] < LOW_CONFIDENCE_PROTOCOL
    items = [it for it in items
             if it["protocol_id"] == proto["choice"] or (uncertain and it["severity"] == "red_flag")]
    asked = [it for it in items if "state_flag" not in it]  # 불리언 플래그·병력 리스트는 코드가 답한다
    needed = {f for it in asked for f in it["requires_state"]}
    answers.update(_post({k: v for k, v in state.items() if k in needed},
                         {it["id"]: {"type": "noul", "instructions": it["jev_question"]} for it in asked}))
    for it in items:  # state_flag 항목: 전처리가 이미 계산한 불리언 → 확률 1.0/0.0
        if "state_flag" in it:
            v = state
            for k in it["state_flag"].split("."):  # dict → 키 조회, list → 멤버십
                v = v.get(k, False) if isinstance(v, dict) else (k in v if isinstance(v, list) else False)
            answers[it["id"]] = {"type": "noul", "noul": 1.0 if v else 0.0}
    return answers
