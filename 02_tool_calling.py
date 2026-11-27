"""2. Tool Calling — 모델이 도구를 요청하면 실행해서 결과를 돌려주는 반복 구조"""
import json

from llm_client import client, MODEL

ORDERS = {o["order_id"]: o for o in json.load(open("data/system/orders.json", encoding="utf-8"))}
SESSION_CUSTOMER = "C0017"  # 로그인한 고객 (세션에서 온 값 — 모델이 정하는 값이 아님)


def get_order(order_id: str) -> dict:
    order = ORDERS.get(order_id)
    if order is None:
        return {"error": "NOT_FOUND"}
    if order["customer_id"] != SESSION_CUSTOMER:  # 소유자 검증은 코드에서
        return {"error": "FORBIDDEN"}
    return {"order_id": order_id, "status": order["status"], "items": order["items"]}


TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_order",
        "description": "주문번호로 주문 정보를 조회",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "예: ORD-20260901-0001"}},
            "required": ["order_id"],
        },
    },
}]
FUNCS = {"get_order": get_order}

messages = [
    {"role": "system", "content": "너는 이커머스 고객 상담원이야. 주문 정보는 반드시 도구로 조회해."},
    {"role": "user", "content": "ORD-20260901-0001 주문 상태 알려줘"},
]

for turn in range(5):  # 무한 반복 방지
    resp = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS, temperature=0)
    msg = resp.choices[0].message
    if not msg.tool_calls:  # 도구 요청이 없으면 최종 답변
        print("[답변]", msg.content)
        break
    messages.append(msg)  # 모델의 도구 요청을 대화에 추가
    for call in msg.tool_calls:
        args = json.loads(call.function.arguments)
        result = FUNCS[call.function.name](**args)
        print(f"[호출] {call.function.name} {args}")
        messages.append({  # 실행 결과를 role=tool 로 돌려줌
            "role": "tool",
            "tool_call_id": call.id,
            "content": json.dumps(result, ensure_ascii=False),
        })
