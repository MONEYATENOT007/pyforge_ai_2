"""Versioned SQLite storage for local chat and feedback."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

SCHEMA_VERSION = 4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(f"Chat database version {version} is newer than this app supports")
            if version == 0:
                db.executescript("""
                    CREATE TABLE sessions (
                        id INTEGER PRIMARY KEY, public_id TEXT NOT NULL UNIQUE,
                        title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                    );
                    CREATE TABLE messages (
                        id INTEGER PRIMARY KEY, public_id TEXT NOT NULL UNIQUE,
                        session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                        role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                        content TEXT NOT NULL, model TEXT, profile TEXT,
                        metrics_json TEXT, run_json TEXT, created_at TEXT NOT NULL
                    );
                    CREATE TABLE feedback (
                        message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
                        rating INTEGER NOT NULL CHECK (rating IN (-1, 1)),
                        comment TEXT NOT NULL DEFAULT '',
                        candidate INTEGER NOT NULL DEFAULT 0 CHECK (candidate IN (0, 1)),
                        failure_category TEXT NOT NULL DEFAULT '',
                        updated_at TEXT NOT NULL
                    );
                    PRAGMA user_version = 2;
                """)
            elif version == 1:
                db.execute("ALTER TABLE sessions ADD COLUMN public_id TEXT")
                db.execute("ALTER TABLE messages ADD COLUMN public_id TEXT")
                db.execute("ALTER TABLE messages ADD COLUMN run_json TEXT")
                db.execute("ALTER TABLE feedback ADD COLUMN failure_category TEXT NOT NULL DEFAULT ''")
                for row in db.execute("SELECT id FROM sessions").fetchall():
                    db.execute("UPDATE sessions SET public_id=? WHERE id=?", (str(uuid4()), row[0]))
                for row in db.execute("SELECT id FROM messages").fetchall():
                    db.execute("UPDATE messages SET public_id=? WHERE id=?", (str(uuid4()), row[0]))
                db.execute("CREATE UNIQUE INDEX sessions_public_id ON sessions(public_id)")
                db.execute("CREATE UNIQUE INDEX messages_public_id ON messages(public_id)")
                db.execute("PRAGMA user_version = 2")
            if version < 3:
                db.execute("""CREATE TABLE evaluation_cases (
                    id INTEGER PRIMARY KEY,
                    public_id TEXT NOT NULL UNIQUE,
                    message_id INTEGER NOT NULL UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
                    prompt TEXT NOT NULL,
                    response TEXT NOT NULL,
                    review_json TEXT NOT NULL,
                    suite_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )""")
                db.execute("PRAGMA user_version = 3")
            if version < 4:
                db.execute("ALTER TABLE evaluation_cases ADD COLUMN context_json TEXT NOT NULL DEFAULT '[]'")
                db.execute("""CREATE TABLE problem_reports (
                    message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
                    expected TEXT NOT NULL DEFAULT '',
                    actual TEXT NOT NULL DEFAULT '',
                    traceback TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )""")
                db.execute("PRAGMA user_version = 4")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_session(self, title: str = "New chat") -> int:
        title = title.strip() or "New chat"
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO sessions(public_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (str(uuid4()), title, _now(), _now()),
            )
            return int(cursor.lastrowid)

    def list_sessions(self) -> list[dict]:
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM sessions ORDER BY updated_at DESC, id DESC")]

    def rename_session(self, session_id: int, title: str) -> None:
        title = title.strip()
        if not title:
            raise ValueError("title cannot be empty")
        with self._connect() as db:
            if db.execute("UPDATE sessions SET title=?, updated_at=? WHERE id=?", (title, _now(), session_id)).rowcount != 1:
                raise KeyError(session_id)

    def delete_session(self, session_id: int) -> None:
        with self._connect() as db:
            if db.execute("DELETE FROM sessions WHERE id=?", (session_id,)).rowcount != 1:
                raise KeyError(session_id)

    def add_message(self, session_id: int, role: str, content: str, *, model: str | None = None,
                    profile: str | None = None, metrics: dict | None = None, run: dict | None = None) -> int:
        if role not in {"user", "assistant"} or not content.strip():
            raise ValueError("message needs a valid role and nonempty content")
        with self._connect() as db:
            if db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone() is None:
                raise KeyError(session_id)
            cursor = db.execute(
                """INSERT INTO messages(public_id, session_id, role, content, model, profile, metrics_json, run_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid4()), session_id, role, content, model, profile,
                 json.dumps(metrics) if metrics is not None else None,
                 json.dumps(run) if run is not None else None, _now()),
            )
            db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (_now(), session_id))
            return int(cursor.lastrowid)

    def messages(self, session_id: int) -> list[dict]:
        with self._connect() as db:
            if db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone() is None:
                raise KeyError(session_id)
            rows = db.execute(
                """SELECT m.*, f.rating, f.comment, f.candidate, f.failure_category,
                          f.updated_at AS feedback_updated_at,
                          p.expected AS problem_expected, p.actual AS problem_actual,
                          p.traceback AS problem_traceback,
                          p.created_at AS problem_created_at, p.updated_at AS problem_updated_at
                   FROM messages m LEFT JOIN feedback f ON f.message_id=m.id
                   LEFT JOIN problem_reports p ON p.message_id=m.id
                   WHERE m.session_id=? ORDER BY m.id""", (session_id,)
            ).fetchall()
            return [{**dict(row),
                     "metrics": json.loads(row["metrics_json"]) if row["metrics_json"] else None,
                     "run": json.loads(row["run_json"]) if row["run_json"] else None} for row in rows]

    def save_feedback(self, message_id: int, rating: int, comment: str = "",
                      candidate: bool = False, failure_category: str = "") -> None:
        if rating not in {-1, 1}:
            raise ValueError("rating must be thumbs up or thumbs down")
        with self._connect() as db:
            row = db.execute("SELECT role FROM messages WHERE id=?", (message_id,)).fetchone()
            if row is None or row["role"] != "assistant":
                raise ValueError("feedback requires an assistant message")
            db.execute(
                """INSERT INTO feedback(message_id, rating, comment, candidate, failure_category, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(message_id) DO UPDATE SET rating=excluded.rating,
                   comment=excluded.comment, candidate=excluded.candidate,
                   failure_category=excluded.failure_category, updated_at=excluded.updated_at""",
                (message_id, rating, comment, int(candidate), failure_category.strip(), _now()),
            )

    def save_problem_report(self, message_id: int, expected: str = "",
                            actual: str = "", traceback: str = "") -> None:
        if not any(value.strip() for value in (expected, actual, traceback)):
            raise ValueError("describe expected behavior, actual behavior, or a traceback")
        with self._connect() as db:
            row = db.execute("SELECT role FROM messages WHERE id=?", (message_id,)).fetchone()
            if row is None or row["role"] != "assistant":
                raise ValueError("problem report requires an assistant message")
            now = _now()
            db.execute(
                """INSERT INTO problem_reports(message_id,expected,actual,traceback,created_at,updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(message_id) DO UPDATE SET expected=excluded.expected,
                   actual=excluded.actual, traceback=excluded.traceback, updated_at=excluded.updated_at""",
                (message_id, expected, actual, traceback, now, now),
            )

    def export_json(self, session_id: int, *, redact: bool = True, include_details: bool = True) -> str:
        from .export import build_export
        with self._connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row is None:
                raise KeyError(session_id)
            payload = build_export(dict(row), self.messages(session_id), redact=redact, include_details=include_details)
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def export_markdown(self, session_id: int, *, redact: bool = True, include_details: bool = True) -> str:
        from .export import to_markdown
        return to_markdown(json.loads(self.export_json(session_id, redact=redact, include_details=include_details)))

    def import_json(self, source: str) -> int:
        from .export import parse_export
        payload = parse_export(source)
        with self._connect() as db:
            session = payload["session"]
            if db.execute("SELECT 1 FROM sessions WHERE public_id=?", (session["id"],)).fetchone():
                raise ValueError("session UUID already exists")
            cursor = db.execute(
                "INSERT INTO sessions(public_id,title,created_at,updated_at) VALUES (?,?,?,?)",
                (session["id"], session["title"], session["created_at"], session["updated_at"]),
            )
            session_id = int(cursor.lastrowid)
            for message in payload["messages"]:
                details = message.get("metadata") or {}
                cursor = db.execute(
                    """INSERT INTO messages(public_id,session_id,role,content,model,profile,metrics_json,run_json,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (message["id"], session_id, message["role"], message["content"],
                     details.get("model"), details.get("profile"),
                     json.dumps(details.get("metrics")) if details.get("metrics") is not None else None,
                     json.dumps(details.get("run")) if details.get("run") is not None else None,
                     message["timestamp"]),
                )
                feedback = message.get("feedback")
                if feedback:
                    db.execute(
                        """INSERT INTO feedback(message_id,rating,comment,candidate,failure_category,updated_at)
                           VALUES (?,?,?,?,?,?)""",
                        (cursor.lastrowid, 1 if feedback["rating"] == "up" else -1,
                         feedback.get("comment", ""), int(feedback.get("candidate", False)),
                         feedback.get("failure_category", ""), feedback["timestamp"]),
                    )
                problem = message.get("problem_report")
                if problem:
                    db.execute(
                        """INSERT INTO problem_reports(message_id,expected,actual,traceback,created_at,updated_at)
                           VALUES(?,?,?,?,?,?)""",
                        (cursor.lastrowid, problem.get("expected", ""), problem.get("actual", ""),
                         problem.get("traceback", ""), problem["created_at"], problem["updated_at"]),
                    )
            return session_id

    def queue_evaluation_case(self, message_id: int) -> str:
        """Snapshot a response and its user prompt for later isolated evaluation."""
        from pyforge.evaluation.requirements import review_requirements
        with self._connect() as db:
            message = db.execute(
                "SELECT id,session_id,role,content FROM messages WHERE id=?", (message_id,)
            ).fetchone()
            if message is None or message["role"] != "assistant":
                raise ValueError("evaluation case requires an assistant message")
            prompts = db.execute(
                """SELECT content FROM messages WHERE session_id=? AND id<? AND role='user'
                   ORDER BY id""", (message["session_id"], message_id)
            ).fetchall()
            if not prompts:
                raise ValueError("assistant message has no preceding user prompt")
            prompt = prompts[-1]["content"]
            context = [row["content"] for row in prompts[:-1]]
            existing = db.execute(
                "SELECT public_id FROM evaluation_cases WHERE message_id=?", (message_id,)
            ).fetchone()
            if existing:
                return existing["public_id"]
            public_id = str(uuid4())
            db.execute(
                """INSERT INTO evaluation_cases(public_id,message_id,prompt,response,review_json,
                   suite_version,status,created_at,context_json) VALUES(?,?,?,?,?,?,?,?,?)""",
                (public_id, message_id, prompt, message["content"],
                 json.dumps(review_requirements(prompt, message["content"], context=context)),
                 "session02-static-v1", "static_reviewed", _now(), json.dumps(context)),
            )
            return public_id

    def evaluation_cases(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM evaluation_cases ORDER BY id DESC"
            ).fetchall()
            return [{**dict(row), "review": json.loads(row["review_json"]),
                     "context": json.loads(row["context_json"])} for row in rows]
