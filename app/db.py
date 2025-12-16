import os
import sqlite3
from threading import Lock

from models.document import Document

class Database:
    DB_NAME = "document.db"
    def __init__(self, repo):
        self.repo = repo

    def save_repo(self):
        with sqlite3.connect(Database.DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS repo(
                    id TEXT PRIMARY KEY,
                    document_json TEXT NOT NULL
                )
            """)

            for doc_id, doc_obj in self.repo.documents.items():
                doc_json_str = doc_obj.json()

                cursor.execute(
                    """INSERT OR REPLACE INTO repo (id, document_json) VALUES (?, ?)""",
                    (doc_id, doc_json_str)
                )

            conn.commit()
            print(f"Document repo saved successfully into: {Database.DB_NAME}")

    def load_repo(self):
        if not os.path.exists(Database.DB_NAME):
            print("No saved document repo found. Starting from scratch.")
            return

        conn = sqlite3.connect(Database.DB_NAME)
        cursor = conn.cursor()

        try:
            cursor.execute("""SELECT id, document_json FROM repo""")
            docs = cursor.fetchall()

            for doc_id, doc_json_str in docs:
                doc_obj = Document(id=doc_id)
                doc_obj.importJson(doc_json_str)
                self.repo.documents[doc_id] = doc_obj

            print(f"Document repo loaded successfully from: {Database.DB_NAME}")

        except sqlite3.OperationalError as e:
            print(f"Error while loading document repo: {e}. Starting from scratch.")
            self.repo.documents = {}

        finally:
            conn.close()
