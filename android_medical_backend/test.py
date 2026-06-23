import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

pwd = os.getenv("DB_PASSWORD")
print("DB_PASSWORD 有沒有讀到：", bool(pwd))
print("DB_PASSWORD 長度：", len(pwd) if pwd else 0)

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=medichain-server.database.windows.net;"
    "DATABASE=MediChainDB;"
    "UID=medichain_admin;"
    f"PWD={pwd};"
    "Encrypt=yes;"
    "Connection Timeout=30;"
)
print("連線成功")
conn.close()