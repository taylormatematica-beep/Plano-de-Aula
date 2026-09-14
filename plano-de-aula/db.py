"""
Histórico de planos gerados.

- Padrão: SQLite em ./dados/historico.db (ou na pasta indicada em DATA_DIR).
- Se existir a variável DATABASE_URL (postgres://...), usa PostgreSQL — recomendado
  em hospedagens cujo disco é apagado a cada publicação (ex.: Render gratuito).
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import fuso
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USA_PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))

if USA_PG:
    import psycopg  # type: ignore
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
else:
    DATA_DIR = Path(os.getenv("DATA_DIR") or (Path(__file__).parent / "dados"))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = DATA_DIR / "historico.db"


@contextmanager
def conexao():
    if USA_PG:
        con = psycopg.connect(DATABASE_URL)
    else:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _q(sql: str) -> str:
    """Converte placeholders '?' para '%s' quando for PostgreSQL."""
    return sql.replace("?", "%s") if USA_PG else sql


def _linhas(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def init():
    ddl = """
    CREATE TABLE IF NOT EXISTS planos (
        id          {pk},
        criado_em   TEXT NOT NULL,
        professor   TEXT NOT NULL,
        disciplina  TEXT NOT NULL,
        serie       TEXT NOT NULL,
        tema        TEXT,
        data_ref    TEXT,
        dados_json  TEXT NOT NULL,
        plano_json  TEXT NOT NULL,
        visto_em    TEXT,
        visto_por   TEXT
    )""".format(pk="SERIAL PRIMARY KEY" if USA_PG else "INTEGER PRIMARY KEY AUTOINCREMENT")
    pk = "SERIAL PRIMARY KEY" if USA_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with conexao() as con:
        con.execute(ddl)
        con.execute("CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT)")
        con.execute(f"""CREATE TABLE IF NOT EXISTS usuarios (
            id            {pk},
            email         TEXT NOT NULL UNIQUE,
            nome          TEXT,
            senha_hash    TEXT,
            perfil        TEXT NOT NULL DEFAULT 'professor',
            ativo         INTEGER NOT NULL DEFAULT 1,
            criado_em     TEXT NOT NULL,
            ultimo_acesso TEXT
        )""")
        con.execute(f"""CREATE TABLE IF NOT EXISTS tokens (
            id          {pk},
            usuario_id  INTEGER NOT NULL,
            token_hash  TEXT NOT NULL UNIQUE,
            expira_em   TEXT NOT NULL,
            usado_em    TEXT,
            criado_em   TEXT NOT NULL
        )""")
        con.execute(f"""CREATE TABLE IF NOT EXISTS documentos (
            id          {pk},
            titulo      TEXT NOT NULL,
            citacao     TEXT,
            categoria   TEXT DEFAULT 'ICE',
            arquivo     TEXT,
            tamanho     INTEGER,
            n_trechos   INTEGER DEFAULT 0,
            ativo       INTEGER NOT NULL DEFAULT 1,
            criado_em   TEXT NOT NULL
        )""")
        con.execute(f"""CREATE TABLE IF NOT EXISTS trechos (
            id            {pk},
            documento_id  INTEGER NOT NULL,
            ordem         INTEGER NOT NULL,
            texto         TEXT NOT NULL
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_trechos_doc ON trechos(documento_id)")
    for col in ("drive_pasta_id",):
        try:
            with conexao() as con:
                if USA_PG:
                    con.execute(f"ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS {col} TEXT")
                else:
                    con.execute(f"ALTER TABLE usuarios ADD COLUMN {col} TEXT")
        except Exception:
            pass
    # colunas adicionadas depois da 1ª versão (migração leve)
    for col in ("drive_file_id", "drive_link", "drive_em", "professor_email", "visto_codigo", "visto_email"):
        try:
            with conexao() as con:
                if USA_PG:
                    con.execute(f"ALTER TABLE planos ADD COLUMN IF NOT EXISTS {col} TEXT")
                else:
                    con.execute(f"ALTER TABLE planos ADD COLUMN {col} TEXT")
        except Exception:
            pass  # coluna já existe


# ---------------------------------------------------------------- config chave/valor
def config_get(chave: str, padrao: str = "") -> str:
    with conexao() as con:
        cur = con.execute(_q("SELECT valor FROM config WHERE chave=?"), (chave,))
        row = cur.fetchone()
    return (row[0] if row else None) or padrao


def config_set(chave: str, valor: str):
    with conexao() as con:
        con.execute(_q("INSERT INTO config (chave, valor) VALUES (?,?) "
                       "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor"), (chave, valor))


def config_del(*chaves: str):
    with conexao() as con:
        for c in chaves:
            con.execute(_q("DELETE FROM config WHERE chave=?"), (c,))


def set_drive(id_: int, file_id: str | None, link: str | None):
    with conexao() as con:
        con.execute(_q("UPDATE planos SET drive_file_id=?, drive_link=?, drive_em=? WHERE id=?"),
                    (file_id, link, fuso.agora_txt() if file_id else None, id_))


def inserir(dados: dict, plano: dict) -> int:
    agora = fuso.agora_txt()
    sql = _q("""INSERT INTO planos (criado_em, professor, professor_email, disciplina, serie, tema, data_ref, dados_json, plano_json)
                VALUES (?,?,?,?,?,?,?,?,?) RETURNING id""")
    params = (agora, dados.get("professor", "").strip(), (dados.get("professor_email") or "").lower().strip() or None,
              dados.get("disciplina", ""), dados.get("serie", ""),
              plano.get("tema", ""), dados.get("data", ""),
              json.dumps(dados, ensure_ascii=False), json.dumps(plano, ensure_ascii=False))
    with conexao() as con:
        cur = con.execute(sql, params)
        return int(cur.fetchone()[0])


def atualizar(id_: int, dados: dict, plano: dict):
    sql = _q("""UPDATE planos SET professor=?, disciplina=?, serie=?, tema=?, data_ref=?, dados_json=?, plano_json=?
                WHERE id=?""")
    with conexao() as con:
        con.execute(sql, (dados.get("professor", "").strip(), dados.get("disciplina", ""), dados.get("serie", ""),
                          plano.get("tema", ""), dados.get("data", ""),
                          json.dumps(dados, ensure_ascii=False), json.dumps(plano, ensure_ascii=False), id_))


def obter(id_: int) -> dict | None:
    with conexao() as con:
        cur = con.execute(_q("SELECT * FROM planos WHERE id=?"), (id_,))
        rows = _linhas(cur)
    if not rows:
        return None
    r = rows[0]
    r["dados"] = json.loads(r.pop("dados_json"))
    r["plano"] = json.loads(r.pop("plano_json"))
    return r


def listar(professor: str | None = None, disciplina: str = "", serie: str = "", busca: str = "",
           limite: int = 500, professor_email: str | None = None) -> list[dict]:
    cond, params = [], []
    if professor_email:
        cond.append("(LOWER(professor_email)=LOWER(?) OR (professor_email IS NULL AND LOWER(professor)=LOWER(?)))")
        params += [professor_email.strip(), (professor or "").strip()]
    elif professor:
        cond.append("LOWER(professor)=LOWER(?)"); params.append(professor.strip())
    if disciplina:
        cond.append("disciplina=?"); params.append(disciplina)
    if serie:
        cond.append("serie=?"); params.append(serie)
    if busca:
        cond.append("(LOWER(tema) LIKE ? OR LOWER(professor) LIKE ?)")
        params += [f"%{busca.lower()}%", f"%{busca.lower()}%"]
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    sql = _q(f"""SELECT id, criado_em, professor, professor_email, disciplina, serie, tema, data_ref, visto_em, visto_por,
                        visto_codigo, drive_link, drive_em
                 FROM planos {where} ORDER BY id DESC LIMIT {int(limite)}""")
    with conexao() as con:
        return _linhas(con.execute(sql, params))


def excluir(id_: int):
    with conexao() as con:
        con.execute(_q("DELETE FROM planos WHERE id=?"), (id_,))


def marcar_visto(id_: int, por: str, desfazer: bool = False, email: str = "", codigo: str = "") -> str:
    """Registra o visto eletrônico da supervisão. Devolve a data/hora gravada ('' ao desfazer)."""
    with conexao() as con:
        if desfazer:
            con.execute(_q("UPDATE planos SET visto_em=NULL, visto_por=NULL, visto_email=NULL, visto_codigo=NULL WHERE id=?"), (id_,))
            return ""
        agora = fuso.agora_txt()
        con.execute(_q("UPDATE planos SET visto_em=?, visto_por=?, visto_email=?, visto_codigo=? WHERE id=?"),
                    (agora, por, email or None, codigo or None, id_))
        return agora


def visto_info(id_: int) -> dict:
    with conexao() as con:
        rows = _linhas(con.execute(_q("SELECT visto_em, visto_por, visto_email, visto_codigo FROM planos WHERE id=?"), (id_,)))
    return rows[0] if rows else {}


def professores() -> list[str]:
    with conexao() as con:
        cur = con.execute("SELECT DISTINCT professor FROM planos ORDER BY professor")
        return [r[0] for r in cur.fetchall()]


# ---------------------------------------------------------------- usuários
def _agora() -> str:
    return fuso.agora_txt()


def usuario_por_email(email: str) -> dict | None:
    with conexao() as con:
        rows = _linhas(con.execute(_q("SELECT * FROM usuarios WHERE LOWER(email)=LOWER(?)"), (email.strip(),)))
    return rows[0] if rows else None


def usuario_por_id(id_: int) -> dict | None:
    with conexao() as con:
        rows = _linhas(con.execute(_q("SELECT * FROM usuarios WHERE id=?"), (id_,)))
    return rows[0] if rows else None


def usuario_criar(email: str, nome: str = "", perfil: str = "professor") -> dict:
    with conexao() as con:
        con.execute(_q("INSERT INTO usuarios (email, nome, perfil, criado_em) VALUES (?,?,?,?)"),
                    (email.lower().strip(), nome.strip(), perfil, _agora()))
    return usuario_por_email(email)


def usuario_definir_senha(id_: int, senha_hash: str, nome: str | None = None):
    with conexao() as con:
        if nome:
            con.execute(_q("UPDATE usuarios SET senha_hash=?, nome=? WHERE id=?"), (senha_hash, nome.strip(), id_))
        else:
            con.execute(_q("UPDATE usuarios SET senha_hash=? WHERE id=?"), (senha_hash, id_))


def usuario_atualizar(id_: int, **campos):
    permitidos = {"nome", "perfil", "ativo", "drive_pasta_id"}
    campos = {k: v for k, v in campos.items() if k in permitidos}
    if not campos:
        return
    sets = ", ".join(f"{k}=?" for k in campos)
    with conexao() as con:
        con.execute(_q(f"UPDATE usuarios SET {sets} WHERE id=?"), (*campos.values(), id_))


def usuario_tocar(id_: int):
    with conexao() as con:
        con.execute(_q("UPDATE usuarios SET ultimo_acesso=? WHERE id=?"), (_agora(), id_))


def usuario_excluir(id_: int):
    with conexao() as con:
        con.execute(_q("DELETE FROM tokens WHERE usuario_id=?"), (id_,))
        con.execute(_q("DELETE FROM usuarios WHERE id=?"), (id_,))


def usuarios_listar() -> list[dict]:
    with conexao() as con:
        return _linhas(con.execute(
            "SELECT id, email, nome, perfil, ativo, criado_em, ultimo_acesso, drive_pasta_id, "
            "CASE WHEN senha_hash IS NULL OR senha_hash='' THEN 0 ELSE 1 END AS tem_senha "
            "FROM usuarios ORDER BY nome, email"))


def usuarios_total_supervisao() -> int:
    with conexao() as con:
        cur = con.execute("SELECT COUNT(*) FROM usuarios WHERE perfil='supervisao' AND ativo=1")
        return int(cur.fetchone()[0])


# ---------------------------------------------------------------- tokens
def token_criar(usuario_id: int, token_hash: str, expira_em: str):
    with conexao() as con:
        con.execute(_q("INSERT INTO tokens (usuario_id, token_hash, expira_em, criado_em) VALUES (?,?,?,?)"),
                    (usuario_id, token_hash, expira_em, _agora()))


def token_ultimo(usuario_id: int) -> dict | None:
    with conexao() as con:
        rows = _linhas(con.execute(_q(
            "SELECT * FROM tokens WHERE usuario_id=? AND usado_em IS NULL ORDER BY id DESC LIMIT 1"), (usuario_id,)))
    return rows[0] if rows else None


def token_obter(token_hash: str) -> dict | None:
    with conexao() as con:
        rows = _linhas(con.execute(_q("SELECT * FROM tokens WHERE token_hash=?"), (token_hash,)))
    return rows[0] if rows else None


def token_usar(id_: int):
    with conexao() as con:
        con.execute(_q("UPDATE tokens SET usado_em=? WHERE id=?"), (_agora(), id_))
        # invalida outros tokens pendentes do mesmo usuário
        con.execute(_q("UPDATE tokens SET usado_em=? WHERE usado_em IS NULL AND usuario_id="
                       "(SELECT usuario_id FROM tokens WHERE id=?)"), (_agora(), id_))


# ---------------------------------------------------------------- biblioteca de documentos
def documento_criar(titulo: str, citacao: str, categoria: str, arquivo: str, tamanho: int, trechos: list[str]) -> int:
    with conexao() as con:
        cur = con.execute(_q("""INSERT INTO documentos (titulo, citacao, categoria, arquivo, tamanho, n_trechos, criado_em)
                                VALUES (?,?,?,?,?,?,?) RETURNING id"""),
                          (titulo.strip(), citacao.strip(), categoria, arquivo, tamanho, len(trechos), fuso.agora_txt()))
        did = int(cur.fetchone()[0])
        for i, t in enumerate(trechos):
            con.execute(_q("INSERT INTO trechos (documento_id, ordem, texto) VALUES (?,?,?)"), (did, i, t))
    return did


def documentos_listar(somente_ativos: bool = False) -> list[dict]:
    where = "WHERE ativo=1" if somente_ativos else ""
    with conexao() as con:
        return _linhas(con.execute(f"SELECT id, titulo, citacao, categoria, arquivo, tamanho, n_trechos, ativo, criado_em "
                                   f"FROM documentos {where} ORDER BY categoria, titulo"))


def documento_obter(id_: int) -> dict:
    with conexao() as con:
        rows = _linhas(con.execute(_q("SELECT * FROM documentos WHERE id=?"), (id_,)))
    return rows[0] if rows else {}


def documento_atualizar(id_: int, **campos):
    permitidos = {"titulo", "citacao", "categoria", "ativo"}
    campos = {k: v for k, v in campos.items() if k in permitidos}
    if not campos:
        return
    sets = ", ".join(f"{k}=?" for k in campos)
    with conexao() as con:
        con.execute(_q(f"UPDATE documentos SET {sets} WHERE id=?"), (*campos.values(), id_))


def documento_excluir(id_: int):
    with conexao() as con:
        con.execute(_q("DELETE FROM trechos WHERE documento_id=?"), (id_,))
        con.execute(_q("DELETE FROM documentos WHERE id=?"), (id_,))


def trechos_listar(doc_ids: list[int] | None) -> list[dict]:
    with conexao() as con:
        if doc_ids:
            marcas = ",".join("?" for _ in doc_ids)
            sql = _q(f"""SELECT t.id, t.documento_id, t.texto, d.titulo FROM trechos t
                         JOIN documentos d ON d.id=t.documento_id
                         WHERE d.ativo=1 AND t.documento_id IN ({marcas})""")
            return _linhas(con.execute(sql, tuple(doc_ids)))
        return _linhas(con.execute("""SELECT t.id, t.documento_id, t.texto, d.titulo FROM trechos t
                                      JOIN documentos d ON d.id=t.documento_id WHERE d.ativo=1"""))
