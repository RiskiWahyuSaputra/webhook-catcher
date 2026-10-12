import sqlite3
import os
import json
import time

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requests.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS captured_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                query_params TEXT,
                headers TEXT NOT NULL,
                body TEXT,
                client_ip TEXT,
                content_type TEXT,
                size_bytes INTEGER,
                created_at INTEGER NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_endpoint ON captured_requests (endpoint)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON captured_requests (created_at)")
    conn.close()

def save_request(req_data):
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO captured_requests 
            (uuid, method, path, endpoint, query_params, headers, body, client_ip, content_type, size_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            req_data["uuid"],
            req_data["method"],
            req_data["path"],
            req_data["endpoint"],
            json.dumps(req_data.get("query_params", {})),
            json.dumps(req_data.get("headers", {})),
            req_data.get("body", ""),
            req_data.get("client_ip", ""),
            req_data.get("content_type", ""),
            req_data.get("size_bytes", 0),
            int(time.time())
        ))
    conn.close()

def list_requests(endpoint=None, search=None, limit=100):
    conn = get_connection()
    query = "SELECT * FROM captured_requests WHERE 1=1"
    params = []

    if endpoint:
        query += " AND endpoint = ?"
        params.append(endpoint)

    if search:
        query += " AND (path LIKE ? OR body LIKE ? OR method LIKE ?)"
        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern])

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "uuid": r["uuid"],
            "method": r["method"],
            "path": r["path"],
            "endpoint": r["endpoint"],
            "query_params": json.loads(r["query_params"]) if r["query_params"] else {},
            "headers": json.loads(r["headers"]) if r["headers"] else {},
            "body": r["body"],
            "client_ip": r["client_ip"],
            "content_type": r["content_type"],
            "size_bytes": r["size_bytes"],
            "created_at": r["created_at"]
        })
    return result

def get_request_by_id(req_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM captured_requests WHERE id = ? OR uuid = ?", (req_id, str(req_id)))
    r = cursor.fetchone()
    conn.close()
    if not r:
        return None
    return {
        "id": r["id"],
        "uuid": r["uuid"],
        "method": r["method"],
        "path": r["path"],
        "endpoint": r["endpoint"],
        "query_params": json.loads(r["query_params"]) if r["query_params"] else {},
        "headers": json.loads(r["headers"]) if r["headers"] else {},
        "body": r["body"],
        "client_ip": r["client_ip"],
        "content_type": r["content_type"],
        "size_bytes": r["size_bytes"],
        "created_at": r["created_at"]
    }

def clear_requests(endpoint=None):
    conn = get_connection()
    with conn:
        if endpoint:
            conn.execute("DELETE FROM captured_requests WHERE endpoint = ?", (endpoint,))
        else:
            conn.execute("DELETE FROM captured_requests")
    conn.close()
