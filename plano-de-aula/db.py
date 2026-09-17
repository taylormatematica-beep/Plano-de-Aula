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
    # Pool: mantém algumas conexões abertas e as reaproveita. Abrir uma conexão nova no PostgreSQL
    # do Render custa ~1-2 s; com o pool, a maioria das requisições nem toca nesse custo.
    try:
        from psycopg_pool import ConnectionPool  # type: ignore
        _POOL = ConnectionPool(
            DATABASE_URL, min_size=1, max_size=int(os.getenv("DB_POOL_MAX", "6")),
            max_idle=300, max_lifetime=1800, timeout=30, open=False,   # abre na 1ª consulta (não trava a subida)
            kwargs={"connect_timeout": 15, "keepalives": 1, "keepalives_idle": 60},
            check=ConnectionPool.check_connection,
        )
    except Exception:  # pool indisponível -> conexões avulsas (funciona, só é mais lento)
        _POOL = None
else:
    DATA_DIR = Path(os.getenv("DATA_DIR") or (Path(__file__).parent / "dados"))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = DATA_DIR / "historico.db"


@contextmanager
def conexao():
    if USA_PG:
        if _POOL is not None:
            if getattr(_POOL, "_opened", False) is False:
                try:
                    _POOL.open(wait=False)
                except Exception:
                    pass
            with _POOL.connection() as con:   # devolve ao pool ao sair (commit/rollback automáticos)
                yield con
            return
        con = psycopg.connect(DATABASE_URL, connect_timeout=15)
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
        con.execute(f"""CREATE TABLE IF NOT EXISTS atividades (
            id              {pk},
            criado_em       TEXT NOT NULL,
            professor       TEXT NOT NULL,
            professor_email TEXT,
            disciplina      TEXT NOT NULL,
            serie           TEXT NOT NULL,
            tipo            TEXT NOT NULL,
            titulo          TEXT,
            avaliativa      INTEGER NOT NULL DEFAULT 0,
            valor_total     REAL,
            planos_ids      TEXT,
            params_json     TEXT NOT NULL,
            conteudo_json   TEXT NOT NULL,
            drive_file_id   TEXT,
            drive_link      TEXT,
            drive_em        TEXT
        )""")
        con.execute(f"""CREATE TABLE IF NOT EXISTS aplicacoes (
            id              {pk},
            atividade_id    INTEGER NOT NULL,
            codigo          TEXT NOT NULL UNIQUE,
            turma           TEXT,
            criado_em       TEXT NOT NULL,
            aberta          INTEGER NOT NULL DEFAULT 1,
            encerrada_em    TEXT,
            embaralhar      INTEGER NOT NULL DEFAULT 1,
            mostrar_nota    INTEGER NOT NULL DEFAULT 0,
            tempo_min       INTEGER
        )""")
        con.execute(f"""CREATE TABLE IF NOT EXISTS respostas (
            id              {pk},
            aplicacao_id    INTEGER NOT NULL,
            aluno_nome      TEXT NOT NULL,
            aluno_numero    TEXT,
            origem          TEXT NOT NULL DEFAULT 'online',
            iniciado_em     TEXT,
            enviado_em      TEXT,
            respostas_json  TEXT NOT NULL,
            correcao_json   TEXT,
            nota            REAL,
            nota_me         REAL,
            nota_disc       REAL,
            corrigido_em    TEXT,
            status          TEXT NOT NULL DEFAULT 'pendente'
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_resp_aplic ON respostas(aplicacao_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_aplic_ativ ON aplicacoes(atividade_id)")
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
_cfg_cache: dict = {}
_CFG_TTL = 30  # segundos — evita ir ao banco a cada clique para ler configurações que quase não mudam


def config_get(chave: str, padrao: str = "") -> str:
    import time as _t
    hit = _cfg_cache.get(chave)
    if hit and hit[1] > _t.time():
        return hit[0] or padrao
    with conexao() as con:
        cur = con.execute(_q("SELECT valor FROM config WHERE chave=?"), (chave,))
        row = cur.fetchone()
    val = (row[0] if row else None)
    _cfg_cache[chave] = (val, _t.time() + _CFG_TTL)
    return val or padrao


def config_set(chave: str, valor: str):
    _cfg_cache.pop(chave, None)
    with conexao() as con:
        con.execute(_q("INSERT INTO config (chave, valor) VALUES (?,?) "
                       "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor"), (chave, valor))


def config_del(*chaves: str):
    for c in chaves:
        _cfg_cache.pop(c, None)
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
                        visto_codigo, drive_link, drive_em, dados_json
                 FROM planos {where} ORDER BY id DESC LIMIT {int(limite)}""")
    with conexao() as con:
        rows = _linhas(con.execute(sql, params))
    for r in rows:   # expõe só o conteúdo (campo digitado pelo professor), sem inflar a resposta
        try:
            r["conteudo"] = (json.loads(r.pop("dados_json") or "{}").get("conteudo") or "")[:200]
        except Exception:
            r.pop("dados_json", None); r["conteudo"] = ""
    return rows


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


