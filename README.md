# capstone_team-3

이커머스 고객 상담(CS) LLM 에이전트 캡스톤 프로젝트.

## 팀원 시작 가이드

### 0. 팀장에게 받을 것 (git 에 없음 · 카톡 등 비공개로 전달)
| 받을 것 | 쓰는 곳 |
|---|---|
| GitHub 레포 초대 (Collaborator) | 메일로 온 초대 수락 후 clone |
| `data.zip` + 데이터 설명 `README.md` | 5단계 데이터 배치 |
| 팀 API 키 | 4단계 `.env` |
| SSH 터널 비밀번호 (수업 자료) | 3단계 터널 |

> API 키 · 비밀번호는 코드, 커밋, 이슈, 공개 채널 어디에도 올리지 않습니다.

### 1. 준비물 설치
Python 3.10 이상, [uv](https://docs.astral.sh/uv/), Git

```powershell
# uv 설치 (Windows PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
```bash
# uv 설치 (macOS · Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh
```
설치 후 터미널을 새로 열고 `python --version`, `uv --version`, `git --version` 으로 확인합니다.

처음 git 을 쓰는 PC 라면 커밋 작성자 정보를 한 번 설정합니다.
```powershell
git config --global user.name "GitHub 아이디"
git config --global user.email "GitHub 에 등록된 이메일"
```

### 2. 클론 및 패키지 설치
```powershell
git clone https://github.com/teamjegal/capstone_team-3.git
cd capstone_team-3
uv sync
```
`uv sync` 가 필수 · 선택 패키지(torch 포함)를 모두 설치합니다. 처음에는 몇 분 걸립니다.
이후 명령은 **항상 이 `capstone_team-3` 폴더 안에서** 실행합니다.

### 3. LLM 서버 터널 열기
터미널 하나에서 아래를 실행하고 **계속 켜 둡니다**. 비밀번호 입력 후 아무 반응이 없으면 정상입니다.
다른 작업은 새 터미널을 열어서 합니다.
```powershell
ssh -N -L 8000:localhost:8000 tunnel@117.16.244.167
```

### 4. `.env` 만들기
```powershell
Copy-Item .env.example .env      # macOS: cp .env.example .env
notepad .env                     # macOS: open -e .env
```
`LLM_API_KEY=` 뒤의 예시 문구를 지우고 팀 API 키를 넣습니다.
키는 **`.env` 에만** 넣습니다. `.env.example` 은 git 에 올라가는 파일이라 키를 넣으면 유출됩니다.

서버 확인 (새 터미널):
```powershell
curl.exe http://localhost:8000/v1/models -H "Authorization: Bearer <API키>"
```

### 5. 데이터셋 배치
`data.zip` 을 프로젝트 폴더에 풀고 `data/` 가 아래처럼 되도록 정리합니다. (`data/` 는 git 에 올리지 않고 각자 배치)
```
data/
├── README.md          ← 데이터 설명 (따로 받은 파일)
├── knowledge/         ← 정책 문서 5개(.md), faq.json, consultation_history.json
├── system/            ← products, customers, orders, shipments, coupons, product_return_conditions
└── eval/              ← eval_public.jsonl (공개 평가셋 30개)
```
배포 zip 은 구조가 조금 달라서 아래 정리가 필요합니다.
- `data/eval_public.jsonl` → `data/eval/eval_public.jsonl` 로 이동
- 따로 받은 데이터 설명 `README.md` → `data/README.md` 로 이동
- macOS 압축 잔여물 `__MACOSX/`, `.DS_Store` 는 지워도 됩니다

```powershell
New-Item -ItemType Directory -Force data\eval
Move-Item data\eval_public.jsonl data\eval\
```

### 6. 동작 확인
```powershell
uv run python 01_chat.py
```
답변과 함께 `응답 시간 · input/output token` 이 나오면 준비 완료입니다.

### 막힐 때
| 증상 | 원인 · 해결 |
|---|---|
| `can't open file '...01_chat.py'` | 프로젝트 폴더 밖에서 실행함 → `cd capstone_team-3` |
| `KeyError: 'LLM_MODEL'` | `.env` 파일이 없음 → 4단계 |
| `UnicodeEncodeError: 'ascii' codec` | `.env` 에 한글 예시 문구가 남아 있음 (키를 `.env.example` 에 넣은 경우가 많음) → `.env` 에 키 입력, `.env.example` 은 `git restore .env.example` |
| `APIConnectionError` / `Connection error` / `WinError 10061` | SSH 터널이 꺼짐 → 3단계 다시 실행 |
| `401` / `Unauthorized` | API 키가 틀림 |
| `FileNotFoundError: data/...` | 5단계 데이터 배치 확인 |
| 커밋 시 `Author identity unknown` | 1단계 `git config` 설정 |

## 실행 방법

### 예제 (환경설정 문서)
```powershell
uv run python 01_chat.py          # 기본 호출 (응답 시간 · 토큰 수)
uv run python 02_tool_calling.py  # Tool Calling (data/ 필요)
uv run python 03_naive_rag.py     # 글자 겹침 검색 RAG 예제 (data/ 필요)
```

### Baseline A — Naive RAG (Embedding + Vector DB)
```powershell
uv run python baseline_rag.py "무료배송 기준이 얼마인가요?"   # 질문 하나 (첫 실행 시 임베딩 모델 다운로드 · 인덱스 생성)
uv run python baseline_rag.py --chat                         # 대화 모드
uv run python baseline_rag.py --rebuild                      # data/ 가 바뀌었을 때 인덱스 다시 생성
```
임베딩 모델 `intfloat/multilingual-e5-small`(약 470MB)은 첫 실행 때 자동으로 받고, 인덱스는 `chroma_db/` 에 저장됩니다 (git 제외).

### Baseline B — Naive Agent · 평가
```powershell
uv run python baseline_agent.py "내 주문 언제 도착해?" --customer C0001   # 질문 하나
uv run python baseline_agent.py --chat --customer C0001                  # 대화 모드 (exit / 종료 로 끝냄)
uv run python run_eval.py                                                # Baseline B 로 공개 평가셋 30개
uv run python run_eval.py --system a                                     # Baseline A 로 공개 평가셋 30개
uv run python run_eval.py --ids PUB-001 --repeat 5                       # 같은 질문 반복 (일관성)
uv run python run_scenarios.py                                           # 문제 유형별 대화 시나리오 16개
uv run python run_scenarios.py S11 S12                                   # 일부 시나리오만
```
### A · B 비교 대화
```powershell
uv run python compare_chat.py --customer C0001
```
질문 하나를 입력하면 Baseline A 와 B 가 차례로 답합니다 (대화 기록은 각자 유지, `--customer` 는 B 만 사용).

`--customer` 는 로그인한 고객 ID(세션)입니다 (C0001 ~ C0050).
결과는 `results/` 에 jsonl 로 저장됩니다 (git 제외).

## 협업 규칙
- `main` 에 직접 커밋하지 않고 브랜치(`feature/...`)를 만들어 작업 → push → PR → 리뷰 후 merge
- 작업 시작 전 `git switch main` → `git pull` 로 최신화, 패키지가 바뀌었으면 `uv sync`
- 패키지 추가는 `uv add <패키지>` 로 (`pyproject.toml` · `uv.lock` 같이 커밋)
- `.env`, `data/`, `results/` 는 커밋하지 않음 (`.gitignore` 에 등록됨)

## 파일 구성
| 파일 | 설명 |
|---|---|
| `llm_client.py` | LLM 연결 공통 코드 (`from llm_client import client, MODEL`) |
| `01_chat.py` | 기본 호출 — 연결 확인, latency · token usage 측정 |
| `02_tool_calling.py` | 도구 호출 루프, 주문 소유자 검증은 코드에서 |
| `03_naive_rag.py` | 환경설정 문서 예제 — 글자 bigram 겹침 기반 단순 RAG |
| `baseline_rag.py` | Baseline A — Naive RAG (multilingual-e5 임베딩 + Chroma, **허점 8개를 일부러 남김**) |
| `baseline_agent.py` | Baseline B — Naive Agent (도구 13개, **허점 15개를 일부러 남김**) |
| `compare_chat.py` | A · B 비교 대화 모드 — 같은 질문에 두 베이스라인 답을 나란히 출력 |
| `run_eval.py` | 평가셋 실행 · 결과 저장 · 간단 채점 (`--system a` / `b`) |
| `run_scenarios.py` | 멀티턴 대화 시나리오 실행 — 대화 중 문제 재현 |
| `scenarios/chat_scenarios.json` | 운영 문제 유형별 대화 시나리오 16개 |
| `docs/baseline_flaws.md` | 허점 지도 — 문제 영역별 코드 위치와 재현 결과 |

## 알려진 문제 (개선 대상)
`baseline_rag.py`(A), `baseline_agent.py`(B) 는 일부러 단순하게 만든 베이스라인입니다.
운영 중 발생하는 문제 15가지(지식검색 · 의도분석 · 시스템연동 · 시스템실행 · 신뢰성 · 보안 · 성능 · 운영)가
재현되도록 허점을 남겨 두었고, 목록과 위치는 [docs/baseline_flaws.md](docs/baseline_flaws.md) 에 있습니다.
팀은 이 중 한 영역을 골라 개선합니다.

## 설치된 패키지
`uv sync` 로 모두 설치됩니다.

| 목적 | 패키지 |
|---|---|
| LLM 호출 · 설정 | `openai`, `python-dotenv`, `pyyaml` |
| 임베딩 (로컬) | `sentence-transformers` (+ torch) |
| Vector DB | `chromadb`, `faiss-cpu` |
| BM25 (Hybrid Search) | `rank-bm25` |
| Structured Output | `pydantic` |
| MCP 도구 서버 | `mcp` |
| 데모 화면 | `streamlit` |
