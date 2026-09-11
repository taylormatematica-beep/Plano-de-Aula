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
    with conexao() as con:
        con.execute(ddl)


def inserir(dados: dict, plano: dict) -> int:
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sql = _q("""INSERT INTO planos (criado_em, professor, disciplina, serie, tema, data_ref, dados_json, plano_json)
                VALUES (?,?,?,?,?,?,?,?) RETURNING id""")
    params = (agora, dados.get("professor", "").strip(), dados.get("disciplina", ""), dados.get("serie", ""),
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
           limite: int = 500) -> list[dict]:
    cond, params = [], []
    if professor:
        cond.append("LOWER(professor)=LOWER(?)"); params.append(professor.strip())
    if disciplina:
        cond.append("disciplina=?"); params.append(disciplina)
    if serie:
        cond.append("serie=?"); params.append(serie)
    if busca:
        cond.append("(LOWER(tema) LIKE ? OR LOWER(professor) LIKE ?)")
        params += [f"%{busca.lower()}%", f"%{busca.lower()}%"]
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    sql = _q(f"""SELECT id, criado_em, professor, disciplina, serie, tema, data_ref, visto_em, visto_por
                 FROM planos {where} ORDER BY id DESC LIMIT {int(limite)}""")
    with conexao() as con:
        return _linhas(con.execute(sql, params))


def excluir(id_: int):
    with conexao() as con:
        con.execute(_q("DELETE FROM planos WHERE id=?"), (id_,))


def marcar_visto(id_: int, por: str, desfazer: bool = False):
    with conexao() as con:
        if desfazer:
            con.execute(_q("UPDATE planos SET visto_em=NULL, visto_por=NULL WHERE id=?"), (id_,))
        else:
            con.execute(_q("UPDATE planos SET visto_em=?, visto_por=? WHERE id=?"),
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), por, id_))


def professores() -> list[str]:
    with conexao() as con:
        cur = con.execute("SELECT DISTINCT professor FROM planos ORDER BY professor")
        return [r[0] for r in cur.fetchall()]
