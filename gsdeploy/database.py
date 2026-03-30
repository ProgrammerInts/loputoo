import sqlite3
import os

DB_PATH = os.path.expanduser("~/.local/share/gsdeploy/gsdeploy.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def slugify(name):
    import re
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or "vm"


def _migrate(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(vms)").fetchall()]
    if "vm_type" not in cols:
        conn.execute("ALTER TABLE vms ADD COLUMN vm_type TEXT NOT NULL DEFAULT 'game'")
    if "hostname" not in cols:
        conn.execute("ALTER TABLE vms ADD COLUMN hostname TEXT NOT NULL DEFAULT ''")
        rows = conn.execute("SELECT id, name FROM vms WHERE hostname = ''").fetchall()
        for row in rows:
            conn.execute("UPDATE vms SET hostname = ? WHERE id = ?",
                         (slugify(row["name"]), row["id"]))
    if "admin_username" not in cols:
        conn.execute("ALTER TABLE vms ADD COLUMN admin_username TEXT NOT NULL DEFAULT 'admin'")
    if "initial_user" not in cols:
        conn.execute("ALTER TABLE vms ADD COLUMN initial_user TEXT NOT NULL DEFAULT ''")
        conn.execute("UPDATE vms SET initial_user = ssh_user WHERE initial_user = ''")
    if "admin_password" not in cols:
        conn.execute("ALTER TABLE vms ADD COLUMN admin_password TEXT NOT NULL DEFAULT ''")
    gs_cols = [r[1] for r in conn.execute("PRAGMA table_info(game_servers)").fetchall()]
    if "version" not in gs_cols:
        conn.execute("ALTER TABLE game_servers ADD COLUMN version TEXT NOT NULL DEFAULT ''")


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS vms (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL UNIQUE,
                hostname       TEXT NOT NULL UNIQUE,
                ip             TEXT NOT NULL,
                initial_user   TEXT NOT NULL,
                ssh_user       TEXT NOT NULL,
                admin_username TEXT NOT NULL DEFAULT 'admin',
                admin_password TEXT NOT NULL DEFAULT '',
                ssh_key        TEXT NOT NULL DEFAULT '~/.ssh/id_ed25519',
                vm_type        TEXT NOT NULL DEFAULT 'game'
            );

            CREATE TABLE IF NOT EXISTS game_servers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                vm_id       INTEGER NOT NULL REFERENCES vms(id) ON DELETE CASCADE,
                name        TEXT NOT NULL,
                game_type   TEXT NOT NULL,
                port        INTEGER NOT NULL,
                version     TEXT NOT NULL DEFAULT '',
                status      TEXT NOT NULL DEFAULT 'unknown'
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        _migrate(conn)


# --- VM queries ---

def get_vms():
    with get_connection() as conn:
        return conn.execute("SELECT * FROM vms ORDER BY name").fetchall()


def add_vm(name, ip, ssh_user, admin_username="admin", admin_password="", ssh_key="~/.ssh/id_ed25519", vm_type="game"):
    hostname = slugify(name)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO vms (name, hostname, ip, initial_user, ssh_user, admin_username, admin_password, ssh_key, vm_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, hostname, ip, ssh_user, ssh_user, admin_username, admin_password, ssh_key, vm_type),
        )


def remove_vm(vm_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM vms WHERE id = ?", (vm_id,))


def update_vm(vm_id, name, ip, initial_user, admin_username, admin_password, ssh_key, vm_type):
    hostname = slugify(name)
    with get_connection() as conn:
        conn.execute(
            "UPDATE vms SET name=?, hostname=?, ip=?, initial_user=?, admin_username=?, admin_password=?, ssh_key=?, vm_type=? WHERE id=?",
            (name, hostname, ip, initial_user, admin_username, admin_password, ssh_key, vm_type, vm_id),
        )


def get_vm(vm_id):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM vms WHERE id = ?", (vm_id,)).fetchone()


def set_vm_ssh_user(vm_id, ssh_user):
    with get_connection() as conn:
        conn.execute("UPDATE vms SET ssh_user = ? WHERE id = ?", (ssh_user, vm_id))


def get_vms_by_type(vm_type):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM vms WHERE vm_type = ? ORDER BY name", (vm_type,)
        ).fetchall()


# --- Game server queries ---

def get_servers(vm_id=None):
    with get_connection() as conn:
        if vm_id:
            return conn.execute(
                "SELECT * FROM game_servers WHERE vm_id = ? ORDER BY name", (vm_id,)
            ).fetchall()
        return conn.execute("SELECT * FROM game_servers ORDER BY name").fetchall()


def add_server(vm_id, name, game_type, port, version=""):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO game_servers (vm_id, name, game_type, port, version) VALUES (?, ?, ?, ?, ?)",
            (vm_id, name, game_type, port, version),
        )


def remove_server(server_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM game_servers WHERE id = ?", (server_id,))


def get_setting(key, default=None):
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def update_server_status(server_id, status):
    with get_connection() as conn:
        conn.execute(
            "UPDATE game_servers SET status = ? WHERE id = ?", (status, server_id)
        )
