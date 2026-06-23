from app.db import create_db_connection


def main():
    try:
        print("正在連線到 Azure 伺服器，請稍候...")
        conn = create_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Doctor")
        count = cursor.fetchone()[0]
        print(f"🎉 連線成功！Doctor 表裡共有 {count} 筆資料。")
    except Exception as exc:
        print("❌ 連線失敗")
        print(exc)
    finally:
        if 'conn' in locals() and conn:
            conn.close()


if __name__ == "__main__":
    main()
