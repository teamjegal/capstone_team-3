"""1. 기본 호출 — 연결 확인"""
import time

from llm_client import client, MODEL

t0 = time.time()
resp = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": "너는 이커머스 고객 상담원이야. 한국어로 짧게 답해."},
        {"role": "user", "content": "안녕하세요, 연결 확인 중입니다."},
    ],
    temperature=0,
)
print(resp.choices[0].message.content)
print(f"\n응답 시간 {time.time() - t0:.1f}초 · "
      f"input {resp.usage.prompt_tokens} token · output {resp.usage.completion_tokens} token")
