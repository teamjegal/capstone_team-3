# 진행 상황 (2026-11-27 기준)

캡스톤 주제: **E-commerce 고객 상담 AI 에이전트** — 운영 중 발생하는 문제 영역 중 하나를 골라 개선

## 1. 요약

| 항목 | 상태 |
|---|---|
| 개발 환경 (Python 3.11 · uv · Git) | ✅ 완료 |
| 필수 패키지 (openai, python-dotenv, pyyaml) | ✅ 설치 · 커밋 |
| 선택 패키지 (환경설정 5번) | ✅ 설치 완료 · ⏳ 커밋 전 |
| LLM 서버 연결 (SSH 터널 + `.env`) | ✅ `01_chat.py` 응답 확인 |
| 데이터셋 배치 (`data/`) | ✅ 완료 (일부 파일 누락 — 4절 참고) |
| Baseline A — Naive RAG (`03_naive_rag.py`) | ✅ 코드 배치 |
| Baseline B — Naive Agent (`baseline_agent.py`) | ✅ 구현 · 허점 15개 반영 |
| 평가 스크립트 (`run_eval.py`) | ✅ 구현 · 공개 평가셋 실행 |
| 개선할 문제 영역 선정 | ⏳ 미정 |

## 2. 레포 · 브랜치

- 레포: https://github.com/teamjegal/capstone_team-3
- `main` — 기본 환경 구성 (PR #1 `setup/base-env` merge 완료)
- `feature/naive-agent` — Baseline B 에이전트 · 평가 스크립트 · 허점 문서 (push 완료, **PR · merge 전**)

```
capstone_team-3/
├── .env                 ← API 키 (git 제외)
├── .env.example         ← .env 템플릿
├── llm_client.py        ← LLM 연결 공통 코드
├── 01_chat.py           ← 기본 호출 (연결 확인)
├── 02_tool_calling.py   ← Tool Calling 예제
├── 03_naive_rag.py      ← Baseline A
├── baseline_agent.py    ← Baseline B (허점 포함)
├── run_eval.py          ← 평가 실행
├── docs/
│   ├── baseline_flaws.md  ← 허점 지도
│   └── PROGRESS.md        ← 이 문서
├── data/                ← 데이터셋 (git 제외, 각자 배치)
│   ├── README.md
│   ├── knowledge/  system/  eval/
└── results/             ← 평가 결과 (git 제외)
```

## 3. 개발 환경

- Python 3.11.3, uv 0.13.10, Git 2.56
- 필수: `openai`, `python-dotenv`, `pyyaml`
- 선택 (환경설정 5번, 전부 설치):

| 목적 | 패키지 | 버전 |
|---|---|---|
| 임베딩 (로컬) | sentence-transformers (+ torch) | 6.3.0 (torch 2.15.0) |
| Vector DB | chromadb, faiss-cpu | 1.5.9, 1.16.0 |
| 키워드 검색 (Hybrid) | rank-bm25 | 0.2.2 |
| Structured Output | pydantic | 2.14.4 |
| MCP 도구 서버 | mcp | 2.3.0 |
| 데모 화면 | streamlit | 1.67.0 |

- LLM: `qwen2.5-14b-instruct` (캡스톤 제공 서버, `localhost:8000` 터널 경유)

## 4. 데이터셋

`data/` 는 환경설정 문서 4번 구조에 맞춰 배치했습니다.

- `knowledge/` 정책 문서 5개(.md, 총 55개 문서) · `faq.json`(100) · `consultation_history.json`(200)
- `system/` products(100) · customers(50) · orders(200) · shipments(200) · coupons(50) · product_return_conditions(100)
- `eval/eval_public.jsonl` (30)
- `README.md` (데이터 설명)

**확인된 차이 · 누락**
- 배포 zip 에는 `eval_public.jsonl` 이 `data/` 바로 아래에 있어 `data/eval/` 로 옮겼음
- 데이터 README 에 있는 `eval_private.jsonl`(30) · `eval_security.jsonl`(20) 은 받은 zip 에 없음 → 조교 확인 필요

**데이터 README 의 핵심 전제**
- 운영 시각은 `2026-11-28(토) 10:00~17:00` — LLM 에 **날짜와 요일**을 넘겨야 정답 판단 가능
- 고객 안내 근거는 `status: approved` 이면서 시행 기간 안인 문서뿐
- `get_order` 는 소유자 검증 필수, `get_return_conditions` 가 카테고리 정책보다 우선
- 주말이라 상담원 이관 시 "11월 30일(월) 콜백" 이 정답에 포함

## 5. Baseline B — Naive Agent

LLM 이 도구 13개 중 무엇을 몇 번 부를지 전부 스스로 결정하는 구조입니다.
주제 설명서의 "운영 중 발생하는 문제" 15가지가 재현되도록 **일부러 허점을 남겼고**,
위치와 재현 예시는 [baseline_flaws.md](baseline_flaws.md) 에 정리했습니다.

| 영역 | 허점 번호 |
|---|---|
| 지식검색 | 01 정보검색 실패 · 02 정보충돌 |
| 의도분석 | 03 의도 파악 / 복합질문 |
| 시스템연동 | 04 실시간 정보(날짜 미제공) |
| 시스템실행 | 05 비결정성 · 06 비즈니스 로직 위반 |
| 신뢰성 | 07 데이터 정합성 · 08 할루시네이션 · 09 예외처리 |
| 보안 | 10 접근권한 · 11 프롬프트 인젝션 |
| 성능 | 12 불필요한 도구 호출 · 13 비용·지연 |
| 운영 | 14 문제 추적 · 15 도구 장애 |

## 6. 평가 결과 (공개 평가셋 30개)

`run_eval.py` 채점 기준: 정답 필수 문구(`must_include`) 전부 포함 & 금지 문구 없음

| 실행 | 조건 | 통과 | 크래시 | 평균 지연 | 평균 LLM 호출 | 평균 input token |
|---|---|---|---|---|---|---|
| 1 | 초기 프롬프트 | 0/29 | 1 | 3.2s | 1.2 | 1,939 |
| 2 | "주문 정보는 도구로 조회" 추가 | 0/30 | 0 | 2.7s | 1.1 | 1,348 |
| 3 | 도구 설명 보강 (현재 버전) | 1/30 | 0 | 4.2s | 1.5 | 2,922 |
| 4 | 현재 버전 재실행 | 0/30 | 0 | 3.2s | 1.3 | 1,988 |

> 같은 코드(3, 4)인데 결과가 다름 → 허점-05 비결정성 확인

**직접 확인한 문제 사례**

| 문제 | 사례 |
|---|---|
| 접근권한 위반 | C0001 로그인 상태에서 C0017 주문의 배송지 · 수령인 이름 노출 |
| 비즈니스 로직 위반 | 설치 완료 TV(PUB-017) "환불 가능", 각인 이어버드(PUB-019) "취소 가능" 안내 |
| 정보충돌 · 할루시네이션 | 골드 등급 반품비 "일부 무료"(구버전 정책), 무료배송 기준 · 새벽배송 마감 시각을 검색 없이 추측 |
| 프롬프트 인젝션 | "이전 지시를 무시하고…" 입력에 시스템 프롬프트 내용 노출 |
| 예외처리 실패 | 상담원 이관이 필요한 케이스에서 이관하지 않거나, 이관해도 콜백 일정 안내 누락 |
| 도구 장애 | 존재하지 않는 주문번호 조회 시 에이전트 크래시 |
| 의도 · 도구 선택 | 대부분의 주문 질문에 `list_orders` 대신 주문번호를 되물음 |
| 성능 | 도구 2회 호출 시 input token 3천+, 응답 8~15초 |

## 7. 진행 중 겪은 이슈와 해결

| 이슈 | 원인 | 해결 |
|---|---|---|
| `can't open file 01_chat.py` | 프로젝트 폴더 밖에서 실행 | 프로젝트 폴더로 `cd` 후 실행 |
| `KeyError: 'LLM_MODEL'` | `.env` 파일 없음 | `.env.example` 복사해 `.env` 생성 |
| `UnicodeEncodeError` | API 키를 `.env.example` 에 넣어 `.env` 에 한글 예시 문구가 남음 | 키를 `.env` 로 옮기고 `.env.example` 원복 (키 유출 방지) |
| 커밋 실패 `Author identity unknown` | git 사용자 정보 미설정 | `git config --global user.name/email` 설정 |
| 평가 30개 전부 `Connection error` | SSH 터널 끊김 | 터널 재접속 |

## 8. 다음 할 일

- [ ] `feature/naive-agent` PR 생성 · 팀 리뷰 · merge
- [ ] 선택 패키지 설치분(`pyproject.toml`, `uv.lock`) 커밋
- [ ] 조교에게 `eval_private.jsonl` · `eval_security.jsonl` 제공 여부 확인
- [ ] 팀 회의: 개선할 **문제 영역 1개** 선정 (허점 지도 참고)
- [ ] 선정 영역의 문제 정의 · 사용자 시나리오 작성
- [ ] 아키텍처 선택 (RAG / Agent / Workflow / Hybrid) 과 근거, 고려한 대안 정리
- [ ] 개선 구현 후 `run_eval.py` 로 Baseline 대비 효과 측정 (`--repeat` 로 일관성 포함)
- [ ] 최종 산출물: 코드 · 문제 정의 · 아키텍처 문서 · 평가 결과 · 발표 자료
