"""표시 규칙. red flag는 확률과 무관하게 항상 표시 — 이 파일 밖에서 이 규칙을 우회하는 코드는 금지."""
THRESHOLDS = {"important": 0.30, "routine": 0.50}  # jev-1.13.0 기준 시작값. 변경 시 평가 결과 첨부.
EMPHASIS = 0.50            # red flag 강조 임계값
URGENCY_LABEL = ["일반", "수 시간 내", "긴급", "즉시"]


def plan(answers: dict, items: list) -> dict:
    shown = []
    for it in items:
        if it["id"] not in answers:  # evaluate()가 묻지 않은 항목 = 다른 프로토콜의 비-red-flag 항목
            continue
        p = answers[it["id"]]["noul"]
        if it["severity"] == "red_flag":
            shown.append({**it, "p": p, "level": "emphasized" if p >= EMPHASIS else "shown"})
        elif p >= THRESHOLDS[it["severity"]]:
            shown.append({**it, "p": p, "level": "emphasized" if p >= 0.7 else "shown"})
    shown.sort(key=lambda x: (x["severity"] != "red_flag", -x["p"]))
    proto = answers["protocol"]
    return {
        "protocol": proto["choice"],
        "protocol_uncertain": proto["choice"] == "other" or proto["confidence"] < 0.5,
        "urgency": URGENCY_LABEL[min(3, round(answers["urgency"]["score"]))],
        "items": shown,
    }


def to_text(p: dict, protocols: dict, debug=False) -> str:
    name = protocols.get(p["protocol"], {}).get("display_name", p["protocol"])
    out = [f"확인 권장 항목 — {name} / 확인 시급도: {p['urgency']}"]
    if p["protocol_uncertain"]:
        out.append("⚠ 프로토콜 불확실: 주호소를 다시 확인하세요")
    for sec, title in [("red_flag", "■ 반드시 확인"), ("important", "■ 확인 권장"), ("routine", "▸ 고려 (접힘)")]:
        rows = [i for i in p["items"] if i["severity"] == sec]
        if not rows:
            continue
        out.append(title)
        for i in rows:
            mark = "★" if i["level"] == "emphasized" else " "
            dbg = f"  [p={i['p']:.2f}]" if debug else ""
            s = i["source"]
            out.append(f" {mark} {i['text']}{dbg}\n     근거: {s['guideline']} {s['section']} {s['url']}")
    return "\n".join(out)
