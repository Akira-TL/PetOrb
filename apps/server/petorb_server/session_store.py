from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from .session_models import EvidenceFrame, SamplingSessionResponse, SessionFinding

ACTIVE_STATUSES = ("READY", "RECEIVING", "ANALYZING")


class ActiveSessionExistsError(RuntimeError):
    pass


class SessionNotFoundError(RuntimeError):
    pass


class NoActiveSessionError(RuntimeError):
    pass


class SessionBusyError(RuntimeError):
    pass


class SessionStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.sessions_dir = data_dir / "sessions"
        self.database_path = data_dir / "petorb.sqlite3"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    animal_id TEXT,
                    status TEXT NOT NULL,
                    sample_quality TEXT,
                    risk_level TEXT,
                    overall_judgment TEXT,
                    recommendation TEXT,
                    findings_json TEXT NOT NULL DEFAULT '[]',
                    error TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS frames (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    detections_json TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );
                """
            )

    def create_session(self, animal_id: str | None) -> SamplingSessionResponse:
        session_id = str(uuid4())
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
            existing = connection.execute(
                f"SELECT id FROM sessions WHERE status IN ({placeholders}) LIMIT 1",
                ACTIVE_STATUSES,
            ).fetchone()
            if existing is not None:
                raise ActiveSessionExistsError(existing["id"])
            connection.execute(
                "INSERT INTO sessions(id, animal_id, status) VALUES (?, ?, 'READY')",
                (session_id, animal_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return self.get_session(session_id)

    def claim_ready_session(self) -> str:
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"SELECT id, status FROM sessions WHERE status IN ({placeholders}) ORDER BY created_at DESC LIMIT 1",
                ACTIVE_STATUSES,
            ).fetchone()
            if row is None:
                raise NoActiveSessionError("no active sampling session")
            if row["status"] != "READY":
                raise SessionBusyError(f"sampling session {row['id']} is already {row['status']}")
            updated = connection.execute(
                "UPDATE sessions SET status = 'RECEIVING', error = NULL WHERE id = ? AND status = 'READY'",
                (row["id"],),
            ).rowcount
            if updated != 1:
                raise SessionBusyError(f"sampling session {row['id']} could not be claimed")
            connection.commit()
            return str(row["id"])
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def set_status(self, session_id: str, status: str, error: str | None = None) -> None:
        with self._connect() as connection:
            updated = connection.execute(
                "UPDATE sessions SET status = ?, error = ? WHERE id = ?",
                (status, error, session_id),
            ).rowcount
        if updated != 1:
            raise SessionNotFoundError(session_id)

    def complete_session(
        self,
        session_id: str,
        *,
        sample_quality: str,
        risk_level: str,
        overall_judgment: str,
        recommendation: str,
        findings: list[SessionFinding],
        evidence_frames: list[EvidenceFrame],
    ) -> SamplingSessionResponse:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM frames WHERE session_id = ?", (session_id,))
            for frame in evidence_frames:
                relative_path = str(Path(session_id) / f"{frame.id}.jpg")
                connection.execute(
                    """
                    INSERT INTO frames(id, session_id, relative_path, width, height, detections_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        frame.id,
                        session_id,
                        relative_path,
                        frame.image.width,
                        frame.image.height,
                        json.dumps([item.model_dump() for item in frame.detections], ensure_ascii=False),
                    ),
                )
            connection.execute(
                """
                UPDATE sessions
                SET status = 'COMPLETED', sample_quality = ?, risk_level = ?, overall_judgment = ?,
                    recommendation = ?, findings_json = ?, error = NULL
                WHERE id = ?
                """,
                (
                    sample_quality,
                    risk_level,
                    overall_judgment,
                    recommendation,
                    json.dumps([item.model_dump() for item in findings], ensure_ascii=False),
                    session_id,
                ),
            )
            connection.commit()
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> SamplingSessionResponse:
        with self._connect() as connection:
            session = connection.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if session is None:
                raise SessionNotFoundError(session_id)
            frames = connection.execute(
                "SELECT * FROM frames WHERE session_id = ? ORDER BY rowid",
                (session_id,),
            ).fetchall()

        evidence = [
            EvidenceFrame(
                id=str(frame["id"]),
                url=f"/api/sessions/{session_id}/evidence/{frame['id']}",
                image={"width": frame["width"], "height": frame["height"]},
                detections=json.loads(frame["detections_json"]),
            )
            for frame in frames
        ]
        return SamplingSessionResponse(
            id=str(session["id"]),
            animal_id=session["animal_id"],
            status=str(session["status"]),
            sample_quality=session["sample_quality"],
            risk_level=session["risk_level"],
            overall_judgment=session["overall_judgment"],
            recommendation=session["recommendation"],
            findings=json.loads(session["findings_json"]),
            evidence_frames=evidence,
            error=session["error"],
            created_at=str(session["created_at"]),
        )

    def evidence_path(self, session_id: str, frame_id: str) -> Path:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT relative_path FROM frames WHERE session_id = ? AND id = ?",
                (session_id, frame_id),
            ).fetchone()
        if row is None:
            raise SessionNotFoundError(frame_id)
        return self.sessions_dir / str(row["relative_path"])