def planos_por_professor() -> dict:
    """{professor_email_ou_nome: {"total": n, "visados": n, "ultimo": data}} para o relatório de usuários."""
    with conexao() as con:
        linhas = _linhas(con.execute(
            "SELECT professor, dados_json, visto_em, criado_em FROM planos"))
    out: dict = {}
    for l in linhas:
        try:
            email = (json.loads(l["dados_json"] or "{}").get("professor_email") or "").lower()
        except Exception:
            email = ""
        for chave in {email, (l["professor"] or "").strip().lower()} - {""}:
            d = out.setdefault(chave, {"total": 0, "visados": 0, "ultimo": ""})
            d["total"] += 1
            if l["visto_em"]:
                d["visados"] += 1
            if (l["criado_em"] or "") > d["ultimo"]:
                d["ultimo"] = l["criado_em"] or ""
    return out


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


def semelhantes(professor: str, professor_email: str | None, disciplina: str, serie: str,
                data_ref: str, conteudo: str, limite: int = 5) -> list[dict]:
    """Planos do mesmo professor com o mesmo contexto: mesma disciplina+série e (mesma semana OU conteúdo/tema parecido)."""
    import unicodedata, re as _re

    def norm(t: str) -> set:
        t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
        return {w for w in _re.split(r"[^a-z0-9]+", t) if len(w) > 3}

    itens = listar(professor=professor, professor_email=professor_email, disciplina=disciplina, serie=serie, limite=300)
    alvo = norm(conteudo)
    out = []
    for i in itens:
        mesma_semana = (i.get("data_ref") or "").strip() == (data_ref or "").strip()
        pal = norm((i.get("tema") or "") + " " + (i.get("conteudo") or ""))
        inter = len(alvo & pal)
        parecido = bool(alvo) and (inter / max(1, min(len(alvo), len(pal)))) >= 0.6
        if mesma_semana or parecido:
            i["motivo"] = "mesma semana" if mesma_semana else "conteúdo parecido"
            out.append(i)
    return out[:limite]


# ---------------------------------------------------------------- provas e atividades
def atividade_inserir(params: dict, conteudo: dict) -> int:
    sql = _q("""INSERT INTO atividades (criado_em, professor, professor_email, disciplina, serie, tipo, titulo,
                avaliativa, valor_total, planos_ids, params_json, conteudo_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""")
    vals = (fuso.agora_txt(), (params.get("professor") or "").strip(),
            (params.get("professor_email") or "").lower().strip() or None,
            params.get("disciplina", ""), params.get("serie", ""), params.get("tipo", "prova"),
            conteudo.get("titulo", ""), 1 if params.get("avaliativa") else 0,
            float(params.get("valor_total") or 0) if params.get("avaliativa") else None,
            ",".join(str(i) for i in params.get("planos_ids") or []),
            json.dumps(params, ensure_ascii=False), json.dumps(conteudo, ensure_ascii=False))
    with conexao() as con:
        return int(con.execute(sql, vals).fetchone()[0])


def atividade_atualizar(id_: int, params: dict, conteudo: dict):
    sql = _q("""UPDATE atividades SET tipo=?, titulo=?, avaliativa=?, valor_total=?, params_json=?, conteudo_json=?
                WHERE id=?""")
    with conexao() as con:
        con.execute(sql, (params.get("tipo", "prova"), conteudo.get("titulo", ""), 1 if params.get("avaliativa") else 0,
                          float(params.get("valor_total") or 0) if params.get("avaliativa") else None,
                          json.dumps(params, ensure_ascii=False), json.dumps(conteudo, ensure_ascii=False), id_))


