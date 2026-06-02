"""
Filename: campus_navigation.py
AI-Driven Intelligent Campus Navigation & Crowd-Sourced Space Optimization System

Minimal single-file FastAPI prototype implementing:
- SQLite storage for nodes, edges, rooms, and occupancy reports
- Dijkstra shortest-path endpoint
- Conflict override endpoint to mark rooms available
- Simple in-memory map seed and DB initialization

Run: uvicorn this_file:app --reload
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import heapq
from typing import List, Tuple, Dict, Optional

DB = "campus.db"

def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS nodes(
        id TEXT PRIMARY KEY,
        x REAL,
        y REAL,
        meta TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS edges(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        u TEXT,
        v TEXT,
        weight REAL,
        meta TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rooms(
        id TEXT PRIMARY KEY,
        node_id TEXT,
        capacity INTEGER,
        scheduled BOOLEAN DEFAULT 1,
        override_open BOOLEAN DEFAULT 0
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id TEXT,
        reporter TEXT,
        occupancy INTEGER,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

init_db()

app = FastAPI(title="Campus Navigation & Space Optimization")

class PathRequest(BaseModel):
    source: str
    target: str

class OverrideRequest(BaseModel):
    room_id: str
    force_open: bool
    reason: Optional[str] = None

class ReportRequest(BaseModel):
    room_id: str
    reporter: str
    occupancy: int

def dijkstra(source: str, target: str) -> Tuple[float, List[str]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM nodes WHERE id=?", (source,))
    if not cur.fetchone():
        raise KeyError("source not found")
    cur.execute("SELECT id FROM nodes WHERE id=?", (target,))
    if not cur.fetchone():
        raise KeyError("target not found")

    # build adjacency
    cur.execute("SELECT u,v,weight FROM edges")
    adj: Dict[str, List[Tuple[float,str]]] = {}
    for u,v,w in cur.fetchall():
        adj.setdefault(u, []).append((w,v))
        adj.setdefault(v, []).append((w,u))

    pq = [(0.0, source, [])]
    seen = {}
    while pq:
        dist,u,path = heapq.heappop(pq)
        if u in seen and seen[u] <= dist:
            continue
        path = path + [u]
        seen[u] = dist
        if u == target:
            conn.close()
            return dist, path
        for w,v in adj.get(u, []):
            nd = dist + w
            if v not in seen or nd < seen[v]:
                heapq.heappush(pq, (nd, v, path))

    conn.close()
    raise KeyError("no path")

@app.post("/path")
def compute_path(req: PathRequest):
    try:
        dist, path = dijkstra(req.source, req.target)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"distance": dist, "path": path}

@app.post("/report")
def report_occupancy(r: ReportRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO reports(room_id,reporter,occupancy) VALUES(?,?,?)",
                (r.room_id, r.reporter, r.occupancy))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.post("/override")
def override_room(o: OverrideRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM rooms WHERE id=?", (o.room_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="room not found")
    cur.execute("UPDATE rooms SET override_open=? WHERE id=?", (1 if o.force_open else 0, o.room_id))
    conn.commit()
    conn.close()
    return {"room_id": o.room_id, "override_open": o.force_open}

# Simple seed helper for manual testing
@app.post("/seed")
def seed():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
    INSERT OR IGNORE INTO nodes(id,x,y,meta) VALUES
      ('gateA',0,0,'Main gate'),
      ('hall1',100,0,'Lecture Hall 1'),
      ('hall2',200,0,'Lecture Hall 2'),
      ('library',150,100,'Library');
    INSERT OR IGNORE INTO edges(u,v,weight) VALUES
      ('gateA','hall1',100),
      ('hall1','hall2',100),
      ('hall2','library',120),
      ('hall1','library',130);
    INSERT OR IGNORE INTO rooms(id,node_id,capacity,scheduled,override_open) VALUES
      ('R101','hall1',60,1,0),
      ('R102','hall2',40,1,0);
    """)
    conn.commit()
    conn.close()
    return {"seeded": True}

@app.get("/rooms")
def list_rooms():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id,node_id,capacity,scheduled,override_open FROM rooms")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == '__main__':
    print("This module is a FastAPI app. Run with uvicorn.")
