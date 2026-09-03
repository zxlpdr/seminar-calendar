from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator

from models import Resource, Seminar


def default_database_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        data_dir = Path(base) / "SeminarCalendar"
    else:
        data_dir = Path.home() / ".seminar_calendar"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "seminars.db"


class SeminarDatabase:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else default_database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialise(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS seminars (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL,
                    meetings_json TEXT NOT NULL DEFAULT '[]',
                    applications_json TEXT NOT NULL DEFAULT '[]',
                    source_text TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_seminars_date ON seminars(event_date)"
            )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Seminar:
        application_data = json.loads(row["applications_json"] or "[]")
        return Seminar(
            id=row["id"],
            company=row["company"],
            event_date=date.fromisoformat(row["event_date"]),
            start_time=row["start_time"],
            end_time=row["end_time"],
            location=row["location"],
            meetings=json.loads(row["meetings_json"] or "[]"),
            applications=[Resource(item["label"], item["value"]) for item in application_data],
            source_text=row["source_text"],
        )

    @staticmethod
    def _parameters(seminar: Seminar) -> tuple[str, ...]:
        if seminar.event_date is None:
            raise ValueError("event_date is required")
        applications = [
            {"label": item.label, "value": item.value} for item in seminar.applications
        ]
        return (
            seminar.company,
            seminar.event_date.isoformat(),
            seminar.start_time,
            seminar.end_time,
            seminar.location,
            json.dumps(seminar.meetings, ensure_ascii=False),
            json.dumps(applications, ensure_ascii=False),
            seminar.source_text,
        )

    def add(self, seminar: Seminar) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO seminars (
                    company, event_date, start_time, end_time, location,
                    meetings_json, applications_json, source_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._parameters(seminar),
            )
            seminar.id = int(cursor.lastrowid)
            return seminar.id

    def update(self, seminar: Seminar) -> None:
        if seminar.id is None:
            raise ValueError("Cannot update a seminar without an id")
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE seminars SET
                    company = ?, event_date = ?, start_time = ?, end_time = ?,
                    location = ?, meetings_json = ?, applications_json = ?,
                    source_text = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                self._parameters(seminar) + (seminar.id,),
            )

    def delete(self, seminar_id: int) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM seminars WHERE id = ?", (seminar_id,))

    def get(self, seminar_id: int) -> Seminar | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM seminars WHERE id = ?", (seminar_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def between(self, start: date, end: date) -> list[Seminar]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM seminars
                WHERE event_date BETWEEN ? AND ?
                ORDER BY event_date, start_time, company, id
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def all(self) -> list[Seminar]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM seminars ORDER BY event_date DESC, start_time, company, id"
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def history(self, before: date) -> list[Seminar]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM seminars WHERE event_date < ?
                ORDER BY event_date DESC, start_time, company, id
                """,
                (before.isoformat(),),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def duplicates(self, seminar: Seminar) -> list[Seminar]:
        if seminar.event_date is None:
            return []
        query = """
            SELECT * FROM seminars
            WHERE company = ? AND event_date = ? AND start_time = ?
        """
        parameters: list[object] = [
            seminar.company,
            seminar.event_date.isoformat(),
            seminar.start_time,
        ]
        if seminar.id is not None:
            query += " AND id != ?"
            parameters.append(seminar.id)
        with self._connection() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()
        return [self._from_row(row) for row in rows]
