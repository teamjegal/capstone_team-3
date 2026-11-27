"""Baseline B — Naive Agent

LLM 이 질문을 보고 어떤 도구를 어떤 순서로 몇 번 부를지 전부 스스로 결정하는 가장 단순한 에이전트.
일부러 '운영 중 발생하는 문제' 들이 재현되도록 허점을 남겨 두었다.
허점 위치는 코드 안의 `# [허점-XX]` 주석과 docs/baseline_flaws.md 에 정리되어 있다.

    uv run python baseline_agent.py "내 주문 언제 도착해?" --customer C0001
"""
import argparse
import json
import pathlib
import re
import time

import yaml

from llm_client import client, MODEL

DATA = pathlib.Path("data")


def _load_json(rel):
    return json.loads((DATA / rel).read_text(encoding="utf-8"))


ORDERS = _load_json("system/orders.json")
SHIPMENTS = _load_json("system/shipments.json")
PRODUCTS = {p["product_id"]: p for p in _load_json("system/products.json")}
RETURN_CONDITIONS = {c["product_id"]: c for c in _load_json("system/product_return_conditions.json")}
CUSTOMERS = {c["customer_id"]: c for c in _load_json("system/customers.json")}
COUPONS = _load_json("system/coupons.json")


# ---------------------------------------------------------------------------
# 지식 문서 (RAG)
# ---------------------------------------------------------------------------
def load_policy_docs(path):
    """정책 문서(.md) 를 '## [DOC_ID] 제목' 단위로 나누고 yaml 메타데이터를 읽음"""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    docs = []
    for chunk in re.split(r"\n(?=## \[)", text)[1:]:
        m = re.search(r"```yaml\n(.*?)```", chunk, re.S)
        meta = yaml.safe_load(m.group(1)) if m else {}
        body = re.sub(r"```yaml\n.*?```", "", chunk, flags=re.S).strip()
        docs.append({"meta": meta, "text": body})
    return docs


# [허점-01 정보검색 실패] faq.json · consultation_history.json 은 색인하지 않음 → FAQ 에만 있는 답은 못 찾음
# [허점-02 정보충돌] status(approved/deprecated/draft/rejected/unverified/expired) 와 적용기간을 보지 않고 전부 색인
DOCS = [d for f in sorted((DATA / "knowledge").glob("*.md")) for d in load_policy_docs(f)]


