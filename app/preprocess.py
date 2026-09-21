"""의사 입력 → Jev state. 나이·바이탈·시간 계산은 전부 여기서 끝낸다 (Jev에 원시값 안 보냄)."""
from app.phi_guard import check_free_text

AGE_BANDS = [(18, "under_18"), (40, "18-39"), (50, "40-49"), (65, "50-64"), (80, "65-79"), (999, "80+")]
VITAL_FLAGS = {  # flag name: (vital key, predicate)
    "sbp_under_90": ("sbp", lambda v: v < 90),
    "sbp_over_180": ("sbp", lambda v: v > 180),
    "hr_over_120": ("hr", lambda v: v > 120),
    "spo2_under_92": ("spo2", lambda v: v < 92),
    "temp_over_38": ("temp", lambda v: v >= 38.0),
}
ALLOWED_INPUT = {"chief_complaint", "age", "sex", "onset_minutes", "vitals", "symptoms", "risk_factors"}


def age_band(age: int) -> str:
    return next(b for lim, b in AGE_BANDS if age < lim)


def vitals_flags(vitals: dict) -> dict:
    # 측정 안 된 바이탈은 False (플래그 없음) — "정상"이라는 뜻이 아니라 "판단 불가"
    return {f: bool(k in vitals and pred(vitals[k])) for f, (k, pred) in VITAL_FLAGS.items()}


def to_state(inp: dict) -> dict:
    extra = set(inp) - ALLOWED_INPUT
    if extra:  # 스키마 밖 필드(이름, 생년월일, MRN 등)는 구조적으로 거부
        raise ValueError(f"허용되지 않은 입력 필드: {sorted(extra)}")
    return {
        "chief_complaint": inp["chief_complaint"],
        "age_band": age_band(int(inp["age"])),
        "sex": inp.get("sex", "unknown"),
        "onset_over_12h": int(inp.get("onset_minutes", 0)) > 12 * 60,
        "vitals_flags": vitals_flags(inp.get("vitals", {})),
        "symptoms": check_free_text(inp.get("symptoms", "")),
        "risk_factors": list(inp.get("risk_factors", [])),
    }
