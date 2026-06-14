import os
from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.google_genai import GoogleGenAI
 

load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
 

Settings.llm = GoogleGenAI(
    model="gemini-3-flash-preview",
    api_key=GEMINI_API_KEY,
)
Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-m3"
)