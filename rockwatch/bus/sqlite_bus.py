"""SQLite bus (demo default): WAL, append-only `events`, per-consumer offsets, agent registry. Zero install,
multi-process, replayable."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from rockwatch.bus.base import Bus
from rockwatch.schemas import Envelope

COLS = ["msg_id", "topic", "agent_id", "zone_id", "sim_date", "wall_ts", "kind", "payload", "confidence", "quality", "evidence_ids"]
SCHEMA = """
CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, msg_id TEXT UNIQUE, topic TEXT, agent_id TEXT,
  zone_id TEXT, sim_date TEXT, wall_ts REAL, kind TEXT, payload TEXT, confidence REAL, quality TEXT, evidence_ids TEXT);
CREATE INDEX IF NOT EXISTS ix_topic_seq ON events(topic, seq);
CREATE INDEX IF NOT EXISTS ix_topic_date ON events(topic, sim_date, zone_id);
CREATE TABLE IF NOT EXISTS offsets(consumer TEXT PRIMARY KEY, seq INTEGER);
CREATE TABLE IF NOT EXISTS registry(agent_id TEXT PRIMARY KEY, cmd TEXT, pid INTEGER, started REAL, auto_restart INTEGER, restarts INTEGER DEFAULT 0);
"""


class SqliteBus(Bus):
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA synchronous=NORMAL")
        self.con.executescript(SCHEMA)

    def _retry(self, fn, *a):
        for i in range(50):
            try:
                return fn(*a)
            except sqlite3.OperationalError as e:
                if "locked" not in str(e) and "busy" not in str(e):
                    raise
                time.sleep(0.05 * (i + 1))
        raise RuntimeError("sqlite bus busy")

    def publish(self, envs):
        envs = envs if isinstance(envs, list) else [envs]
        if not envs:
            return
        rows = [(e.msg_id, e.topic, e.agent_id, e.zone_id, e.sim_date, e.wall_ts, e.kind, json.dumps(e.payload, default=float),
                 e.confidence, e.quality, json.dumps(e.evidence_ids)) for e in envs]

        def go():
            self.con.execute("BEGIN IMMEDIATE")
            try:
                self.con.executemany(f"INSERT OR IGNORE INTO events({','.join(COLS)}) VALUES ({','.join('?' * len(COLS))})", rows)
                self.con.execute("COMMIT")
            except Exception:
                self.con.execute("ROLLBACK")
                raise
        self._retry(go)

    @staticmethod
    def _env(r) -> Envelope:
        seq, *vals = r
        d = dict(zip(COLS, vals))
        d["payload"] = json.loads(d["payload"])
        d["evidence_ids"] = json.loads(d["evidence_ids"])
        e = Envelope(**d)
        e.seq = seq
        return e

    def _poll(self, consumer, topics, max_n):
        def go():
            row = self.con.execute("SELECT seq FROM offsets WHERE consumer=?", (consumer,)).fetchone()
            off = row[0] if row else 0
            q = f"SELECT seq,{','.join(COLS)} FROM events WHERE seq>? AND topic IN ({','.join('?' * len(topics))}) ORDER BY seq LIMIT ?"
            rows = self.con.execute(q, (off, *topics, max_n)).fetchall()
            if rows:
                new = rows[-1][0]
                self.con.execute("INSERT INTO offsets(consumer,seq) VALUES(?,?) ON CONFLICT(consumer) DO UPDATE SET seq=excluded.seq", (consumer, new))
            return rows
        return [self._env(r) for r in self._retry(go)]

    def _read(self, topics, since_seq, kind, limit, latest, sim_date=None, zone_id=None, date_from=None):
        q = f"SELECT seq,{','.join(COLS)} FROM events WHERE seq>? AND topic IN ({','.join('?' * len(topics))})"
        args: list = [since_seq, *topics]
        for col, val, op in (("kind", kind, "="), ("sim_date", sim_date, "="), ("zone_id", zone_id, "="), ("sim_date", date_from, ">=")):
            if val is not None:
                q += f" AND {col}{op}?"
                args.append(val)
        q += " ORDER BY seq DESC" if latest else " ORDER BY seq"
        if limit or latest:
            q += " LIMIT ?"
            args.append(limit or 1)
        rows = self._retry(lambda: self.con.execute(q, args).fetchall())
        out = [self._env(r) for r in rows]
        return out[::-1] if latest else out

    # ---- registry (launcher / supervisor)
    def register(self, agent_id: str, cmd: list[str], pid: int, auto_restart: bool) -> None:
        self._retry(lambda: self.con.execute(
            "INSERT INTO registry(agent_id,cmd,pid,started,auto_restart) VALUES(?,?,?,?,?) ON CONFLICT(agent_id) DO UPDATE SET "
            "cmd=excluded.cmd,pid=excluded.pid,started=excluded.started,auto_restart=excluded.auto_restart",
            (agent_id, json.dumps(cmd), pid, time.time(), int(auto_restart))))

    def registry(self) -> list[dict]:
        rows = self._retry(lambda: self.con.execute("SELECT agent_id,cmd,pid,started,auto_restart,restarts FROM registry").fetchall())
        return [dict(agent_id=a, cmd=json.loads(c), pid=p, started=s, auto_restart=bool(ar), restarts=r) for a, c, p, s, ar, r in rows]

    def bump_restart(self, agent_id: str, pid: int) -> None:
        self._retry(lambda: self.con.execute("UPDATE registry SET pid=?, started=?, restarts=restarts+1 WHERE agent_id=?", (pid, time.time(), agent_id)))

    def close(self):
        self.con.close()
