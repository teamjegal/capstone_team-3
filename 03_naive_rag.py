"""3. Naive RAG 파이프라인 — 검색한 문서를 프롬프트에 넣어 답변 생성"""
import pathlib
import re

import yaml

from llm_client import client, MODEL


def load_policy_docs(path):
    """정책 문서(.md) 한 파일을 '## [DOC_ID] 제목' 단위로 나누고 yaml 메타데이터를 읽음"""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    docs = []
    for chunk in re.split(r"\n(?=## \[)", text)[1:]:
        meta = yaml.safe_load(re.search(r"```yaml\n(.*?)```", chunk, re.S).group(1))
        body = re.sub(r"```yaml\n.*?```", "", chunk, flags=re.S).strip()
        docs.append({"meta": meta, "text": body})
    return docs


DOCS = [d for f in sorted(pathlib.Path("data/knowledge").glob("*.md")) for d in load_policy_docs(f)]


def bigrams(s):
    s = re.sub(r"\s+", "", s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def search_policy(question, k=3):
    """가장 단순한 검색 — 질문과 글자 2개 단위로 많이 겹치는 문서 k개 (임베딩 검색으로 바꿔 볼 자리)"""
    q = bigrams(question)
    ranked = sorted(DOCS, key=lambda d: len(q & bigrams(d["text"])), reverse=True)
    return ranked[:k]


def ask_llm(prompt):
    resp = client.chat.completions.create(
        model=MODEL, messages=[{"role": "user", "content": prompt}], temperature=0)
    return resp.choices[0].message.content


def pipeline(question):
    documents = search_policy(question)
    context = "\n\n".join(d["text"] for d in documents)

    prompt = f"""다음 문서를 참고하여 고객 질문에 답변하세요.

참고 문서:
{context}

고객 질문:
{question}
"""
    answer = ask_llm(prompt)
    return answer, documents


if __name__ == "__main__":
    answer, documents = pipeline("무료 배송 기준이 얼마인가요?")
    for d in documents:
        print(f"[검색] {d['meta']['doc_id']} · {d['meta']['status']} · {d['meta']['title']}")
    print("[답변]", answer)