def atividade_obter(id_: int) -> dict | None:
    with conexao() as con:
        rows = _linhas(con.execute(_q("SELECT * FROM atividades WHERE id=?"), (id_,)))
    if not rows:
        return None
    r = rows[0]
    r["params"] = json.loads(r.pop("params_json"))
    r["conteudo"] = json.loads(r.pop("conteudo_json"))
    return r


def atividades_listar(professor: str | None = None, professor_email: str | None = None,
                      disciplina: str = "", serie: str = "", busca: str = "", limite: int = 500) -> list[dict]:
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
        cond.append("(LOWER(titulo) LIKE ? OR LOWER(professor) LIKE ?)")
        params += [f"%{busca.lower()}%"] * 2
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    sql = _q(f"""SELECT id, criado_em, professor, professor_email, disciplina, serie, tipo, titulo, avaliativa,
                        valor_total, planos_ids, drive_link, drive_em, conteudo_json
                 FROM atividades {where} ORDER BY id DESC LIMIT {int(limite)}""")
    with conexao() as con:
        rows = _linhas(con.execute(sql, params))
    for r in rows:
        try:
            r["n_questoes"] = len(json.loads(r.pop("conteudo_json") or "{}").get("questoes") or [])
        except Exception:
            r.pop("conteudo_json", None); r["n_questoes"] = 0
    return rows


def atividade_excluir(id_: int):
    with conexao() as con:
        con.execute(_q("DELETE FROM atividades WHERE id=?"), (id_,))


def atividade_set_drive(id_: int, file_id: str | None, link: str | None):
    with conexao() as con:
        con.execute(_q("UPDATE atividades SET drive_file_id=?, drive_link=?, drive_em=? WHERE id=?"),
                    (file_id, link, fuso.agora_txt() if file_id else None, id_))


def planos_obter_varios(ids: list[int]) -> list[dict]:
    """Planos completos (dados + plano) na ordem dos ids informados."""
    ids = [int(i) for i in ids][:20]
    if not ids:
        return []
    marcas = ",".join("?" * len(ids))
    with conexao() as con:
        rows = _linhas(con.execute(_q(f"SELECT * FROM planos WHERE id IN ({marcas})"), ids))
    por_id = {}
    for r in rows:
        r["dados"] = json.loads(r.pop("dados_json")); r["plano"] = json.loads(r.pop("plano_json"))
        por_id[r["id"]] = r
    return [por_id[i] for i in ids if i in por_id]


# ---------- aplicações (prova online / lançamento) e respostas dos alunos
def aplicacao_criar(atividade_id: int, codigo: str, turma: str = "", embaralhar: bool = True,
                    mostrar_nota: bool = False, tempo_min: int | None = None) -> int:
    with conexao() as con:
        cur = con.execute(_q("""INSERT INTO aplicacoes (atividade_id, codigo, turma, criado_em, embaralhar, mostrar_nota, tempo_min)
                                VALUES (?,?,?,?,?,?,?) RETURNING id"""),
                          (atividade_id, codigo, turma, fuso.agora_txt(), 1 if embaralhar else 0, 1 if mostrar_nota else 0, tempo_min))
        return int(cur.fetchone()[0])


def aplicacao_por_codigo(codigo: str) -> dict | None:
    with conexao() as con:
        rows = _linhas(con.execute(_q("SELECT * FROM aplicacoes WHERE UPPER(codigo)=UPPER(?)"), (codigo.strip(),)))
    return rows[0] if rows else None


def aplicacao_obter(id_: int) -> dict | None:
    with conexao() as con:
        rows = _linhas(con.execute(_q("SELECT * FROM aplicacoes WHERE id=?"), (id_,)))
    return rows[0] if rows else None


def aplicacoes_da_atividade(atividade_id: int) -> list[dict]:
    with conexao() as con:
        rows = _linhas(con.execute(_q("""SELECT a.*, 
                (SELECT COUNT(*) FROM respostas r WHERE r.aplicacao_id=a.id AND r.enviado_em IS NOT NULL) AS n_respostas,
                (SELECT COUNT(*) FROM respostas r WHERE r.aplicacao_id=a.id AND r.status='corrigido') AS n_corrigidas
                FROM aplicacoes a WHERE a.atividade_id=? ORDER BY a.id DESC"""), (atividade_id,)))
    return rows


