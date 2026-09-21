#!/usr/bin/env python3
"""체크리스트 라이브러리 검증기.

사용법:
  python validate_checklist.py checklists/                  # 프로덕션: 미검증 출처 = 에러
  python validate_checklist.py checklists/ --allow-unverified  # 초안: 미검증 출처 = 경고

검사 항목:
  - 필수 필드 존재, severity 값, id 형식/중복
  - source 필드 누락, TODO 자리표시자, 미검증(verified_by null)
  - jev_question 부정문/복합 질문 휴리스틱
종료 코드: 에러가 있으면 1
"""
import json
import re
import sys
from pathlib import Path

SEVERITIES = {"red_flag", "important", "routine"}
ID_RE = re.compile(r"^[a-z]+_(rf|im|rt)_\d{3}$")
SEV_PREFIX = {"red_flag": "rf", "important": "im", "routine": "rt"}
SOURCE_FIELDS = ["guideline", "section", "url", "quote_summary", "verified_by", "verified_at"]
NEGATION_RE = re.compile(r"\b(not|no|never|without|absence|absent|denies|n't)\b", re.I)
COMPOUND_RE = re.compile(r"\b(and|or)\b", re.I)


def check_file(path: Path, allow_unverified: bool, seen_ids: set):
    errors, warnings = [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"{path.name}: JSON 파싱 실패 ({e})"], []

    for key in ["protocol_id", "display_name", "choice_description", "version", "items"]:
        if key not in data:
            errors.append(f"{path.name}: 최상위 필드 '{key}' 누락")
    if errors:
        return errors, warnings

    for it in data["items"]:
        iid = it.get("id", "<no id>")
        loc = f"{path.name}:{iid}"

        for key in ["id", "text", "severity", "jev_question", "requires_state", "source"]:
            if key not in it:
                errors.append(f"{loc}: 필드 '{key}' 누락")
        if "source" not in it or "severity" not in it:
            continue

        if not ID_RE.match(iid):
            errors.append(f"{loc}: id 형식 오류 (<proto>_<rf|im|rt>_<000>)")
        if iid in seen_ids:
            errors.append(f"{loc}: id 중복")
        seen_ids.add(iid)

        sev = it["severity"]
        if sev not in SEVERITIES:
            errors.append(f"{loc}: severity '{sev}' 잘못됨")
        elif ID_RE.match(iid) and iid.split("_")[1] != SEV_PREFIX[sev]:
            errors.append(f"{loc}: id 접두사와 severity 불일치")

        src = it["source"]
        missing = [f for f in SOURCE_FIELDS if f not in src]
        if missing:
            errors.append(f"{loc}: source 필드 누락 {missing}")
            continue

        placeholder = [f for f in ["guideline", "section", "url", "quote_summary"]
                       if not src[f] or str(src[f]).strip().upper() == "TODO"]
        unverified = not src["verified_by"] or not src["verified_at"]
        if placeholder or unverified:
            msg = f"{loc}: 출처 미검증 (자리표시자: {placeholder or '없음'}, verified_by: {src['verified_by']})"
            (warnings if allow_unverified else errors).append(msg)
        elif not str(src["url"]).startswith("https://"):
            errors.append(f"{loc}: url은 https:// 로 시작해야 함")

        q = it.get("jev_question", "")
        if NEGATION_RE.search(q):
            warnings.append(f"{loc}: jev_question에 부정 표현 가능성 → 긍정형으로 재작성 검토: '{q}'")
        if COMPOUND_RE.search(q):
            warnings.append(f"{loc}: jev_question에 and/or → 판단이 두 개 숨어 있는지 확인: '{q}'")

    return errors, warnings


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    allow_unverified = "--allow-unverified" in sys.argv
    if not args:
        print(__doc__)
        sys.exit(2)
    root = Path(args[0])
    files = sorted(root.glob("*.json")) if root.is_dir() else [root]
    if not files:
        print(f"검사할 JSON 없음: {root}")
        sys.exit(2)

    all_err, all_warn, seen = [], [], set()
    for f in files:
        e, w = check_file(f, allow_unverified, seen)
        all_err += e
        all_warn += w

    for w in all_warn:
        print(f"WARN  {w}")
    for e in all_err:
        print(f"ERROR {e}")
    mode = "초안" if allow_unverified else "프로덕션"
    print(f"\n[{mode} 모드] 파일 {len(files)}개, 항목 {len(seen)}개, 에러 {len(all_err)}, 경고 {len(all_warn)}")
    sys.exit(1 if all_err else 0)


if __name__ == "__main__":
    main()
