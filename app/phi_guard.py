"""자유서술 입력의 식별정보 차단. 통과 못 하면 ValueError — 서버에서 요청 거부."""
import re

MAX_LEN = 300
PATTERNS = {
    "phone": re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}"),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "date": re.compile(r"\b\d{2,4}[./-]\d{1,2}[./-]\d{1,4}\b|\d{4}년\s*\d{1,2}월\s*\d{1,2}일"),
    "id_number": re.compile(r"\b\d{6}-?\d{7}\b"),  # 주민등록번호 형태
}


def check_free_text(text: str) -> str:
    if len(text) > MAX_LEN:
        raise ValueError(f"symptoms는 {MAX_LEN}자 이내 ({len(text)}자)")
    for name, pat in PATTERNS.items():
        if pat.search(text):
            raise ValueError(f"symptoms에 식별정보 패턴({name}) 포함 — 제거 후 재시도")
    return text
