"""python3 -m app.web [port]  — 최소 웹 UI. stdlib http.server, 의존성 없음.

GET  /            index.html
POST /api/check   의사 입력 JSON → render.plan() 결과 (확률 필드는 제거해 내보냄)
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError

from app import jev_client, preprocess, render

DOCS = Path(__file__).parent.parent / "docs"  # index.html·demo.json은 GitHub Pages와 공유
PROTOS = jev_client.load_protocols()
ITEMS = [i for p in PROTOS.values() for i in p["items"]]


def check(inp: dict) -> dict:
    state = preprocess.to_state(inp)
    plan = render.plan(jev_client.evaluate(state, PROTOS, ITEMS), ITEMS)
    plan["protocol_name"] = PROTOS.get(plan["protocol"], {}).get("display_name", "해당 없음")
    for it in plan["items"]:  # 원시 확률은 UI로 내보내지 않는다
        it.pop("p", None); it.pop("jev_question", None); it.pop("requires_state", None)
    return plan


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("access-control-allow-origin", "*")  # github.io 페이지에서 로컬 API 호출 허용
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            return self._send(200, (DOCS / "index.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/demo.json" and (DOCS / "demo.json").exists():
            return self._send(200, (DOCS / "demo.json").read_bytes())
        self._send(404, {"error": "not found"})

    def do_OPTIONS(self):  # CORS preflight
        self.send_response(204)
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-headers", "content-type")
        self.send_header("access-control-allow-methods", "POST")
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/check":
            return self._send(404, {"error": "not found"})
        try:
            inp = json.loads(self.rfile.read(int(self.headers.get("content-length", 0)) or 0) or b"{}")
            self._send(200, check(inp))
        except (ValueError, KeyError) as e:  # PHI 가드·스키마 위반 — 원문은 로그에 남기지 않는다
            self._send(400, {"error": str(e)})
        except URLError as e:
            self._send(502, {"error": f"Jev 서버에 연결할 수 없음 ({e.reason}). make serve 실행 여부 확인"})

    def log_message(self, fmt, *args):  # 기본 로그는 요청 경로만 — 입력 본문은 절대 기록하지 않음
        sys.stderr.write(f"{self.command} {self.path} {args[1] if len(args) > 1 else ''}\n")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
