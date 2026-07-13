import os
import sqlite3
from contextlib import contextmanager

from config import DATA_DIR, DATABASE_PATH

_initialized = False


def init_db():
    global _initialized
    os.makedirs(DATA_DIR, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS bases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL,
                ativa INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_id INTEGER NOT NULL,
                usuario TEXT NOT NULL,
                senha_hash TEXT NOT NULL,
                nome TEXT NOT NULL,
                nivel TEXT NOT NULL,
                senha_alterada INTEGER NOT NULL DEFAULT 0,
                ativo INTEGER NOT NULL DEFAULT 1,
                UNIQUE (base_id, usuario),
                FOREIGN KEY (base_id) REFERENCES bases (id)
            );

            CREATE TABLE IF NOT EXISTS ativos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                codigo TEXT NOT NULL,
                tipo TEXT NOT NULL DEFAULT '',
                patrimonio TEXT NOT NULL DEFAULT '',
                data_aquisicao TEXT,
                local TEXT NOT NULL DEFAULT 'base',
                em_manutencao INTEGER NOT NULL DEFAULT 0,
                ordem_servico TEXT NOT NULL DEFAULT '',
                observacoes TEXT NOT NULL DEFAULT '',
                atualizado_em TEXT,
                UNIQUE (base_id, codigo),
                FOREIGN KEY (base_id) REFERENCES bases (id)
            );

            CREATE INDEX IF NOT EXISTS idx_ativos_base_manutencao
                ON ativos (base_id, em_manutencao);

            CREATE TABLE IF NOT EXISTS manutencoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_id INTEGER NOT NULL,
                ativo_id INTEGER NOT NULL,
                os_numero TEXT NOT NULL,
                data_abertura TEXT NOT NULL,
                observacoes_abertura TEXT NOT NULL DEFAULT '',
                responsavel TEXT NOT NULL,
                data_conclusao TEXT,
                observacoes_encerramento TEXT NOT NULL DEFAULT '',
                aberta INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL,
                FOREIGN KEY (base_id) REFERENCES bases (id),
                FOREIGN KEY (ativo_id) REFERENCES ativos (id)
            );

            CREATE INDEX IF NOT EXISTS idx_manutencoes_ativo
                ON manutencoes (ativo_id, aberta);

            CREATE INDEX IF NOT EXISTS idx_manutencoes_base
                ON manutencoes (base_id, data_abertura);

            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL UNIQUE,
                senha_hash TEXT NOT NULL,
                nome TEXT NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS historico_ativos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_id INTEGER NOT NULL,
                ativo_id INTEGER,
                codigo TEXT NOT NULL,
                nome TEXT NOT NULL,
                acao TEXT NOT NULL,
                usuario TEXT NOT NULL,
                usuario_nome TEXT NOT NULL DEFAULT '',
                detalhes TEXT NOT NULL DEFAULT '',
                em_manutencao INTEGER,
                local TEXT,
                ordem_servico TEXT,
                criado_em TEXT NOT NULL,
                FOREIGN KEY (base_id) REFERENCES bases (id)
            );

            CREATE INDEX IF NOT EXISTS idx_historico_base_data
                ON historico_ativos (base_id, criado_em);
            """
        )
        _migrar_colunas_ativos(conn)
    _seed_admin_if_needed()
    _initialized = True


def _migrar_colunas_ativos(conn):
    """Adiciona colunas novas em bancos já existentes."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(ativos)").fetchall()}
    alteracoes = []
    if "tipo" not in cols:
        alteracoes.append("ALTER TABLE ativos ADD COLUMN tipo TEXT NOT NULL DEFAULT ''")
    if "patrimonio" not in cols:
        alteracoes.append(
            "ALTER TABLE ativos ADD COLUMN patrimonio TEXT NOT NULL DEFAULT ''"
        )
    if "data_aquisicao" not in cols:
        alteracoes.append("ALTER TABLE ativos ADD COLUMN data_aquisicao TEXT")
    for sql in alteracoes:
        conn.execute(sql)


def _seed_admin_if_needed():
    from werkzeug.security import generate_password_hash

    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
        if count == 0:
            conn.execute(
                """
                INSERT INTO admins (usuario, senha_hash, nome, ativo)
                VALUES (?, ?, ?, 1)
                """,
                ("admin", generate_password_hash("admin1234"), "Administrador"),
            )


@contextmanager
def get_conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def check_connection():
    try:
        init_db()
        with get_conn() as conn:
            conn.execute("SELECT 1")
        return True, None
    except Exception as exc:
        return False, str(exc)
