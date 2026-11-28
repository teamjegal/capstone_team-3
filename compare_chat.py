"""비교 대화 모드 — 같은 질문을 Baseline A(RAG)와 Baseline B(Agent)에 차례로 넣고 답을 나란히 본다.

    uv run python compare_chat.py --customer C0001

A 와 B 는 대화 기록(history)을 각자 따로 유지한다. A 는 고객 ID 를 쓰지 않는다 (주문 조회 기능 없음).
종료: exit / quit / 종료 (또는 Ctrl+C)
"""
import argparse

from baseline_agent import run_agent
from baseline_rag import build_index, run_rag


def show_a(out):
    print("\n── Baseline A (RAG) " + "─" * 40)
    for d in out["retrieved"]:
        print(f"[검색] {d['doc_id']} · {d['status']} · 유사도 {d['score']}")
    print("[답변]", out["answer"])
    u = out["usage"]
    print(f"  ({out['latency_s']}초 · LLM {u['llm_calls']}회 · input {u['prompt_tokens']} token)")


def show_b(out):
    print("\n── Baseline B (Agent) " + "─" * 38)
    for t in out["tool_calls"]:
        print(f"[호출] {t['tool']} {t['args']}")
    print("[답변]", out["answer"])
    u = out["usage"]
    print(f"  ({out['latency_s']}초 · LLM {u['llm_calls']}회 · input {u['prompt_tokens']} token)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--customer", default="C0001", help="로그인한 고객 ID (Baseline B 만 사용)")
    a = ap.parse_args()

    build_index()  # A 의 Vector DB 준비 (없으면 생성)
    print(f"비교 대화 모드 · 로그인 고객 {a.customer} (B 만 사용) · 종료: exit / quit / 종료")
    hist_a, hist_b = [], []
    while True:
        try:
            q = input("\n" + "=" * 60 + "\n[고객] ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q.lower() in ("exit", "quit", "종료"):
            break

        out_a = run_rag(q, history=hist_a)
        show_a(out_a)
        hist_a = out_a["messages"]

        try:
            out_b = run_agent(q, a.customer, history=hist_b)
        except Exception as e:  # B 의 도구 장애로 비교 대화 전체가 끊기지 않도록 (B 자체 허점은 그대로)
            print("\n── Baseline B (Agent) " + "─" * 38)
            print(f"[크래시] {type(e).__name__}: {e}")
            continue
        show_b(out_b)
        hist_b = out_b["messages"]


if __name__ == "__main__":
    main()
