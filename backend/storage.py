import json
import os
import sqlite3
from pathlib import Path

DB = Path(os.getenv('AEGIS_DATA_DIR', str(Path(__file__).resolve().parent.parent / '.data'))) / 'aegis.sqlite3'

def connect():
    DB.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.executescript('''
    CREATE TABLE IF NOT EXISTS analyses (id TEXT PRIMARY KEY, created TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL, kind TEXT NOT NULL, group_id TEXT NOT NULL, notes TEXT NOT NULL, result TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY CHECK(id=1), consent TEXT NOT NULL, analysis_ids TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), retention_days INTEGER NOT NULL DEFAULT 0);
    INSERT OR IGNORE INTO settings(id,retention_days) VALUES (1,0);
    ''')
    days=c.execute('SELECT retention_days FROM settings WHERE id=1').fetchone()[0]
    if days: c.execute("DELETE FROM analyses WHERE created < strftime('%Y-%m-%dT%H:%M:%S', 'now', ?)",(f'-{days} days',))
    c.commit()
    return c

def decode(row, full=True):
    d=dict(row); d['result']=json.loads(d['result'])
    if not full: d.pop('text')
    return d
