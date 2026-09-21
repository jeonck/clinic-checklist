# CLAUDE.md — 진단 전 체크리스트 (Jev)

## 이 프로젝트가 하는 일
의사가 주호소와 바이탈을 넣으면, **실존 가이드라인에 근거한** 확인 권장 항목을 1초 안에 정렬해 보여준다.
Jev(TypeSafe System One 모델)는 항목 선택과 정렬만 한다. 화면의 모든 문구와 인용은 `checklists/*.json`에서 온다.

작업 전 `jev-clinical-checklist` 스킬을 로드할 것.

## 레포 구조
```
checklists/          프로토콜별 항목 라이브러리 (JSON, 사람이 검증한 출처 포함)
app/
  preprocess.py      나이대·바이탈 플래그·시간 계산 (Jev에 계산 시키지 않음)
  jev_client.py      system_one 단일 호출 (모든 질문 병렬)
  render.py          표시 규칙 (red flag 항상 표시)
  phi_guard.py       식별정보 차단
  web.py, index.html 최소 웹 UI (stdlib http.server)
eval/
  cases/*.jsonl      가상 증례 + 검토자 라벨
  run.py             지표 계산
scripts/validate_checklist.py
```

## 명령어
```bash
python scripts/validate_checklist.py checklists/                    # 프로덕션 검증 (CI 필수)
python scripts/validate_checklist.py checklists/ --allow-unverified # 초안 작업 중
python eval/run.py --model jev-1.13.0 --cases eval/cases/
pytest
```

## 하지 말 것
- 가이드라인 이름·조항·URL을 기억으로 채우기 → `verified_by: null`로 두고 검토 목록에 올릴 것
- red flag 항목을 확률로 숨기는 코드
- Jev에 원시 생년월일, 원시 수치 비교, 날짜 계산 맡기기
- `jev-latest` 사용 (버전 고정: `jev-1.13.0`)
- 식별정보를 state에 넣기, state 원문을 로그에 남기기
- UI에 "진단", "판정", "안전" 문구, 원시 확률 노출
- 임계값 변경 PR에 평가 결과 미첨부

## 완료 정의 (Definition of Done)
- [ ] `validate_checklist.py` 프로덕션 모드 통과 (배포 대상 항목)
- [ ] 평가: red flag 표시 recall = 1.0, 강조 recall ≥ 0.95, 프로토콜 정확도 ≥ 0.90
- [ ] p95 지연 ≤ 1s
- [ ] 새 jev_question은 긍정형 단문, 판단 하나
- [ ] PHI 가드 테스트 통과 (전화번호/이메일/날짜 패턴 거부)

## 현재 범위 (MVP)
흉통 프로토콜 1개, 항목 약 20개, 평가 증례 30개 이상. 다른 프로토콜은 흉통 지표가 합격한 뒤 추가.
