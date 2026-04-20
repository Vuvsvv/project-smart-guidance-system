import json
import os
from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.schema import Document

# 1. 設定 LLM 和 Embedding 模型

from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# Gemini API Key 
GEMINI_API_KEY = ""


Settings.llm = GoogleGenAI(
    model="gemini-3-flash-preview",
    api_key=GEMINI_API_KEY,
)


Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-m3"
)


# 2. 載入 JSON 資料 → 轉成 Document


def load_doctors(filepath: str) -> list[Document]:
    """載入醫師資料，每位醫師一個 Document"""
    with open(filepath, encoding="utf-8") as f:
        raw = json.load(f)

    documents = []
    for item in raw:
        code = item.get("code", "")
        name = item.get("name", "")

 
        if code.isdigit() or code == "請選擇看診科別":
            continue

        parts = name.split("_")
        if len(parts) != 2:
            continue

        dept, doctor = parts


        text = (
            f"醫師姓名：{doctor}\n"
            f"所屬科別：{dept}\n"
            f"查詢關鍵字：{dept} {doctor}"
        )

        documents.append(Document(
            text=text,
            metadata={"dept": dept, "doctor": doctor}
        ))

    print(f"醫師資料載入完成：共 {len(documents)} 筆")
    return documents


def load_departments(filepath: str, label: str) -> list[Document]:

    with open(filepath, encoding="utf-8") as f:
        raw = json.load(f)

    documents = []
    for category, dept_list in raw.items():
        text = (
            f"科別大類：{category}\n"
            f"類型：{label}\n"
            f"包含門診：{'、'.join(dept_list)}\n"
            f"查詢關鍵字：{category} {' '.join(dept_list)}"
        )
        documents.append(Document(
            text=text,
            metadata={"category": category, "type": label}
        ))

    print(f" {label}科別資料載入完成：共 {len(documents)} 個大類")
    return documents



# 3. 建立向量索引


def build_index():

    docs = []
    docs += load_doctors("doctor.json")
    docs += load_departments("一般門診初診.json", "初診")
    docs += load_departments("一般門診複診.json", "複診")

    print(f"\n 總共建立 {len(docs)} 個文件，開始向量化（第一次較慢）")
    index = VectorStoreIndex.from_documents(
        docs,
        show_progress=True
    )

    print(" 索引建立完成 \n")
    return index



# 4. 建立查詢引擎（召回 + 生成）


def build_query_engine(index):
    query_engine = index.as_query_engine(
        similarity_top_k=5,
        response_mode="compact"
    )
    return query_engine



# 5. 自訂系統 AI Prompt


from llama_index.core import PromptTemplate

SYSTEM_PROMPT = PromptTemplate(
    """你是台北榮民醫院的導引助理。根據以下醫院資料回答問題，回答要簡潔，不要有多餘的問候語或祝福語。

醫院資料：
---------------------
{context_str}
---------------------

問題：{query_str}

回答規則：
1. 問症狀或要看什麼科 → 一句話說建議科別，再條列醫師名字
2. 問某科有哪些醫師 → 直接條列醫師名字，不需要其他說明
3. 只有明確急症關鍵字（如：昏迷、大量出血、呼吸困難）才提醒急診
4. 禁止：問候語、祝福語、「辛苦您了」、「很高興為您服務」等廢話
5. 格式範例：
   建議掛：骨科
   醫師：
   - 王OO
   - 李OO
"""
)


# 6. 主程式：互動問答


def main():
    print("=" * 50)
    print("  台北榮民醫院 RAG 導引系統")
    print("=" * 50)

    index = build_index()
    query_engine = build_query_engine(index)

    query_engine.update_prompts(
        {"response_synthesizer:text_qa_template": SYSTEM_PROMPT}
    )

    test_queries = [
        "手腫起來，可能是跌倒骨折，要看哪科？",
        "肚子一直痛、拉肚子，要掛什麼科？",
        "心臟內科有哪些醫師？",
        "眼睛看不清楚，要看什麼科？",
        "我媽媽最近記憶力很差，常常忘東忘西，要看哪裡？",
    ]

    print("\n 開始測試查詢...\n")
    for i, query in enumerate(test_queries, 1):
        print(f" 問題 {i}：{query}")
        response = query_engine.query(query)
        print(f" 回答：{response}\n")
        print("-" * 40)

    print("\n  進入互動模式（輸入 q 結束）\n")
    while True:
        user_input = input("請輸入您的問題：").strip()
        if user_input.lower() == "q":
            break
        if not user_input:
            continue
        response = query_engine.query(user_input)
        print(f" {response}\n")


if __name__ == "__main__":
    main()
