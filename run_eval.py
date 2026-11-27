"""평가 데이터셋으로 Baseline Agent 를 돌려 문제를 재현 · 측정한다.

    uv run python run_eval.py                    # 공개 평가셋 30개 전체
    uv run python run_eval.py --ids PUB-001 PUB-017
    uv run python run_eval.py --ids PUB-001 --repeat 3   # 실행 일관성(비결정성) 확인

결과는 results/eval_<시각>.jsonl 에 케이스별로 저장된다.
채점은 단순 문자열 포함 여부 + 도구 이름 비교라서 참고용 지표다.
"""
import argparse
import json
import pathlib
import time
import traceback

from baseline_agent import run_agent


def find_eval_file():
    for p in [pathlib.Path("data/eval_public.jsonl"), pathlib.Path("data/eval/eval_public.jsonl")]:
        if p.exists():
            return p
    raise FileNotFoundError("data/eval_public.jsonl 을 찾을 수 없습니다")


def score(case, out):
    exp = case["expected"]
    answer = out.get("answer") or ""
    called = [t["tool"] for t in out.get("tool_calls", [])]
    expected_tools = [t["tool"] for t in exp.get("tool_calls", [])]
    return {
        "must_include_hit": [s for s in exp.get("must_include", []) if s in answer],
        "must_include_miss": [s for s in exp.get("must_include", []) if s not in answer],
        "must_not_include_violated": [s for s in exp.get("must_not_include", []) if s in answer],
        "missing_tools": [t for t in expected_tools if t not in called],
        "extra_tool_calls": max(0, len(called) - len(expected_tools)),
        "escalated": "escalate_to_agent" in called,
        "expected_action": exp.get("action"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*", help="실행할 케이스 id (생략 시 전체)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--repeat", type=int, default=1)
    a = ap.parse_args()

    cases = [json.loads(l) for l in find_eval_file().read_text(encoding="utf-8").splitlines() if l.strip()]
    if a.ids:
        cases = [c for c in cases if c["id"] in a.ids]
    if a.limit:
        cases = cases[:a.limit]

    out_dir = pathlib.Path("results")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"eval_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"

    rows = []
    with out_path.open("w", encoding="utf-8") as f:
        for case in cases:
            for r in range(a.repeat):
                try:
                    out = run_agent(case["query"], case["session"]["customer_id"],
                                    history=case.get("conversation_history"))
                    out.pop("messages", None)
                    err = None
                except Exception as e:  # 에이전트 크래시도 결과로 기록
                    out, err = {"answer": None, "tool_calls": [], "usage": {}, "latency_s": None}, \
                        f"{type(e).__name__}: {e}"
                    traceback.print_exc()
                s = score(case, out) if err is None else {}
                row = {"id": case["id"], "run": r, "category": case["category"], "query": case["query"],
                       "error": err, **out, "score": s, "trap": case.get("trap")}
                rows.append(row)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                inc = case["expected"].get("must_include", [])
                status = "ERROR" if err else f"포함 {len(s['must_include_hit'])}/{len(inc)}"
                tools = " → ".join(t["tool"] for t in out["tool_calls"]) or "-"
                print(f"{case['id']}#{r} [{case['category']}] {status} · {out['latency_s']}s · {tools}")

    ok = [r for r in rows if not r["error"]]
    print("\n===== 요약 =====")
    print(f"케이스 {len(rows)} · 크래시 {len(rows) - len(ok)}")
    if ok:
        full = sum(1 for r in ok if not r["score"]["must_include_miss"] and not r["score"]["must_not_include_violated"])
        print(f"must_include 전부 포함 & 금지어 없음: {full}/{len(ok)}")
        print(f"평균 지연 {sum(r['latency_s'] for r in ok) / len(ok):.1f}s · "
              f"평균 LLM 호출 {sum(r['usage']['llm_calls'] for r in ok) / len(ok):.1f}회 · "
              f"평균 input token {sum(r['usage']['prompt_tokens'] for r in ok) / len(ok):.0f}")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
