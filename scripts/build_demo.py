#!/usr/bin/env python3
"""평가 결과 JSON → docs/demo.json (GitHub Pages 예시 증례, 백엔드 없이 표시).

  python3 scripts/build_demo.py eval/results/<결과>.json [...]   # 여러 파일이면 뒤 파일이 같은 case_id를 덮어씀
확률은 정렬에만 쓰고 파일에 넣지 않는다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
res = {"model": None, "cases": []}
for f in sys.argv[1:]:
    r = json.load(open(f))
    res["model"] = r["model"]
    res["cases"] = [c for c in res["cases"] if c["case_id"] not in {x["case_id"] for x in r["cases"]}] + r["cases"]
res["cases"].sort(key=lambda c: c["case_id"])
protos = {p["protocol_id"]: p for p in (json.loads(f.read_text()) for f in (ROOT / "checklists").glob("*.json"))}
items = {i["id"]: i for p in protos.values() for i in p["items"]}
cases = {c["case_id"]: c for f in (ROOT / "eval/cases").glob("*.jsonl") for c in map(json.loads, open(f)) if c}

demo = []
for r in res["cases"]:
    c = cases[r["case_id"]]
    st = c["state"]
    shown = sorted(r["shown"], key=lambda k: (items[k]["severity"] != "red_flag", -r["p"].get(k, 0)))
    demo.append({
        "case_id": r["case_id"], "protocol_name": protos.get(r["protocol"], {}).get("display_name", "해당 없음"),
        "summary": f"{st['age_band']} {st.get('sex', '')} · {st['symptoms'][:40]}",
        "state": {k: st[k] for k in ["chief_complaint", "symptoms", "risk_factors", "sex"] if k in st},
        "plan": {"protocol": r["protocol"], "protocol_name": protos.get(r["protocol"], {}).get("display_name", "해당 없음"),
                 "protocol_uncertain": r["protocol"] == "other" or r["protocol_conf"] < 0.5,
                 "urgency": r["urgency"],
                 "items": [{k: items[i][k] for k in ["id", "text", "severity", "source"]} | {"level": r["shown"][i]}
                           for i in shown]},
    })
(ROOT / "docs/demo.json").write_text(json.dumps(demo, ensure_ascii=False))
print(f"{len(demo)} cases → docs/demo.json (model {res['model']})")
