"""python -m app.main input.json [--debug]  — 의사 입력 JSON → 확인 권장 항목."""
import json
import logging
import sys

from app import jev_client, preprocess, render

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    inp = json.load(open(sys.argv[1]))
    state = preprocess.to_state(inp)
    protos = jev_client.load_protocols()
    items = [i for p in protos.values() for i in p["items"]]
    answers = jev_client.evaluate(state, protos, items)
    print(render.to_text(render.plan(answers, items), protos, debug="--debug" in sys.argv))
