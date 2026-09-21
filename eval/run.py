"""평가 실행: python eval/run.py --model jev-1.13.0 --cases eval/cases/ [--out results.json]

지표: red flag 표시 recall(=1.0 필수), red flag 강조 recall(≥0.95), important recall(≥0.90),
protocol accuracy(≥0.90), 평균 표시 항목 수(≤12), p95 지연(≤1s).
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from app import jev_client, render  # noqa: E402

PASS = {"rf_shown_recall": 1.0, "rf_emph_recall": 0.95, "important_recall": 0.90,
        "protocol_accuracy": 0.90}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=jev_client.MODEL)
    ap.add_argument("--cases", default="eval/cases/")
    ap.add_argument("--out")
    a = ap.parse_args()
    assert a.model == jev_client.MODEL, f"모델 버전 고정: {jev_client.MODEL}"

    protos = jev_client.load_protocols()
    items = [i for p in protos.values() for i in p["items"]]
    sev = {i["id"]: i["severity"] for i in items}
    cases = [dict(json.loads(l), _file=f.stem) for f in sorted(Path(a.cases).glob("*.jsonl")) for l in open(f) if l.strip()]

    hits = {k: [0, 0] for k in ["rf_shown", "rf_emph", "important"]}
    proto_ok, n_shown, lat, per_case = 0, [], [], []
    by_file = {}  # 프로토콜별 red flag 강조 / important recall / 프로토콜 정확도
    for c in cases:
        t = time.perf_counter()
        ans = jev_client.evaluate(c["state"], protos, items)
        lat.append(time.perf_counter() - t)
        plan = render.plan(ans, items)
        shown = {i["id"]: i["level"] for i in plan["items"]}
        n_shown.append(len(shown))
        proto_ok += plan["protocol"] == c["expected_protocol"]
        misses = []
        for e in c["expected_items"]:
            if sev[e] == "red_flag":
                hits["rf_shown"][1] += 1; hits["rf_shown"][0] += e in shown
                hits["rf_emph"][1] += 1; hits["rf_emph"][0] += shown.get(e) == "emphasized"
                if shown.get(e) != "emphasized": misses.append(e)
            elif sev[e] == "important":
                hits["important"][1] += 1; hits["important"][0] += e in shown
                if e not in shown: misses.append(e)
        bf = by_file.setdefault(c["_file"], {"n": 0, "proto_ok": 0, "rf": [0, 0], "im": [0, 0]})
        bf["n"] += 1; bf["proto_ok"] += plan["protocol"] == c["expected_protocol"]
        for e in c["expected_items"]:
            if sev[e] == "red_flag": bf["rf"][1] += 1; bf["rf"][0] += shown.get(e) == "emphasized"
            elif sev[e] == "important": bf["im"][1] += 1; bf["im"][0] += e in shown
        per_case.append({"case_id": c["case_id"], "protocol": plan["protocol"],
                         "protocol_conf": round(ans["protocol"]["confidence"], 3),
                         "urgency": plan["urgency"], "shown": shown,
                         "missed": misses, "n_shown": len(shown),
                         "p": {k: round(v["noul"], 3) for k, v in ans.items() if "noul" in v}})
        print(f"{c['case_id']} {plan['protocol']:11} shown={len(shown):2} "
              f"{lat[-1]*1000:5.0f}ms  miss={misses or '-'}")

    lat.sort()
    m = {
        "rf_shown_recall": hits["rf_shown"][0] / max(1, hits["rf_shown"][1]),
        "rf_emph_recall": hits["rf_emph"][0] / max(1, hits["rf_emph"][1]),
        "important_recall": hits["important"][0] / max(1, hits["important"][1]),
        "protocol_accuracy": proto_ok / len(cases),
        "avg_shown": statistics.mean(n_shown),
        "p95_latency_s": lat[int(len(lat) * 0.95) - 1] if lat else None,
    }
    print("\n== 지표 ==")
    ok = True
    for k, v in m.items():
        crit = PASS.get(k)
        st = "" if crit is None else ("PASS" if v >= crit else "FAIL")
        if k == "avg_shown": st = "PASS" if v <= 12 else "FAIL"
        if k == "p95_latency_s": st = "PASS" if v <= 1.0 else "FAIL"
        ok &= st != "FAIL"
        print(f"{k:18} {v:.3f}  {st}")
    for f, b in by_file.items():
        print(f"  [{f}] n={b['n']} protocol={b['proto_ok']/b['n']:.3f} "
              f"rf_emph={b['rf'][0]/max(1,b['rf'][1]):.3f} important={b['im'][0]/max(1,b['im'][1]):.3f}")
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        json.dump({"model": a.model, "thresholds": render.THRESHOLDS, "emphasis": render.EMPHASIS,
                   "metrics": m, "by_file": by_file, "cases": per_case}, open(a.out, "w"), ensure_ascii=False, indent=1)
        print("→", a.out)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
