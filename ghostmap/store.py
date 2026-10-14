"""Bounded SQLite queries. Each worker opens its own connection."""
import ipaddress
from contextlib import contextmanager, nullcontext
import sqlite3
from pathlib import Path

KINDS = ("Host", "Service", "Finding", "Credential", "Access", "Note")

class Store:
    def __init__(self, path):
        self._batch = False
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(self.path, timeout=15)
        self.path.chmod(0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA foreign_keys=ON;
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS nodes(id INTEGER PRIMARY KEY, project INTEGER NOT NULL REFERENCES projects(id),
          kind TEXT NOT NULL, label TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'hypothesis', evidence TEXT NOT NULL DEFAULT '', x REAL DEFAULT 0, y REAL DEFAULT 0,
          UNIQUE(project,kind,label));
        CREATE TABLE IF NOT EXISTS edges(id INTEGER PRIMARY KEY, project INTEGER REFERENCES projects(id),
          source INTEGER REFERENCES nodes(id), target INTEGER REFERENCES nodes(id), label TEXT DEFAULT '',
          UNIQUE(source,target,label));
        CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, project INTEGER REFERENCES projects(id),
          target TEXT, profile TEXT, state TEXT, detail TEXT DEFAULT '', created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS node_project ON nodes(project,id);
        CREATE INDEX IF NOT EXISTS edge_project ON edges(project);
        ''')
        columns = {r[1] for r in self.db.execute('PRAGMA table_info(nodes)')}
        if 'evidence' not in columns:
            with self.write():
                self.db.execute("ALTER TABLE nodes ADD COLUMN evidence TEXT NOT NULL DEFAULT ''")
    def write(self):
        return nullcontext() if self._batch else self.db
    @contextmanager
    def batch(self):
        self._batch=True
        try:
            with self.db:
                yield
        finally:
            self._batch=False
    def close(self):
        self.db.close()
    def projects(self):
        return self.db.execute('SELECT * FROM projects ORDER BY id DESC LIMIT 1000').fetchall()
    def project(self, name):
        name = name.strip()
        if not name or len(name) > 120:
            raise ValueError('Project name must contain 1–120 characters')
        with self.write():
            return self.db.execute('INSERT INTO projects(name) VALUES (?)', (name,)).lastrowid
    def node(self, project, kind, label, detail='', status='hypothesis', x=0, y=0, evidence=''):
        if kind not in KINDS or status not in ('hypothesis','confirmed'):
            raise ValueError('Invalid node type or status')
        label = label.strip()
        if not label or len(label) > 250:
            raise ValueError('Label must contain 1–250 characters')
        with self.write():
            self.db.execute('INSERT INTO nodes(project,kind,label,detail,status,x,y,evidence) VALUES(?,?,?,?,?,?,?,?) '
                'ON CONFLICT(project,kind,label) DO UPDATE SET evidence=excluded.evidence,status=excluded.status',
                (project,kind,label,detail,status,x,y,evidence))
        return self.db.execute('SELECT id FROM nodes WHERE project=? AND kind=? AND label=?', (project,kind,label)).fetchone()[0]
    def host(self, project, address):
        return self.node(project,'Host',str(ipaddress.ip_address(address.strip())))
    def nodes(self, project, search='', offset=0, limit=400):
        return self.db.execute('SELECT * FROM nodes WHERE project=? AND (label LIKE ? OR detail LIKE ?) '
            'ORDER BY id LIMIT ? OFFSET ?', (project,'%'+search+'%','%'+search+'%',min(limit,400),offset)).fetchall()
    def count(self, project):
        return self.db.execute('SELECT count(*) FROM nodes WHERE project=?',(project,)).fetchone()[0]
    def edge(self, project, source, target, label='related'):
        if source == target:
            raise ValueError('Select two different nodes')
        rows=self.db.execute('SELECT id FROM nodes WHERE project=? AND id IN (?,?)',(project,source,target)).fetchall()
        if len(rows)!=2:
            raise ValueError('Both nodes must belong to this project')
        with self.write():
            self.db.execute('INSERT OR IGNORE INTO edges(project,source,target,label) VALUES(?,?,?,?)', (project,source,target,label))
    def edges(self, project, ids):
        if not ids: return []
        placeholders=','.join('?' for _ in ids)
        return self.db.execute(f'SELECT * FROM edges WHERE project=? AND source IN ({placeholders}) AND target IN ({placeholders})', (project,*ids,*ids)).fetchall()
    def position(self, node, x, y):
        with self.write():
            self.db.execute('UPDATE nodes SET x=?,y=? WHERE id=?',(x,y,node))
    def details(self, node, detail, status):
        with self.write():
            self.db.execute('UPDATE nodes SET detail=?,status=? WHERE id=?',(detail,status,node))
    def task(self, project, target, profile):
        with self.write():
            return self.db.execute("INSERT INTO tasks(project,target,profile,state) VALUES(?,?,?,'running')",(project,target,profile)).lastrowid
    def finish_task(self, task, state, detail=''):
        with self.write():
            self.db.execute('UPDATE tasks SET state=?,detail=? WHERE id=?',(state,detail,task))
    def tasks(self, project):
        return self.db.execute('SELECT * FROM tasks WHERE project=? ORDER BY id DESC LIMIT 100',(project,)).fetchall()
