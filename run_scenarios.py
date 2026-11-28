"""대화 시나리오로 '운영 중 발생하는 문제' 를 재현한다.

    uv run python run_scenarios.py              # 전체 시나리오
    uv run python run_scenarios.py S07 S11      # 일부만
    uv run python run_scenarios.py --agent improved S11 S12 S13 # 개선 에이전트로 실행
    uv run python run_scenarios.py --agent secure S11 S12 S13   # 코드 가드 방식으로 실행

scenarios/chat_scenarios.json 의 각 시나리오를 --chat 대화 모드와 같은 방식(이전 턴을 history 로 전달)으로 실행하고,
턴별 도구 호출 · 답변 · 토큰 · 지연을 출력한 뒤 results/scenarios_<시각>.jsonl 에 저장한다.
문제가 실제로 재현됐는지는 각 시나리오의 'watch' 항목을 보고 사람이 판단한다.
"""
import json
import pathlib
import sys
import time

AGENT = sys.argv[sys.argv.index("--agent") + 1] if "--agent" in sys.argv else "baseline"
if AGENT == "improved":
    from improved_agent import run_agent as _improved_run

    def run_agent(q, customer, history=None, key=None):
        return _improved_run(q, customer, history=history)
elif AGENT == "secure":
    from secure_agent import run_agent as _secure_run

    def run_agent(q, customer, history=None, key=None):
        return _secure_run(q, customer, history=history, session_key=key)
else:
    from baseline_agent import run_agent as _base_run

    def run_agent(q, customer, history=None, key=None):
        return _base_run(q, customer, history=history)

SCENARIO_FILE = pathlib.Path("scenarios/chat_scenarios.json")


def run_scenario(sc, key=None):
    history, turns = [], []
    for q in sc["turns"]:
        try:
            out = run_agent(q, sc["customer"], history=history, key=key)
            err = None
        except Exception as e:  # 도구 장애 등으로 대화가 중단되는 경우도 기록
            out, err = {"answer": None, "tool_calls": [], "usage": {}, "latency_s": None}, f"{type(e).__name__}: {e}"
        messages = out.pop("messages", history)
        turns.append({"query": q, "error": err, **out})
        print(f"\n  [고객] {q}")
        for t in out["tool_calls"]:
            print(f"    [호출] {t['tool']} {t['args']}")
        if err:
            print(f"    [크래시] {err}")
            break  # 실제 서비스라면 여기서 대화가 끊김
        u = out["usage"]
        print(f"  [답변] {out['answer']}")
        if out.get("security", {}).get("blocked_by"):
            print(f"    [보안] {out['security']['blocked_by']} · 누적 {out['security']['flags']}회")
        print(f"    ({out['latency_s']}초 · LLM {u['llm_calls']}회 · input {u['prompt_tokens']} token)")
        history = messages  # --chat 모드와 동일하게 도구 결과까지 전부 누적
    return turns


def main():
    scenarios = json.loads(SCENARIO_FILE.read_text(encoding="utf-8"))
    ids = [x for x in sys.argv[1:] if x not in ("--agent", "secure", "baseline", "improved")]
    if ids:
        scenarios = [s for s in scenarios if s["id"] in ids]

    out_dir = pathlib.Path("results")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"scenarios_{AGENT}_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for sc in scenarios:
            for r in range(sc.get("repeat", 1)):
                print("\n" + "=" * 80)
                print(f"{sc['id']} [{sc['area']}] {sc['problem']} · 고객 {sc['customer']}"
                      + (f" · 반복 {r + 1}/{sc['repeat']}" if sc.get("repeat", 1) > 1 else ""))
                print(f"  확인할 점: {sc['watch']}")
                turns = run_scenario(sc, key=f"{sc['id']}#{r}")
                f.write(json.dumps({**sc, "run": r, "result": turns}, ensure_ascii=False) + "\n")
    print(f"\n저장: {out_path}")


if __name__ == "__main__":
    main()
