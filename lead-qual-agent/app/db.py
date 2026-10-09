"""SQLite persistence (stdlib only, JSON-document storage).

MVP uses SQLite; swap DB_PATH / this module for Postgres in production.
Each entity is stored as a JSON blob plus a few indexed columns.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from app import config
from app.models import (
    AuditEntry,
    BANTConfig,
    Client,
    ConversationMessage,
    ICPConfig,
    Lead,
    Meeting,
    QualificationResult,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients      (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS icp_configs  (id TEXT PRIMARY KEY, client_id TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bant_configs (id TEXT PRIMARY KEY, client_id TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS leads        (id TEXT PRIMARY KEY, client_id TEXT, email TEXT, status TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages     (id TEXT PRIMARY KEY, lead_id TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS qualifications (id TEXT PRIMARY KEY, lead_id TEXT, client_id TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meetings     (id TEXT PRIMARY KEY, lead_id TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit        (id TEXT PRIMARY KEY, lead_id TEXT, client_id TEXT, ts TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS routing_state (client_id TEXT PRIMARY KEY, last_index INTEGER NOT NULL DEFAULT -1);
CREATE INDEX IF NOT EXISTS idx_leads_client ON leads(client_id);
CREATE INDEX IF NOT EXISTS idx_leads_email  ON leads(email);
CREATE INDEX IF NOT EXISTS idx_msgs_lead    ON messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_quals_lead   ON qualifications(lead_id);
CREATE INDEX IF NOT EXISTS idx_audit_lead   ON audit(lead_id);
"""


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(config.DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Clients / configs
# --------------------------------------------------------------------------- #
def save_client(client: Client) -> Client:
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO clients (id, data) VALUES (?, ?)",
            (client.id, client.model_dump_json()),
        )
        conn.commit()
        return client
    finally:
        conn.close()


def list_clients() -> List[Client]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT data FROM clients ORDER BY id").fetchall()
        return [Client.model_validate_json(r["data"]) for r in rows]
    finally:
        conn.close()


def get_client(client_id: str) -> Optional[Client]:
    conn = _connect()
    try:
        row = conn.execute("SELECT data FROM clients WHERE id = ?", (client_id,)).fetchone()
        return Client.model_validate_json(row["data"]) if row else None
    finally:
        conn.close()


def save_icp(icp: ICPConfig) -> ICPConfig:
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO icp_configs (id, client_id, data) VALUES (?, ?, ?)",
            (icp.id, icp.client_id, icp.model_dump_json()),
        )
        conn.commit()
        return icp
    finally:
        conn.close()


def get_icp_for_client(client_id: str) -> Optional[ICPConfig]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT data FROM icp_configs WHERE client_id = ? LIMIT 1", (client_id,)
        ).fetchone()
        return ICPConfig.model_validate_json(row["data"]) if row else None
    finally:
        conn.close()


def save_bant(cfg: BANTConfig) -> BANTConfig:
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO bant_configs (id, client_id, data) VALUES (?, ?, ?)",
            (cfg.id, cfg.client_id, cfg.model_dump_json()),
        )
        conn.commit()
        return cfg
    finally:
        conn.close()


def get_bant_for_client(client_id: str) -> Optional[BANTConfig]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT data FROM bant_configs WHERE client_id = ? LIMIT 1", (client_id,)
        ).fetchone()
        return BANTConfig.model_validate_json(row["data"]) if row else None
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Leads
# --------------------------------------------------------------------------- #
def save_lead(lead: Lead) -> Lead:
    lead.updated_at = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO leads (id, client_id, email, status, data) VALUES (?, ?, ?, ?, ?)",
            (lead.id, lead.client_id, (lead.email or "").lower(), lead.status.value, lead.model_dump_json()),
        )
        conn.commit()
        return lead
    finally:
        conn.close()


