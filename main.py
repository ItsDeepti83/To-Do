from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3
import httpx
import os
from datetime import datetime

app = FastAPI(title="TaskFlow API", version="1.0.0")

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # In production, set to your frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DATABASE ──────────────────────────────────────────────────────────────────
DB_PATH = "taskflow.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            text        TEXT    NOT NULL,
            priority    TEXT    NOT NULL DEFAULT 'low',
            done        INTEGER NOT NULL DEFAULT 0,
            ai_tip      TEXT,
            created_at  TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ── SCHEMAS ───────────────────────────────────────────────────────────────────
class TaskCreate(BaseModel):
    text: str
    priority: str = "low"   # low | mid | high

class TaskUpdate(BaseModel):
    done: Optional[bool] = None
    text: Optional[str] = None
    priority: Optional[str] = None

# ── HELPERS ───────────────────────────────────────────────────────────────────
def row_to_dict(row):
    return {
        "id":         row["id"],
        "text":       row["text"],
        "priority":   row["priority"],
        "done":       bool(row["done"]),
        "ai_tip":     row["ai_tip"],
        "created_at": row["created_at"],
    }

async def fetch_ai_tip(task_id: int, text: str, priority: str):
    """Call Claude API and update the task with an AI tip."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 80,
                    "system": (
                        "You are a productivity assistant. For a given task, give ONE "
                        "ultra-short tip (max 12 words, no punctuation at end). "
                        "Be practical and specific. Reply with just the tip."
                    ),
                    "messages": [
                        {"role": "user", "content": f'Task: "{text}" Priority: {priority}'}
                    ],
                },
            )
        tip = resp.json()["content"][0]["text"].strip()
        conn = get_db()
        conn.execute("UPDATE tasks SET ai_tip = ? WHERE id = ?", (tip, task_id))
        conn.commit()
        conn.close()
    except Exception:
        pass   # AI tip is optional — never crash the app

# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "app": "TaskFlow API"}

@app.get("/tasks")
def get_tasks(filter: str = "all"):
    conn = get_db()
    if filter == "active":
        rows = conn.execute("SELECT * FROM tasks WHERE done=0 ORDER BY id DESC").fetchall()
    elif filter == "done":
        rows = conn.execute("SELECT * FROM tasks WHERE done=1 ORDER BY id DESC").fetchall()
    elif filter == "high":
        rows = conn.execute("SELECT * FROM tasks WHERE priority='high' ORDER BY id DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

@app.post("/tasks", status_code=201)
async def create_task(body: TaskCreate):
    if not body.text.strip():
        raise HTTPException(400, "Task text cannot be empty")
    if body.priority not in ("low", "mid", "high"):
        raise HTTPException(400, "Priority must be low, mid, or high")

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO tasks (text, priority, done, created_at) VALUES (?, ?, 0, ?)",
        (body.text.strip(), body.priority, datetime.utcnow().isoformat()),
    )
    task_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()

    task = row_to_dict(row)

    # Fire AI tip in background (non-blocking)
    import asyncio
    asyncio.create_task(fetch_ai_tip(task_id, body.text, body.priority))

    return task

@app.patch("/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate):
    conn = get_db()
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Task not found")

    updates, params = [], []
    if body.done is not None:
        updates.append("done=?");     params.append(int(body.done))
    if body.text is not None:
        updates.append("text=?");     params.append(body.text.strip())
    if body.priority is not None:
        updates.append("priority=?"); params.append(body.priority)

    if updates:
        params.append(task_id)
        conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id=?", params)
        conn.commit()

    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return row_to_dict(row)

@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    conn = get_db()
    row = conn.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Task not found")
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()

@app.get("/stats")
def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    done  = conn.execute("SELECT COUNT(*) FROM tasks WHERE done=1").fetchone()[0]
    conn.close()
    return {
        "total":     total,
        "done":      done,
        "remaining": total - done,
        "pct":       round(done / total * 100) if total else 0,
    }
