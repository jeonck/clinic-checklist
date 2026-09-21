# 진단 전 체크리스트 (Jev)

의사가 주호소와 바이탈을 입력하면, **실존 가이드라인에 근거한** 확인 권장 항목을 정렬해 보여준다.
화면의 모든 문구와 인용은 사람이 검증한 `checklists/*.json`에서 온다. Jev(TypeSafe System One)는
"이 환자에게 어떤 항목이 해당되는가"만 판단해 순서와 강조를 정한다 — **생성하는 텍스트는 0**.

```
[의사 입력: 주호소 + 나이 + 바이탈 + 증상 (PHI 없음)]
   │  app/preprocess.py   나이대·바이탈 플래그·경과시간 → 불리언 (Jev에 계산 안 시킴)
   │  app/phi_guard.py    전화·이메일·날짜·주민번호 패턴 거부, 300자 제한
   ▼
[Jev 2회 호출]  app/jev_client.py
   1. 프로토콜 Choice + 긴급도 Score   ← {chief_complaint, symptoms}
   2. 항목별 Noul(해당 확률)           ← {symptoms}   ※ 플래그·병력 항목은 코드가 답함
   ▼
[표시 규칙]  app/render.py   red flag는 확률 무관 항상 표시 → 정렬 → 근거 인용 붙여 출력
```

## 빠른 시작 (Apple silicon, 로컬 open-jev)

```bash
make setup          # open-jev 클론 + mlx-community/gemma-3-4b-it-4bit (~2.5 GB)
make serve          # http://127.0.0.1:8000
make health         # {"ok": true, ...}
python3 -m app.main input.json --debug
```

`input.json` 예시:
```json
{"chief_complaint": "chest_pain", "age": 58, "sex": "M", "onset_minutes": 30,
 "vitals": {"sbp": 142, "hr": 96, "spo2": 97, "temp": 36.8},
 "symptoms": "30분 전 시작된 가슴 중앙 압박감, 왼팔로 뻗침, 식은땀 동반",
 "risk_factors": ["smoking", "hypertension"]}
```

TypeSafe API로 전환: `TYPESAFE_BASE_URL=https://api.typesafe.ai TYPESAFE_API_KEY=sk-...` (모델은 `jev-1.13.0` 고정).

## 명령어

```bash
make test           # 서버 없이 도는 단위 테스트 (PHI 가드, 전처리, red flag 표시 규칙)
make validate       # 체크리스트 검증, 초안 모드
python3 scripts/validate_checklist.py checklists/        # 프로덕션 모드 — 미검증 출처는 에러
make eval           # 평가셋 실행 → eval/results/<날짜>.json
```

## 현재 상태 (MVP: 흉통 1개 프로토콜)

| | |
|---|---|
| 항목 | 26개 (red flag 8 / important 13 / routine 5) — **출처 전부 미검증** (`verified_by: null`) |
| 평가셋 | 가상 증례 35개 (전형·비전형·주입·부정문) — `labeled_by: draft-unreviewed` |
| 평가 v3 (로컬 gemma-3-4b) | red flag 표시 1.00 · 강조 0.972 · important 0.949 · 프로토콜 1.00 · 평균 표시 10.7 · p95 15 s |

p95 ≤ 1 s 기준은 TypeSafe API에서 재측정해야 한다. 임계값(`app/render.py`)은 모델별 튠값이라 모델을 바꾸면 평가를 다시 돌린다.

### 배포 전 사람이 할 일
1. 26항목 `source` 원문 확인 후 `verified_by` / `verified_at` 기입 — 프로덕션 검증기가 통과할 때까지 배포 불가
2. 35증례 `expected_items` 임상 검토
3. 규제 검토 (FDA CDS 관점: 항목마다 근거 링크, 단일 결론 없음)

## 절대 규칙
- 가이드라인 이름·조항·URL을 기억으로 채우지 않는다 → `verified_by: null`
- red flag를 확률로 숨기지 않는다
- 나이·수치·날짜 계산을 Jev에 맡기지 않는다
- 식별정보를 state에 넣지 않고, state 원문을 로그에 남기지 않는다
- UI에 "진단", "판정", "안전", 원시 확률을 쓰지 않는다

자세한 개발 지침은 [CLAUDE.md](CLAUDE.md).

## 로컬 모델 튜닝에서 배운 것
- Noul state에 `symptoms` 외 필드(`vitals_flags`, `sex`…)를 하나만 더 넣어도 false positive가 2배 (v1 평균 표시 15.1 → v3 10.7)
- 질문은 `"The symptoms text explicitly states that …"` 형태로 — 안 그러면 4B 모델은 흉통에 "그럴듯한" 항목 전부에 yes
- 구조화된 사실(플래그, 병력 리스트)은 `state_flag`로 코드가 답한다 — 모델보다 정확하고 빠르다
