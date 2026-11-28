"""Baseline A — Naive RAG (Embedding + Vector DB)

주제 설명서의 1차 구성:
    사용자 질문 → Embedding → Vector DB 검색 → Prompt 구성 → LLM(14B) 답변 생성

임베딩은 sentence-transformers(multilingual-e5-small, 로컬 실행), Vector DB 는 Chroma 를 사용한다.
주제 설명서에 적힌 Baseline A 의 한계가 그대로 드러나도록 단순하게 두었다 (`# [A-허점-XX]` 주석).

    uv run python baseline_rag.py --rebuild                       # 인덱스 다시 만들기
    uv run python baseline_rag.py "무료배송 기준이 얼마인가요?"      # 질문 하나
    uv run python baseline_rag.py --chat                          # 대화 모드
"""
import argparse
import json
import os
import pathlib
import re
import time

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")  # Windows 캐시 경고 숨김

import chromadb
import yaml
from sentence_transformers import SentenceTransformer

from llm_client import client, MODEL

DATA = pathlib.Path("data")
DB_PATH = "chroma_db"
COLLECTION = "knowledge"
EMBED_MODEL = "intfloat/multilingual-e5-small"  # 다국어 · 한국어 지원, CPU 로도 빠름 (최초 1회 다운로드)
TOP_K = 3

_embedder = None


def embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


# ---------------------------------------------------------------------------
# 1. 문서 적재 (청킹 + 메타데이터)
# ---------------------------------------------------------------------------
def load_chunks():
    chunks = []
    # 정책 문서: '## [DOC_ID] 제목' 단위로 청킹
    for f in sorted((DATA / "knowledge").glob("*.md")):
        text = f.read_text(encoding="utf-8")
        for chunk in re.split(r"\n(?=## \[)", text)[1:]:
            m = re.search(r"```yaml\n(.*?)```", chunk, re.S)
            meta = yaml.safe_load(m.group(1)) if m else {}
            body = re.sub(r"```yaml\n.*?```", "", chunk, flags=re.S).strip()
            chunks.append({"id": meta.get("doc_id"), "text": body, "meta": {
                "source": f.name, "doc_id": meta.get("doc_id"), "title": meta.get("title"),
                "status": meta.get("status"), "effective_from": meta.get("effective_from"),
                "effective_to": meta.get("effective_to"), "visibility": meta.get("visibility")}})
    # FAQ: 질문 + 답변을 한 청크로
    for q in json.loads((DATA / "knowledge" / "faq.json").read_text(encoding="utf-8")):
        chunks.append({"id": q["faq_id"], "text": f"Q. {q['question']}\nA. {q['answer']}", "meta": {
            "source": "faq.json", "doc_id": q["faq_id"], "title": q["question"],
            "status": q["status"], "effective_from": q.get("updated_at")}})
    # Chroma 메타데이터는 str/int/float/bool 만 허용 → 문자열로 바꾸고 None 제거
    for c in chunks:
        c["meta"] = {k: str(v) for k, v in c["meta"].items() if v is not None}
    return chunks


# ---------------------------------------------------------------------------
# 2. 인덱싱 (Embedding → Vector DB)
# ---------------------------------------------------------------------------
def build_index(rebuild=False):
    db = chromadb.PersistentClient(path=DB_PATH)
    if rebuild:
        try:
            db.delete_collection(COLLECTION)
        except Exception:
            pass
    col = db.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    if col.count() > 0:
        return col
    # [A-허점-01 정보충돌] status(deprecated/draft/rejected/unverified/expired) · 시행기간 · outdated FAQ 를
    #   거르지 않고 전부 같은 컬렉션에 넣음 → 과거 · 미승인 문서가 현행 문서와 똑같이 검색됨
    # [A-허점-02 보안] visibility: internal(상담원 전용) 문서와 악성 지시가 섞인 미검증 문서(REF-020)도 그대로 적재
    chunks = load_chunks()
    emb = embedder().encode([f"passage: {c['text']}" for c in chunks], normalize_embeddings=True,
                            show_progress_bar=True)
    col.add(ids=[c["id"] for c in chunks], documents=[c["text"] for c in chunks],
            metadatas=[c["meta"] for c in chunks], embeddings=emb.tolist())
    print(f"인덱스 생성: {len(chunks)}개 청크 → {DB_PATH}/")
    return col