def aplicacao_atualizar(id_: int, **campos):
    if not campos:
        return
    sets = ", ".join(f"{k}=?" for k in campos)
    with conexao() as con:
        con.execute(_q(f"UPDATE aplicacoes SET {sets} WHERE id=?"), (*campos.values(), id_))


def aplicacao_excluir(id_: int):
    with conexao() as con:
        con.execute(_q("DELETE FROM respostas WHERE aplicacao_id=?"), (id_,))
        con.execute(_q("DELETE FROM aplicacoes WHERE id=?"), (id_,))


def resposta_criar(aplicacao_id: int, aluno_nome: str, aluno_numero: str, respostas: dict, origem: str = "online",
                   enviado: bool = True) -> int:
    agora = fuso.agora_txt()
    with conexao() as con:
        cur = con.execute(_q("""INSERT INTO respostas (aplicacao_id, aluno_nome, aluno_numero, origem, iniciado_em, enviado_em, respostas_json)
                                VALUES (?,?,?,?,?,?,?) RETURNING id"""),
                          (aplicacao_id, aluno_nome.strip(), (aluno_numero or "").strip(), origem, agora,
                           agora if enviado else None, json.dumps(respostas, ensure_ascii=False)))
        return int(cur.fetchone()[0])


def resposta_obter(id_: int) -> dict | None:
    with conexao() as con:
        rows = _linhas(con.execute(_q("SELECT * FROM respostas WHERE id=?"), (id_,)))
    if not rows:
        return None
    r = rows[0]
    r["respostas"] = json.loads(r.pop("respostas_json") or "{}")
    r["correcao"] = json.loads(r.pop("correcao_json") or "null")
    return r


def respostas_da_aplicacao(aplicacao_id: int) -> list[dict]:
    with conexao() as con:
        rows = _linhas(con.execute(_q("SELECT * FROM respostas WHERE aplicacao_id=? ORDER BY aluno_numero, aluno_nome"), (aplicacao_id,)))
    for r in rows:
        r["respostas"] = json.loads(r.pop("respostas_json") or "{}")
        r["correcao"] = json.loads(r.pop("correcao_json") or "null")
    return rows


def resposta_ja_enviada(aplicacao_id: int, aluno_nome: str, aluno_numero: str) -> dict | None:
    """Evita envio duplicado do mesmo aluno na mesma aplicação (mesmo número ou mesmo nome)."""
    with conexao() as con:
        rows = _linhas(con.execute(_q("""SELECT id, aluno_nome, aluno_numero, enviado_em FROM respostas
                                          WHERE aplicacao_id=? AND enviado_em IS NOT NULL AND
                                          ((aluno_numero<>'' AND aluno_numero=?) OR LOWER(aluno_nome)=LOWER(?))"""),
                                      (aplicacao_id, (aluno_numero or "").strip(), aluno_nome.strip())))
    return rows[0] if rows else None


def resposta_corrigir(id_: int, correcao: dict, nota: float, nota_me: float, nota_disc: float, status: str):
    with conexao() as con:
        con.execute(_q("""UPDATE respostas SET correcao_json=?, nota=?, nota_me=?, nota_disc=?, corrigido_em=?, status=?
                          WHERE id=?"""),
                    (json.dumps(correcao, ensure_ascii=False), nota, nota_me, nota_disc, fuso.agora_txt(), status, id_))


def resposta_atualizar(id_: int, aluno_nome: str | None = None, aluno_numero: str | None = None, respostas: dict | None = None):
    campos, vals = [], []
    if aluno_nome is not None:
        campos.append("aluno_nome=?"); vals.append(aluno_nome.strip())
    if aluno_numero is not None:
        campos.append("aluno_numero=?"); vals.append(aluno_numero.strip())
    if respostas is not None:
        campos.append("respostas_json=?"); vals.append(json.dumps(respostas, ensure_ascii=False))
    if not campos:
        return
    with conexao() as con:
        con.execute(_q(f"UPDATE respostas SET {', '.join(campos)} WHERE id=?"), (*vals, id_))


def resposta_excluir(id_: int):
    with conexao() as con:
        con.execute(_q("DELETE FROM respostas WHERE id=?"), (id_,))
