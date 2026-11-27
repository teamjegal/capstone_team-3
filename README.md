# capstone_team-3

이커머스 고객 상담(CS) LLM 에이전트 캡스톤 프로젝트.

## 빠른 시작

### 1. 준비물
Python 3.10 이상, [uv](https://docs.astral.sh/uv/), Git

```powershell
# uv 설치 (Windows)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. 클론 및 패키지 설치
```powershell
git clone https://github.com/teamjegal/capstone_team-3.git
cd capstone_team-3
uv sync
```

### 3. LLM 서버 터널 열기
터미널 하나에서 아래를 실행하고 **계속 켜 둡니다**. 비밀번호(수업 자료 참고) 입력 후 아무 반응이 없으면 정상입니다.
```powershell
ssh -N -L 8000:localhost:8000 tunnel@117.16.244.167
```

### 4. `.env` 만들기
```powershell
Copy-Item .env.example .env
```
`.env` 의 `LLM_API_KEY` 에 팀 API 키를 넣습니다. **`.env` 는 절대 커밋하지 않습니다** (`.gitignore` 에 등록됨).

서버 확인 (새 터미널):
```powershell
curl.exe http://localhost:8000/v1/models -H "Authorization: Bearer <API키>"
```

### 5. 데이터셋 배치
배포된 `ecommerce_cs_mock_data.zip` 을 프로젝트 폴더에 풀어 `data/` 가 아래처럼 되게 합니다. (`data/` 는 git 에 올리지 않고 각자 배치)
```
data/
├── README.md       ← 데이터 설명 (꼭 읽기)
├── knowledge/      ← 정책 문서 5개(.md), faq.json, consultation_history.json
├── system/         ← products, customers, orders, shipments, coupons, product_return_conditions
└── eval/           ← eval_public.jsonl 등
```

### 6. 예제 실행
```powershell
uv run python 01_chat.py          # 기본 호출 (응답 시간 · 토큰 수)
uv run python 02_tool_calling.py  # Tool Calling (data/ 필요)
uv run python 03_naive_rag.py     # Naive RAG (data/ 필요)
```

## 파일 구성
| 파일 | 설명 |
|---|---|
| `llm_client.py` | LLM 연결 공통 코드 (`from llm_client import client, MODEL`) |
| `01_chat.py` | 기본 호출 — 연결 확인, latency · token usage 측정 |
| `02_tool_calling.py` | 도구 호출 루프, 주문 소유자 검증은 코드에서 |
| `03_naive_rag.py` | 글자 bigram 겹침 기반 단순 RAG — 개선 출발점 |

## 알려진 문제 (개선 대상)
`03_naive_rag.py` 는 일부러 단순하게 만든 베이스라인입니다.
- 배송 질문에 환불 문서가 1순위로 검색됨 (bigram 겹침 검색의 한계)
- 승인되지 않은 `draft` 문서가 컨텍스트에 섞여 들어옴

## 선택 패키지
| 목적 | 설치 |
|---|---|
| 임베딩 (로컬) | `uv add sentence-transformers` |
| Vector DB | `uv add chromadb` 또는 `uv add faiss-cpu` |
| BM25 (Hybrid Search) | `uv add rank-bm25` |
| Structured Output | `uv add pydantic` |
| MCP 도구 서버 | `uv add mcp` |
| 데모 화면 | `uv add streamlit` |
