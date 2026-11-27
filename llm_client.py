"""LLM 연결 공통 코드 — 다른 파일에서 from llm_client import client, MODEL 로 사용"""
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # 같은 폴더의 .env 를 읽음

MODEL = os.environ["LLM_MODEL"]
client = OpenAI(
    base_url=os.getenv("LLM_BASE_URL", "http://localhost:8000/v1"),
    api_key=os.getenv("LLM_API_KEY", "none"),
)