def _bigrams(s):
    s = re.sub(r"\s+", "", s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


# ---------------------------------------------------------------------------
# 도구 (모의 백엔드 API)
# ---------------------------------------------------------------------------
def search_knowledge(query: str) -> list:
    # [허점-01] 글자 bigram 겹침만으로 순위 → 긴 문서가 무조건 유리, 동의어·의미 검색 불가
    q = _bigrams(query)
    ranked = sorted(DOCS, key=lambda d: len(q & _bigrams(d["text"])), reverse=True)[:3]
    # [허점-11 간접 프롬프트 인젝션] 문서 본문을 걸러내지 않고 그대로 모델에 전달
    # [허점-13 비용] 문서 전문을 통째로 넣어 컨텍스트가 커짐
    return [{"doc_id": d["meta"].get("doc_id"), "title": d["meta"].get("title"), "text": d["text"]} for d in ranked]


def list_orders(customer_id: str) -> list:
    # [허점-10 접근권한] customer_id 를 모델이 정한 값 그대로 사용 — 세션 고객과 같은지 확인하지 않음
    # [허점-13 비용] 주문 전체 필드(결제·주소·이력)를 그대로 반환, 기간 제한·정렬 없음
    return [o for o in ORDERS if o["customer_id"] == customer_id]


def get_order(order_id: str) -> dict:
    # [허점-10 접근권한] 주문 소유자 검증 없음 → 주문번호만 알면 누구 주문이든 조회
    for o in ORDERS:
        if o["order_id"] == order_id:
            return o
    # [허점-15 예외처리] 없는 주문이면 예외 발생 → 에이전트 전체가 죽음
    raise KeyError(f"order not found: {order_id}")


def get_shipment(order_id: str) -> dict:
    # [허점-10 접근권한] 소유자 검증 없음
    for s in SHIPMENTS:
        if s["order_id"] == order_id:
            return s
    return {}  # [허점-07 데이터정합성] 빈 결과를 돌려줘도 모델이 그럴듯하게 지어낼 수 있음


def search_products(query: str) -> list:
    return [{"product_id": p["product_id"], "name": p["name"], "category": p["category"], "sale_price": p["sale_price"]}
            for p in PRODUCTS.values() if query in p["name"]][:10]


def get_product(product_id: str) -> dict:
    return PRODUCTS[product_id]


def get_return_conditions(product_id: str) -> dict:
    return RETURN_CONDITIONS[product_id]


def check_cancellation(order_id: str) -> dict:
    order = get_order(order_id)
    # [허점-06 비즈니스로직 위반] '배송중' 도 취소 가능으로 판단, 주문제작(각인 등)·설치상품 예외도 안 봄
    cancellable = order["status"] in ("결제완료", "상품준비중", "배송중")
    return {"order_id": order_id, "status": order["status"], "cancellable": cancellable}


def check_refund(order_id: str, product_id: str) -> dict:
    cond = RETURN_CONDITIONS.get(product_id, {})
    # [허점-06 비즈니스로직 위반] 단순변심 가능 여부 플래그만 확인
    #   반품 기한(simple_change_window_days), 수령일, non_returnable_cases(개봉·설치·착용 등),
    #   final sale, 결제금액·쿠폰 차감은 전혀 계산하지 않음
    return {
        "order_id": order_id,
        "product_id": product_id,
        "refundable": bool(cond.get("simple_change_returnable", True)),
        "return_shipping_fee": cond.get("return_shipping_fee"),
    }


def check_coupon_restoration(order_id: str) -> dict:
    order = get_order(order_id)
    # [허점-06 비즈니스로직 위반] 쿠폰이 있으면 무조건 복원 가능 — 만료일·부분취소·쿠폰 종류 무시
    return {"order_id": order_id, "coupon_id": order.get("coupon_id"), "restorable": order.get("coupon_id") is not None}


def list_coupons(customer_id: str, status: str = None) -> list:
    # [허점-10 접근권한] 다른 고객 쿠폰도 조회 가능
    return [c for c in COUPONS if c["customer_id"] == customer_id and (status is None or c["status"] == status)]


def get_customer_profile(customer_id: str) -> dict:
    # [허점-10 접근권한·개인정보] 연락처·이메일·주소·내부 메모까지 통째로 반환
    return CUSTOMERS[customer_id]


def escalate_to_agent(reason_code: str) -> dict:
    # [허점-09 예외처리 실패] 언제 이관해야 하는지 규칙은 코드에 없음 — 전부 모델 판단에 맡김
    return {"ticket_id": f"TKT-{int(time.time())}", "reason_code": reason_code, "status": "접수됨"}


FUNCS = {f.__name__: f for f in [
    search_knowledge, list_orders, get_order, get_shipment, search_products, get_product,
    get_return_conditions, check_cancellation, check_refund, check_coupon_restoration,
    list_coupons, get_customer_profile, escalate_to_agent,
]}


def _tool(name, desc, **params):
    required = [k for k, v in params.items() if not v.pop("optional", False)]
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": params, "required": required}}}


_S = {"type": "string"}
TOOLS = [
    _tool("search_knowledge", "배송·환불·쿠폰·등급 등 상담 정책·약관·매뉴얼 문서 검색", query=dict(_S)),
    _tool("list_orders", "고객의 주문 목록 조회 (주문번호를 모를 때 먼저 사용)", customer_id=dict(_S)),
    _tool("get_order", "주문번호로 주문 상세 조회", order_id=dict(_S, description="예: ORD-20260901-0001")),
    _tool("get_shipment", "주문번호로 배송 상태 조회", order_id=dict(_S)),
    _tool("search_products", "상품명으로 상품 검색", query=dict(_S)),
    _tool("get_product", "상품 상세 조회", product_id=dict(_S, description="예: P001")),
    _tool("get_return_conditions", "상품별 교환·환불 조건 조회", product_id=dict(_S)),
    _tool("check_cancellation", "주문 취소 가능 여부 확인", order_id=dict(_S)),
    _tool("check_refund", "환불 가능 여부 확인", order_id=dict(_S), product_id=dict(_S)),
    _tool("check_coupon_restoration", "주문에 사용한 쿠폰 복원 가능 여부 확인", order_id=dict(_S)),
    _tool("list_coupons", "고객 쿠폰 목록 조회", customer_id=dict(_S),
          status=dict(_S, description="사용가능/사용완료/만료", optional=True)),
    _tool("get_customer_profile", "고객 정보 조회 (등급·적립금 등)", customer_id=dict(_S)),
    _tool("escalate_to_agent", "상담원에게 연결", reason_code=dict(_S)),
]

# [허점-03 의도파악] 의도 분류 단계 없이 질문을 바로 모델에 던짐 → 복합 질문 일부 누락, 애매한 질문에 되묻지 않음
# [허점-08 할루시네이션] '고객 만족 최우선' 만 강조 — 근거 없는 내용 금지, 모르면 모른다고 하라는 규칙 없음
# [허점-09] 에스컬레이션 코드(E01~E10)와 이관 기준을 알려주지 않음
# [허점-04 실시간 정보] 오늘 날짜를 알려주지 않음 → '언제 도착', '며칠 지났는지' 계산이 틀림
SYSTEM_PROMPT = """너는 A사 이커머스 고객 상담원이야. 고객 만족을 최우선으로 친절하게 한국어로 답해.
주문·배송·쿠폰·환불 정보는 도구로 조회하고, 필요하면 도구를 자유롭게 사용해.
현재 로그인한 고객 ID: {customer_id}"""


def run_agent(query, customer_id, history=None, max_turns=10, temperature=0.7, verbose=False):
    """질문 하나를 처리하고 답변 · 도구 호출 기록 · 토큰 · 지연시간을 돌려준다."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(customer_id=customer_id)}]
    messages += history or []
    # [허점-11 직접 프롬프트 인젝션] 사용자 입력을 검사 없이 그대로 전달
    messages.append({"role": "user", "content": query})

    trace, usage = [], {"llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
    t0 = time.time()
    answer = None
    # [허점-12 불필요한 도구 호출] 최대 10턴까지 허용, 같은 도구·인자 반복 호출을 막거나 캐시하지 않음
    for _ in range(max_turns):
        # [허점-05 비결정성] temperature 0.7 → 같은 질문에도 도구 호출 순서·횟수·답변이 달라짐
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, temperature=temperature)
        usage["llm_calls"] += 1
        usage["prompt_tokens"] += resp.usage.prompt_tokens
        usage["completion_tokens"] += resp.usage.completion_tokens
        msg = resp.choices[0].message
        if not msg.tool_calls:
            answer = msg.content
            break
        messages.append(msg)
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)
            # [허점-15 도구장애] try/except 없음 — 도구 예외·잘못된 도구 이름이면 그대로 크래시
            result = FUNCS[call.function.name](**args)
            trace.append({"tool": call.function.name, "args": args})
            if verbose:
                print(f"[호출] {call.function.name} {args}")
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, ensure_ascii=False, default=str)})
    # [허점-07 데이터정합성] 최종 답변을 도구 결과와 대조하는 검증 단계 없음
    # [허점-14 문제추적] trace 를 파일로 남기지 않음 (어떤 문서·도구 결과 때문에 틀렸는지 사후 추적 불가)
    return {
        "answer": answer,
        "tool_calls": trace,
        "usage": usage,
        "latency_s": round(time.time() - t0, 2),
    }


def _print_result(out):
    print("[답변]", out["answer"])
    print(f"  (응답 시간 {out['latency_s']}초 · LLM 호출 {out['usage']['llm_calls']}회 · "
          f"input {out['usage']['prompt_tokens']} token · output {out['usage']['completion_tokens']} token)")


def chat(customer_id):
    """터미널 대화 모드 — 이전 질문·답변을 history 로 넘겨 대화를 이어간다."""
    print(f"대화 모드 · 로그인 고객 {customer_id} · 종료: exit / quit / 종료 (또는 Ctrl+C)")
    history = []
    while True:
        try:
            query = input("\n[고객] ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not query:
            continue
        if query.lower() in ("exit", "quit", "종료"):
            break
        out = run_agent(query, customer_id, history=history, verbose=True)
        _print_result(out)
        # [허점-12] 도구 호출 결과는 history 에 남기지 않음 — 다음 턴에서 같은 조회를 반복하기 쉬움
        history += [{"role": "user", "content": query},
                    {"role": "assistant", "content": out["answer"] or ""}]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", help="질문 (생략하면 --chat 과 같음)")
    ap.add_argument("--customer", default="C0001", help="로그인한 고객 ID (세션)")
    ap.add_argument("--chat", action="store_true", help="터미널 대화 모드")
    a = ap.parse_args()
    if a.chat or not a.query:
        chat(a.customer)
    else:
        _print_result(run_agent(a.query, a.customer, verbose=True))
