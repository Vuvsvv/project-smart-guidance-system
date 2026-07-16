import os
import time
from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.llms.cerebras import Cerebras

load_dotenv()

CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")
Settings.llm = Cerebras(
    model=CEREBRAS_MODEL,
    api_key=os.getenv("CEREBRAS_API_KEY"),
    max_tokens=int(os.getenv("CEREBRAS_MAX_TOKENS", "8192")),
    context_window=65536,
)
print(f"  LLM：Cerebras（{CEREBRAS_MODEL}）")


def ask_llm(prompt: str, label: str = "AI", max_tokens: int | None = None) -> str:
    
    llm = Settings.llm
    saved = None
    if max_tokens is not None:
        saved = llm.max_tokens
        llm.max_tokens = max_tokens

    t0 = time.perf_counter()
    try:
        raw = str(llm.complete(prompt))
    finally:
        if saved is not None:
            llm.max_tokens = saved

    elapsed = time.perf_counter() - t0
    print(f"  [{label}] AI 耗時 {elapsed:.2f} 秒")
    return raw.strip().replace("```json", "").replace("```", "").strip()