# ---------------------------------------------------------------------------
# 3. 검색 → 프롬프트 → 답변
# ---------------------------------------------------------------------------
def search(question, k=TOP_K):
    col = build_index()
    q = embedder().encode([f"query: {question}"], normalize_embeddings=True)
    # [A-허점-03 정보검색 실패] 질문을 그대로 임베딩해 top-3 만 가져옴 — 키워드 검색 · 재순위 · 질문 재작성 없음,
    #   메타데이터 필터(where) 미사용
    r = col.query(query_embeddings=q.tolist(), n_results=k)
    return [{"doc_id": i, "text": d, "meta": m, "score": round(1 - dist, 3)}
            for i, d, m, dist in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0])]


# [A-허점-04 실시간 정보 부족] 주문 · 배송 · 쿠폰 등 시스템 데이터를 조회할 방법이 없음 (정적 문서만 검색)
# [A-허점-05 신뢰성] 근거에 없으면 모른다고 하라는 지시, 문서 상태 · 우선순위 판단 기준, 오늘 날짜가 없음
PROMPT = """다음 문서를 참고하여 고객 질문에 답변하세요.

참고 문서:
{context}

고객 질문:
{question}
"""


def run_rag(question, customer_id=None, history=None):
    """run_agent 와 같은 형태로 결과를 돌려준다 (평가 스크립트 호환). customer_id 는 쓰지 않음."""
    t0 = time.time()
    docs = search(question)
    # [A-허점-06 프롬프트 인젝션] 검색 문서 본문을 검사 없이 그대로 프롬프트에 삽입
    context = "\n\n".join(d["text"] for d in docs)
    messages = list(history or [])
    messages.append({"role": "user", "content": PROMPT.format(context=context, question=question)})
    resp = client.chat.completions.create(model=MODEL, messages=messages, temperature=0)
    answer = resp.choices[0].message.content
    # [A-허점-07 데이터 정합성] 답변과 근거 문서의 일치 여부를 검증하지 않음
    return {
        "answer": answer,
        "tool_calls": [{"tool": "search_knowledge", "args": {"query": question},
                        "result": [f"{d['doc_id']}({d['meta'].get('status')})" for d in docs]}],
        "retrieved": [{"doc_id": d["doc_id"], "status": d["meta"].get("status"), "score": d["score"]} for d in docs],
        "usage": {"llm_calls": 1, "prompt_tokens": resp.usage.prompt_tokens,
                  "completion_tokens": resp.usage.completion_tokens},
        "latency_s": round(time.time() - t0, 2),
        "messages": messages + [{"role": "assistant", "content": answer}],
    }


def _print_result(out):
    for d in out["retrieved"]:
        print(f"[검색] {d['doc_id']} · {d['status']} · 유사도 {d['score']}")
    print("[답변]", out["answer"])
    u = out["usage"]
    print(f"  (응답 시간 {out['latency_s']}초 · input {u['prompt_tokens']} token · output {u['completion_tokens']} token)")


def chat():
    print("Baseline A 대화 모드 · 종료: exit / quit / 종료 (또는 Ctrl+C)")
    build_index()
    history = []
    while True:
        try:
            q = input("\n[고객] ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q.lower() in ("exit", "quit", "종료"):
            break
        out = run_rag(q, history=history)
        _print_result(out)
        # [A-허점-08 비용] 이전 턴의 검색 문서 전문까지 포함한 프롬프트를 계속 누적
        history = out["messages"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?")
    ap.add_argument("--chat", action="store_true")
    ap.add_argument("--rebuild", action="store_true", help="Vector DB 인덱스를 지우고 다시 생성")
    a = ap.parse_args()
    if a.rebuild:
        build_index(rebuild=True)
    if a.chat:
        chat()
    elif a.query:
        _print_result(run_rag(a.query))
    elif not a.rebuild:
        chat()
