"""
数据库服务
SQLite 持久化：OCR 结果、反馈数据、比對结果
"""

import sqlite3
import json
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "app.db"


class DBService:
    """SQLite 数据库服务"""

    _conn: sqlite3.Connection = None

    def __init__(self):
        self._ensure_db()

    def _ensure_db(self):
        """确保数据库和表已创建"""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = self.get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scan_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT UNIQUE NOT NULL,
                file_id TEXT,
                mode TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                error TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME
            );

            CREATE TABLE IF NOT EXISTS scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                data JSON NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES scan_tasks(task_id)
            );

            CREATE TABLE IF NOT EXISTS feedback_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE NOT NULL,
                filename TEXT,
                sheet_count INTEGER DEFAULT 0,
                row_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS feedback_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                chapter TEXT,
                data JSON NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES feedback_files(file_id)
            );

            CREATE TABLE IF NOT EXISTS compare_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                compare_id TEXT UNIQUE NOT NULL,
                task_id TEXT,
                feedback_file_id TEXT,
                stats JSON,
                diff_items JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES scan_tasks(task_id),
                FOREIGN KEY (feedback_file_id) REFERENCES feedback_files(file_id)
            );

            CREATE INDEX IF NOT EXISTS idx_scan_tasks_status ON scan_tasks(status);
            CREATE INDEX IF NOT EXISTS idx_scan_results_task ON scan_results(task_id);
            CREATE INDEX IF NOT EXISTS idx_feedback_files_id ON feedback_files(file_id);
            CREATE INDEX IF NOT EXISTS idx_feedback_data_file ON feedback_data(file_id);
            CREATE INDEX IF NOT EXISTS idx_compare_results_id ON compare_results(compare_id);
        """)
        conn.commit()

    def get_conn(self) -> sqlite3.Connection:
        if DBService._conn is None:
            DBService._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            DBService._conn.row_factory = sqlite3.Row
        return DBService._conn

    def close(self):
        if DBService._conn:
            DBService._conn.close()
            DBService._conn = None

    # === Scan Tasks ===
    def create_scan_task(self, file_id: str, mode: str = "normal", task_id: str = None) -> str:
        if task_id is None:
            task_id = str(uuid.uuid4())
        conn = self.get_conn()
        conn.execute(
            "INSERT INTO scan_tasks (task_id, file_id, mode, status) VALUES (?, ?, ?, 'pending')",
            (task_id, file_id, mode)
        )
        conn.commit()
        return task_id

    def update_scan_task(self, task_id: str, status: str, progress: int = 0,
                          error: str = None, completed_at: str = None):
        conn = self.get_conn()
        if completed_at:
            conn.execute(
                "UPDATE scan_tasks SET status=?, progress=?, error=?, completed_at=? WHERE task_id=?",
                (status, progress, error, completed_at, task_id)
            )
        else:
            conn.execute(
                "UPDATE scan_tasks SET status=?, progress=?, error=? WHERE task_id=?",
                (status, progress, error, task_id)
            )
        conn.commit()

    def save_scan_result(self, task_id: str, data: Dict):
        conn = self.get_conn()
        conn.execute(
            "INSERT INTO scan_results (task_id, data) VALUES (?, ?)",
            (task_id, json.dumps(data, ensure_ascii=False))
        )
        conn.commit()

    def get_scan_result(self, task_id: str) -> Optional[Dict]:
        conn = self.get_conn()
        row = conn.execute(
            "SELECT data FROM scan_results WHERE task_id=? ORDER BY id DESC LIMIT 1",
            (task_id,)
        ).fetchone()
        return json.loads(row["data"]) if row else None

    def get_scan_task(self, task_id: str) -> Optional[Dict]:
        conn = self.get_conn()
        row = conn.execute(
            "SELECT * FROM scan_tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_scan_tasks(self, limit: int = 50) -> List[Dict]:
        conn = self.get_conn()
        rows = conn.execute(
            "SELECT task_id, file_id, mode, status, progress, created_at, completed_at "
            "FROM scan_tasks ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # === Feedback Files ===
    def save_feedback_file(self, file_id: str, filename: str, sheets: List[str], row_counts: Dict[str, int]):
        conn = self.get_conn()
        total_rows = sum(row_counts.values())
        conn.execute(
            "INSERT OR REPLACE INTO feedback_files (file_id, filename, sheet_count, row_count) "
            "VALUES (?, ?, ?, ?)",
            (file_id, filename, len(sheets), total_rows)
        )
        conn.commit()

    def save_feedback_chapter(self, file_id: str, chapter: str, data: List[Dict]):
        conn = self.get_conn()
        conn.execute(
            "INSERT INTO feedback_data (file_id, chapter, data) VALUES (?, ?, ?)",
            (file_id, chapter, json.dumps(data, ensure_ascii=False))
        )
        conn.commit()

    def get_feedback_file(self, file_id: str) -> Optional[Dict]:
        conn = self.get_conn()
        row = conn.execute(
            "SELECT * FROM feedback_files WHERE file_id=?", (file_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_feedback_chapters(self, file_id: str) -> Dict[str, List[Dict]]:
        conn = self.get_conn()
        rows = conn.execute(
            "SELECT chapter, data FROM feedback_data WHERE file_id=?", (file_id,)
        ).fetchall()
        result = {}
        for row in rows:
            result[row["chapter"]] = json.loads(row["data"])
        return result

    def list_feedback_files(self, limit: int = 50) -> List[Dict]:
        conn = self.get_conn()
        rows = conn.execute(
            "SELECT file_id, filename, sheet_count, row_count, created_at "
            "FROM feedback_files ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # === Compare Results ===
    def save_compare_result(self, compare_id: str, task_id: str, feedback_file_id: str,
                            stats: Dict, diff_items: List[Dict]) -> str:
        conn = self.get_conn()
        conn.execute(
            "INSERT INTO compare_results (compare_id, task_id, feedback_file_id, stats, diff_items) "
            "VALUES (?, ?, ?, ?, ?)",
            (compare_id, task_id, feedback_file_id,
             json.dumps(stats, ensure_ascii=False),
             json.dumps(diff_items, ensure_ascii=False))
        )
        conn.commit()
        return compare_id

    def get_compare_result(self, compare_id: str) -> Optional[Dict]:
        conn = self.get_conn()
        row = conn.execute(
            "SELECT * FROM compare_results WHERE compare_id=?", (compare_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["stats"] = json.loads(d["stats"])
        d["diff_items"] = json.loads(d["diff_items"])
        return d

    def list_compare_results(self, limit: int = 50) -> List[Dict]:
        conn = self.get_conn()
        rows = conn.execute(
            "SELECT compare_id, task_id, feedback_file_id, stats, created_at "
            "FROM compare_results ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["stats"] = json.loads(d["stats"])
            result.append(d)
        return result

    def get_summary(self) -> Dict:
        """获取系统摘要统计"""
        conn = self.get_conn()
        scan_count = conn.execute("SELECT COUNT(*) FROM scan_tasks").fetchone()[0]
        scan_completed = conn.execute(
            "SELECT COUNT(*) FROM scan_tasks WHERE status='completed'").fetchone()[0]
        feedback_count = conn.execute("SELECT COUNT(*) FROM feedback_files").fetchone()[0]
        compare_count = conn.execute("SELECT COUNT(*) FROM compare_results").fetchone()[0]

        return {
            "scan_tasks": scan_count,
            "scan_completed": scan_completed,
            "feedback_files": feedback_count,
            "compare_results": compare_count,
            "db_path": str(DB_PATH)
        }
