# 진단 전 체크리스트 (Jev)

> **연구용 프로토타입 — 임상 사용 금지.** 체크리스트 출처는 아직 사람이 검증하지 않았고(`verified_by: null`),
> 평가 증례는 전부 가상이며 임상 검토 전입니다. 데모: https://jeonck.github.io/clinic-checklist/

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
python3 -m app.main input.json --debug   # CLI
python3 -m app.web 8080                   # 웹 UI → http://127.0.0.1:8080
```

`input.json` 예시:
```json
{"chief_complaint": "chest_pain", "age": 58, "sex": "M", "onset_minutes": 30,
 "vitals": {"sbp": 142, "hr": 96, "spo2": 97, "temp": 36.8},
 "symptoms": "30분 전 시작된 가슴 중앙 압박감, 왼팔로 뻗침, 식은땀 동반",
 "risk_factors": ["smoking", "hypertension"]}
```

TypeSafe API로 전환: `TYPESAFE_BASE_URL=https://api.typesafe.ai TYPESAFE_API_KEY=sk-...` (모델은 `jev-1.13.0` 고정).

## 데모 페이지 (GitHub Pages)

https://jeonck.github.io/clinic-checklist/ — 정적 페이지라 Jev 백엔드가 없다. 두 가지 모드:
- **예시 증례**: 평가셋 증례의 결과를 미리 계산해 둔 `docs/demo.json`을 보여준다 (`scripts/build_demo.py <결과 JSON>`으로 갱신).
- **로컬 API 주소**: 내 컴퓨터에서 `make serve` + `python3 -m app.web`을 띄우고 `http://127.0.0.1:8080`을 넣으면 실제로 호출한다 (CORS 허용됨).

## 명령어

```bash
make test           # 서버 없이 도는 단위 테스트 (PHI 가드, 전처리, red flag 표시 규칙)
make validate       # 체크리스트 검증, 초안 모드
python3 scripts/validate_checklist.py checklists/        # 프로덕션 모드 — 미검증 출처는 에러
make eval           # 평가셋 실행 → eval/results/<날짜>.json
```

## 현재 상태

| 프로토콜 | 항목 | 증례 | 평가 (로컬 gemma-3-4b) |
|---|---|---|---|
| 흉통 `chest_pain` | 26 (rf 8 / im 13 / rt 5) | 35 | red flag 강조 0.972 · important 0.949 · 프로토콜 0.97 |
| 두통 `headache` | 26 (rf 10 / im 12 / rt 4) | 32 | red flag 강조 1.000 · important 1.000 · 프로토콜 1.00 · 평균 표시 12.2 |

전 항목 **출처 미검증** (`verified_by: null`), 전 증례 `labeled_by: draft-unreviewed`. red flag 표시 recall은 코드로 보장(1.0).
프로토콜 선택 후 그 프로토콜 항목만 묻고, 선택이 불확실하면 모든 프로토콜의 red flag를 표시한다.

p95 ≤ 1 s 기준은 TypeSafe API에서 재측정해야 한다. 임계값(`app/render.py`)은 모델별 튠값이라 모델을 바꾸면 평가를 다시 돌린다.

### 배포 전 사람이 할 일
1. 52항목 `source` 원문 확인 후 `verified_by` / `verified_at` 기입 — 프로덕션 검증기가 통과할 때까지 배포 불가
2. 67증례 `expected_items` 임상 검토
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
- 구조화된 사실(플래그, 병력 리스트, 나이 기준)은 `state_flag`로 코드가 답한다 — 모델보다 정확하고 빠르다
- 한국어 입력에는 핵심 용어를 병기하면 잡힌다: `벼락두통 (thunderclap)` 0.01→1.0, `위약, 힘이 빠짐` 0.02→0.95
- "A, B, C, or D" 긴 나열 질문은 개별 항목보다 못 잡는다 → 신경학적 결손을 위약/언어/시각 3개로 분리