def get_lead(lead_id: str) -> Optional[Lead]:
    conn = _connect()
    try:
        row = conn.execute("SELECT data FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return Lead.model_validate_json(row["data"]) if row else None
    finally:
        conn.close()


def find_leads_by_email(client_id: str, email: str) -> List[Lead]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT data FROM leads WHERE client_id = ? AND email = ?",
            (client_id, (email or "").lower()),
        ).fetchall()
        return [Lead.model_validate_json(r["data"]) for r in rows]
    finally:
        conn.close()


def list_leads(client_id: str) -> List[Lead]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT data FROM leads WHERE client_id = ? ORDER BY json_extract(data,'$.created_at') DESC",
            (client_id,),
        ).fetchall()
        return [Lead.model_validate_json(r["data"]) for r in rows]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Messages / qualifications / meetings / audit
# --------------------------------------------------------------------------- #
def save_message(msg: ConversationMessage) -> ConversationMessage:
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO messages (id, lead_id, data) VALUES (?, ?, ?)",
            (msg.id, msg.lead_id, msg.model_dump_json()),
        )
        conn.commit()
        return msg
    finally:
        conn.close()


def list_messages(lead_id: str) -> List[ConversationMessage]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT data FROM messages WHERE lead_id = ? ORDER BY json_extract(data,'$.timestamp')",
            (lead_id,),
        ).fetchall()
        return [ConversationMessage.model_validate_json(r["data"]) for r in rows]
    finally:
        conn.close()


def save_qualification(q: QualificationResult) -> QualificationResult:
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO qualifications (id, lead_id, client_id, data) VALUES (?, ?, ?, ?)",
            (q.id, q.lead_id, q.client_id, q.model_dump_json()),
        )
        conn.commit()
        return q
    finally:
        conn.close()


def latest_qualification(lead_id: str) -> Optional[QualificationResult]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT data FROM qualifications WHERE lead_id = ? "
            "ORDER BY json_extract(data,'$.created_at') DESC LIMIT 1",
            (lead_id,),
        ).fetchone()
        return QualificationResult.model_validate_json(row["data"]) if row else None
    finally:
        conn.close()


def save_meeting(m: Meeting) -> Meeting:
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO meetings (id, lead_id, data) VALUES (?, ?, ?)",
            (m.id, m.lead_id, m.model_dump_json()),
        )
        conn.commit()
        return m
    finally:
        conn.close()


def get_meeting_for_lead(lead_id: str) -> Optional[Meeting]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT data FROM meetings WHERE lead_id = ? "
            "ORDER BY json_extract(data,'$.created_at') DESC LIMIT 1",
            (lead_id,),
        ).fetchone()
        return Meeting.model_validate_json(row["data"]) if row else None
    finally:
        conn.close()


def add_audit(entry: AuditEntry) -> AuditEntry:
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO audit (id, lead_id, client_id, ts, data) VALUES (?, ?, ?, ?, ?)",
            (entry.id, entry.lead_id, entry.client_id, entry.timestamp, entry.model_dump_json()),
        )
        conn.commit()
        return entry
    finally:
        conn.close()


def list_audit(lead_id: str) -> List[AuditEntry]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT data FROM audit WHERE lead_id = ? ORDER BY ts", (lead_id,)
        ).fetchall()
        return [AuditEntry.model_validate_json(r["data"]) for r in rows]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Routing state (round-robin counter)
# --------------------------------------------------------------------------- #
def next_round_robin_index(client_id: str, modulo: int) -> int:
    if modulo <= 0:
        return 0
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT last_index FROM routing_state WHERE client_id = ?", (client_id,)
        ).fetchone()
        last = row["last_index"] if row else -1
        nxt = (last + 1) % modulo
        conn.execute(
            "INSERT OR REPLACE INTO routing_state (client_id, last_index) VALUES (?, ?)",
            (client_id, nxt),
        )
        conn.commit()
        return nxt
    finally:
        conn.close()
