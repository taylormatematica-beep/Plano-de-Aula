"""
Assistente de Plano de Aula — Escola Presidente Bernardes
Execute:  python app.py   e acesse http://localhost:5000
"""
import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from io import BytesIO

from gerador import CONFIG_FILE, carregar_config, gerar_plano
from pdf import gerar_pdf
import db
import drive
import fuso
import referencias

db.init()

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

# ----------------------------------------------------------------------------
# Autenticação por usuário (e-mail institucional + senha)
# ----------------------------------------------------------------------------
import os, hmac  # noqa: E402
from flask import redirect, session, url_for, abort  # noqa: E402
import auth  # noqa: E402
import email_util  # noqa: E402


def _env(nome: str) -> str:
    """Lê variável de ambiente removendo espaços e aspas acidentais."""
    return os.getenv(nome, "").strip().strip('"').strip("'").strip()


DIRECAO_NOME = _env("DIRECAO_NOME")           # nome impresso no campo Direção
SUPERVISAO_NOME = _env("SUPERVISAO_NOME")     # nome padrão da supervisão
SUPERVISAO_SENHA = _env("SUPERVISAO_SENHA")   # senha de emergência da supervisão (opcional)
PUBLIC_URL = _env("PUBLIC_URL")

app.secret_key = os.getenv("SECRET_KEY") or (SUPERVISAO_SENHA + "-plano-bernardes-2026")
app.config.update(
    SESSION_COOKIE_NAME="planoaula_sessao",
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=bool(os.getenv("RENDER") or os.getenv("FORCE_HTTPS")),  # https no Render
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 14,  # 14 dias
)

from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

ROTAS_PUBLICAS = {"login", "primeiro_acesso", "definir_senha", "static", "sup_login", "healthz"}


def _base_url() -> str:
    base = PUBLIC_URL or request.url_root.rstrip("/")
    if base.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
        base = "https://" + base[len("http://"):]
    return base


def usuario_atual() -> dict | None:
    uid = session.get("uid")
    if not uid:
        return None
    u = db.usuario_por_id(uid)
    if not u or not u.get("ativo", 1):
        session.clear()
        return None
    return u


def _e_supervisao() -> bool:
    if session.get("sup"):
        return True
    u = usuario_atual()
    return bool(u and u.get("perfil") == "supervisao")


def _nome_professor() -> str:
    u = usuario_atual()
    return (u or {}).get("nome") or session.get("professor", "")


def _email_professor() -> str:
    u = usuario_atual()
    return (u or {}).get("email", "")


@app.before_request
def _exigir_login():
    if request.endpoint in ROTAS_PUBLICAS or (request.endpoint or "").startswith("static"):
        return None
    if usuario_atual() or session.get("sup"):
        return None
    if request.path.startswith("/api/"):
        return jsonify({"erro": "Sessão expirada. Entre novamente.", "login": True}), 401
    return redirect(url_for("login", next=request.path))


@app.route("/healthz")
def healthz():
    """Verificação pública (sem segredos): arquivos, banco e configuração básica."""
    import importlib, traceback as tb
    linhas = []
    base = Path(__file__).parent
    for f in ["auth.py", "email_util.py", "db.py", "drive.py", "gerador.py", "pdf.py",
              "templates/login.html", "templates/index.html", "templates/historico.html",
              "templates/conta.html", "templates/usuarios.html", "static/logo.png"]:
        linhas.append(f"{'OK ' if (base / f).exists() else 'FALTA'}  {f}")
    try:
        with db.conexao() as con:
            con.execute("SELECT 1")
        linhas.append(f"OK   banco de dados ({'PostgreSQL' if db.USA_PG else 'SQLite local'})")
        try:
            n = len(db.usuarios_listar())
            linhas.append(f"OK   tabela usuarios ({n} usuário(s))")
        except Exception as e:  # noqa: BLE001
            linhas.append(f"ERRO tabela usuarios: {type(e).__name__}: {str(e)[:160]}")
    except Exception as e:  # noqa: BLE001
        linhas.append(f"ERRO banco de dados: {type(e).__name__}: {str(e)[:160]}")
    linhas.append(f"{'OK ' if email_util.configurado() else 'AVISO'}  E-mail: {email_util.descricao() if email_util.configurado() else 'não configurado (links aparecerão na tela da supervisão)'}")
    linhas.append(f"{'OK ' if auth.SUPERVISAO_EMAILS else 'AVISO'}  SUPERVISAO_EMAILS {'definido' if auth.SUPERVISAO_EMAILS else 'vazio'}")
    linhas.append(f"{'OK ' if PUBLIC_URL else 'AVISO'}  PUBLIC_URL {'definido' if PUBLIC_URL else 'vazio (usará o endereço da requisição)'}")
    try:
        render_template("login.html", modo="login", erro="", dominio=auth.dominio_msg(), email="", ok="")
        linhas.append("OK   template login.html renderiza")
    except Exception as e:  # noqa: BLE001
        linhas.append(f"ERRO ao renderizar login.html: {type(e).__name__}: {str(e)[:160]}")
    status = 200 if not any(l.startswith("ERRO") or l.startswith("FALTA") for l in linhas) else 500
    return "<pre style='font:14px/1.6 monospace;padding:16px'>VERIFICAÇÃO DO SISTEMA\n\n" + "\n".join(linhas) + "</pre>", status


@app.errorhandler(500)
def _erro_500(e):
    import traceback
    tb = traceback.format_exc()
    app.logger.error("ERRO 500 em %s\n%s", request.path, tb)
    print("ERRO 500 em", request.path, "\n", tb, flush=True)
    ultima = [l for l in tb.strip().splitlines() if l.strip()][-1] if tb.strip() and tb.strip() != "NoneType: None" else str(e)
    return (f"<!doctype html><meta charset=utf-8><body style='font-family:Segoe UI,Arial;padding:28px;max-width:720px'>"
            f"<h2>Ocorreu um erro no servidor</h2>"
            f"<p style='background:#fdecec;border:1px solid #f3b4b4;padding:10px;border-radius:8px;font-family:monospace;font-size:13px'>{ultima}</p>"
            f"<p>Abra <a href='/healthz'>/healthz</a> para ver a verificação do sistema. O detalhe completo está no log do servidor.</p>"
            f"<p><a href='/login'>← Voltar</a></p>"), 500


@app.route("/login", methods=["GET", "POST"])
def login():
    erro = ""
    if request.method == "POST":
        try:
            u = auth.autenticar(request.form.get("email", ""), request.form.get("senha", ""))
            session.clear()
            session.permanent = bool(request.form.get("lembrar"))
            session["uid"] = u["id"]
            session["professor"] = u.get("nome") or ""
            destino = request.args.get("next") or "/"
            return redirect(destino if destino.startswith("/") else "/")
        except auth.AuthErro as e:
            erro = str(e)
    return render_template("login.html", modo="login", erro=erro, dominio=auth.dominio_msg(),
                           email=request.form.get("email", ""), ok="")


@app.route("/primeiro-acesso", methods=["GET", "POST"])
def primeiro_acesso():
    erro, ok, link_manual = "", "", ""
    if request.method == "POST":
        try:
            r = auth.solicitar_acesso(request.form.get("email", ""), _base_url())
            if r["enviado"]:
                ok = ("Enviamos um link para o seu e-mail. Abra a mensagem e clique em "
                      "<b>Criar minha senha</b>. Verifique também a pasta de spam.")
            else:
                erro = ("Não foi possível enviar o e-mail agora. Procure a supervisão para receber o link de acesso."
                        + (f" (Detalhe técnico: {r['erro']})" if _e_supervisao() else ""))
                if _e_supervisao():
                    link_manual = r["link"] or ""
        except auth.AuthErro as e:
            erro = str(e)
    return render_template("login.html", modo="primeiro", erro=erro, ok=ok, dominio=auth.dominio_msg(),
                           email=request.form.get("email", ""), link_manual=link_manual)


@app.route("/senha/<token>", methods=["GET", "POST"])
def definir_senha(token):
    erro, usuario = "", None
    try:
        t = auth.validar_token(token)
        usuario = db.usuario_por_id(t["usuario_id"])
    except auth.AuthErro as e:
        return render_template("login.html", modo="token_invalido", erro=str(e), dominio=auth.dominio_msg(), ok="")
    if request.method == "POST":
        s1, s2 = request.form.get("senha", ""), request.form.get("senha2", "")
        nome = request.form.get("nome", "").strip()
        if s1 != s2:
            erro = "As senhas não coincidem."
        elif not nome:
            erro = "Informe seu nome completo (ele aparece no plano de aula)."
        else:
            try:
                u = auth.definir_senha(token, s1, nome)
                session.clear()
                session.permanent = True
                session["uid"] = u["id"]
                session["professor"] = u.get("nome") or ""
                return redirect("/?bemvindo=1")
            except auth.AuthErro as e:
                erro = str(e)
    return render_template("login.html", modo="senha", erro=erro, ok="", usuario=usuario, token=token,
                           dominio=auth.dominio_msg(), nome=request.form.get("nome") or usuario.get("nome") or "")


@app.route("/supervisao/login", methods=["GET", "POST"])
def sup_login():
    """Acesso de emergência da supervisão por senha única (SUPERVISAO_SENHA). Opcional."""
    if not SUPERVISAO_SENHA:
        return redirect(url_for("login"))
    erro = ""
    if request.method == "POST":
        digitada = request.form.get("senha", "").strip().encode()
        if hmac.compare_digest(digitada, SUPERVISAO_SENHA.encode()):
            session.permanent = True
            session["sup"] = True
            session.setdefault("professor", SUPERVISAO_NOME or "Supervisão")
            return redirect("/historico")
        erro = "Senha incorreta."
    return render_template("login.html", modo="sup", erro=erro, ok="", dominio=auth.dominio_msg())


@app.route("/supervisao/sair")
def sup_sair():
    session.pop("sup", None)
    return redirect("/historico")


@app.route("/diagnostico")
def diagnostico():
    if not _e_supervisao():
        return "Apenas a supervisão pode ver o diagnóstico.", 403

    def info_senha(v: str) -> str:
        if not v:
            return "❌ NÃO definida"
        return f"✅ definida — {len(v)} caracteres, começa com «{v[0]}» e termina com «{v[-1]}»"
    cfg = carregar_config()
    linhas = {
        "Login por usuário": f"domínio {auth.dominio_msg()} · {len(db.usuarios_listar())} usuário(s) · {db.usuarios_total_supervisao()} supervisão",
        "E-mail": (f"✅ {email_util.descricao()}" if email_util.configurado()
                   else "❌ não configurado (BREVO_API_KEY + EMAIL_FROM) — links terão de ser repassados manualmente"),
        "SUPERVISAO_EMAILS": ", ".join(sorted(auth.SUPERVISAO_EMAILS)) or "— (nenhum; use SUPERVISAO_SENHA ou promova pela tela Usuários)",
        "SUPERVISAO_SENHA (emergência)": info_senha(SUPERVISAO_SENHA),
        "PUBLIC_URL": PUBLIC_URL or "⚠️ vazio (usará o endereço da requisição)",
        "SUPERVISAO_NOME": SUPERVISAO_NOME or "❌ vazio",
        "DIRECAO_NOME": DIRECAO_NOME or "❌ vazio",
        "DATABASE_URL": "✅ PostgreSQL" if db.USA_PG else "⚠️ não definida (usando SQLite local — histórico some a cada deploy no Render)",
        "IA": f"{cfg['provider']} · {cfg['model']} · chave {'✅' if cfg['api_key'] else '❌'}",
        "Google Drive": ("✅ conectado como " + drive.status()["conta"]) if drive.conectado()
                        else ("⚠️ credenciais OK, falta conectar (Configurações)" if drive.credenciais_ok()
                              else "— não configurado (opcional)"),
        "Horário do sistema": f"{fuso.agora().strftime('%d/%m/%Y %H:%M')} ({fuso.FUSO.key}) · UTC do servidor: {__import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%H:%M')}",
        "Sessão atual": f"usuário: {_email_professor() or '—'} · supervisão: {'sim' if _e_supervisao() else 'não'}",
    }
    html = "".join(f"<tr><td style='padding:6px 12px;font-weight:600'>{k}</td><td style='padding:6px 12px'>{v}</td></tr>" for k, v in linhas.items())
    return (f"<!doctype html><meta charset=utf-8><title>Diagnóstico</title>"
            f"<body style='font-family:Segoe UI,Arial;padding:24px'><h2>Diagnóstico do servidor</h2>"
            f"<table style='border-collapse:collapse;background:#f6f6f8;border-radius:8px'>{html}</table>"
            f"<p><a href='/healthz'>Verificação de arquivos e banco</a> · <a href='/'>← voltar</a></p>")


@app.route("/sair")
def sair():
    session.clear()
    return redirect(url_for("login"))


@app.route("/conta", methods=["GET", "POST"])
def conta():
    u = usuario_atual()
    if not u:
        return redirect(url_for("login"))
    erro = ok = ""
    if request.method == "POST":
        try:
            if request.form.get("acao") == "nome":
                nome = request.form.get("nome", "").strip()
                if len(nome) < 3:
                    raise auth.AuthErro("Informe seu nome completo.")
                db.usuario_atualizar(u["id"], nome=nome)
                session["professor"] = nome
                ok = "Nome atualizado."
            else:
                auth.trocar_senha(u["id"], request.form.get("atual", ""), request.form.get("nova", ""))
                ok = "Senha alterada com sucesso."
        except auth.AuthErro as e:
            erro = str(e)
        u = usuario_atual()
    return render_template("conta.html", u=u, erro=erro, ok=ok, e_supervisao=_e_supervisao())


# Componentes curriculares conforme as matrizes 2026 da escola (Integral Profissional)
DISCIPLINAS_GRUPOS = {
    "Formação Geral Básica": [
        "Língua Portuguesa", "Língua Inglesa", "Arte", "Educação Física", "Matemática",
        "Física", "Química", "Biologia", "História", "Geografia", "Filosofia", "Sociologia",
    ],
    "Parte Diversificada / Escola da Escolha": [
        "Projeto de Vida", "Eletiva", "Estudos Orientados", "Práticas Experimentais",
        "Nivelamento – Língua Portuguesa", "Nivelamento – Matemática",
        "Cultura Digital e Fundamentos de IA", "Ferramentas para o Mundo do Trabalho",
        "Projetos Integradores e de Corresponsabilidade Social (PICS)",
        "Práticas de Leitura e Escrita",
    ],
    "Técnico – Automação Industrial (2º ano)": ["Automação Industrial III", "Automação Industrial IV"],
    "Técnico – Mecatrônica (2º ano)": ["Mecatrônica III", "Mecatrônica IV"],
    "Técnico – Desenvolvimento de Sistemas (3º ano)": [
        "Conceitos Avançados em Arquitetura de Sistemas", "Desenvolvimento Back-end",
        "Desenvolvimento de Aplicativos", "Desenvolvimento de Softwares", "Desenvolvimento Front-end II",
        "Fundamentos de Segurança de Softwares", "Prática Profissional e Empreendedora",
    ],
}
DISCIPLINAS = [d for grupo in DISCIPLINAS_GRUPOS.values() for d in grupo]
SERIES = ["1º ano", "2º ano", "3º ano"]


def _slug(t: str) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()


def _formatar_data(iso: str) -> str:
    """'2026-09-14' -> '14/09/2026'. Aceita também texto livre (ex.: '14 a 18/09/2026')."""
    try:
        y, m, d = iso.split("-")
        return f"{d}/{m}/{y}"
    except Exception:
        return iso


@app.route("/")
def index():
    cfg = carregar_config()
    return render_template(
        "index.html",
        disciplinas=DISCIPLINAS,
        disciplinas_grupos=DISCIPLINAS_GRUPOS,
        series=SERIES,
        hoje=fuso.hoje().isoformat(),
        ia_configurada=bool(cfg["api_key"]),
        provider=cfg["provider"],
        model=cfg["model"],
        supervisao_nome=SUPERVISAO_NOME,
        direcao_nome=DIRECAO_NOME,
        e_supervisao=_e_supervisao(),
        drive_conectado=drive.conectado(),
        usuario=usuario_atual() or {"nome": session.get("professor", ""), "email": ""},
        fontes=referencias.FONTES,
        documentos=db.documentos_listar(somente_ativos=True),
    )


@app.route("/api/gerar", methods=["POST"])
def api_gerar():
    dados = request.get_json(force=True) or {}
    u = usuario_atual()
    if u:
        dados["professor"] = u.get("nome") or dados.get("professor", "")
        dados["professor_email"] = u.get("email", "")
    obrig = ["professor", "disciplina", "conteudo", "data", "serie"]
    faltando = [c for c in obrig if not str(dados.get(c, "")).strip()]
    if faltando:
        return jsonify({"erro": f"Preencha: {', '.join(faltando)}"}), 400

    dados["data"] = _formatar_data(dados["data"])
    if dados.get("data_fim"):
        dados["data"] = f"{dados['data']} a {_formatar_data(dados['data_fim'])}"
    fontes_sel = dados.get("fontes") or ["bncc", "crmg", "ice"]
    if isinstance(fontes_sel, str):
        fontes_sel = [f for f in fontes_sel.split(",") if f]
    doc_ids = [int(x) for x in (dados.get("documentos") or []) if str(x).isdigit()]
    consulta = f"{dados.get('conteudo','')} {dados.get('disciplina','')}"
    try:
        contexto, citacoes = referencias.montar_contexto(fontes_sel, doc_ids, consulta)
    except Exception:  # noqa: BLE001
        contexto, citacoes = "", []
    try:
        plano = gerar_plano(dados, contexto=contexto, citacoes=citacoes)
    except Exception as e:  # noqa: BLE001
        msg = re.sub(r"[?&]key=[^&\s)\]]+", "?key=***", str(e))  # nunca expor a chave
        return jsonify({"erro": f"Falha ao consultar a IA: {msg}"}), 502
    dados.setdefault("direcao", DIRECAO_NOME)
    if not dados.get("supervisao"):
        dados["supervisao"] = SUPERVISAO_NOME
    session["professor"] = dados["professor"].strip()
    id_ = db.inserir(dados, plano)
    return jsonify({"id": id_, "dados": dados, "plano": plano})


@app.route("/api/pdf", methods=["POST"])
def api_pdf():
    body = request.get_json(force=True) or {}
    dados, plano = body.get("dados", {}), body.get("plano", {})
    plano = {k: v for k, v in plano.items() if not k.startswith("_")}
    visto = None
    if body.get("id"):
        item = db.obter(int(body["id"]))
        if item and item.get("visto_em"):
            # plano já visado pela supervisão: vale a versão gravada (não aceita edições)
            dados, plano, visto = item["dados"], item["plano"], _visto_de(item)
        else:
            try:
                db.atualizar(int(body["id"]), dados, plano)   # guarda as edições feitas na tela
            except Exception:
                pass
    pdf = gerar_pdf(dados, plano, visto)
    nome = f"plano-de-aula-{_slug(dados.get('disciplina','')) or 'x'}-{_slug(dados.get('serie',''))}-{_slug(dados.get('data',''))}-{_slug(dados.get('professor',''))}.pdf"
    resp = send_file(BytesIO(pdf), mimetype="application/pdf", as_attachment=True, download_name=nome)
    # envio automático ao Drive (silencioso: nunca impede o download)
    if body.get("id") and drive.conectado() and drive.status()["auto"]:
        try:
            info = _enviar_drive(int(body["id"]), dados, plano, pdf)
            resp.headers["X-Drive-Link"] = info["link"]
        except Exception as e:  # noqa: BLE001
            resp.headers["X-Drive-Erro"] = str(e)[:150]
    return resp


def _enviar_drive(id_: int, dados: dict, plano: dict, pdf: bytes | None = None) -> dict:
    item = db.obter(id_) or {}
    pdf = pdf or gerar_pdf(dados, plano)
    d = dict(dados); d["_tema"] = plano.get("tema", "")
    info = drive.enviar_pdf(pdf, d, file_id_existente=item.get("drive_file_id"))
    db.set_drive(id_, info["id"], info["link"])
    return info


# ----------------------------------------------------------------------------
# Histórico
# ----------------------------------------------------------------------------
def _visto_de(item: dict) -> dict | None:
    if not item or not item.get("visto_em"):
        return None
    return {"em": item["visto_em"], "por": item.get("visto_por") or "", "codigo": item.get("visto_codigo") or ""}


def _codigo_visto(id_: int, quando: str) -> str:
    """Código curto de verificação (impresso no carimbo), derivado do plano + data/hora + chave secreta."""
    h = hashlib.sha256(f"{id_}|{quando}|{app.secret_key}".encode()).hexdigest().upper()
    return f"{h[:4]}-{h[4:8]}"


def _pode_ver(item: dict) -> bool:
    if _e_supervisao():
        return True
    em = _email_professor()
    if em and item.get("dados", {}).get("professor_email"):
        return item["dados"]["professor_email"].lower() == em.lower()
    return item.get("professor", "").lower() == _nome_professor().lower()


@app.route("/historico")
def historico():
    sup = _e_supervisao()
    return render_template(
        "historico.html",
        e_supervisao=sup,
        tem_senha_sup=bool(SUPERVISAO_SENHA),
        usuario=usuario_atual(),
        professor_atual=_nome_professor(),
        professores=db.professores() if sup else [],
        disciplinas=DISCIPLINAS, series=SERIES,
    )


@app.route("/api/historico")
def api_historico():
    sup = _e_supervisao()
    prof = request.args.get("professor", "").strip()
    if sup:
        itens = db.listar(professor=prof or None, disciplina=request.args.get("disciplina", ""),
                          serie=request.args.get("serie", ""), busca=request.args.get("busca", ""))
    else:
        itens = db.listar(professor=_nome_professor(), professor_email=_email_professor() or None,
                          disciplina=request.args.get("disciplina", ""),
                          serie=request.args.get("serie", ""), busca=request.args.get("busca", ""))
    return jsonify(itens)


@app.route("/api/historico/<int:id_>")
def api_historico_item(id_):
    item = db.obter(id_)
    if not item:
        return jsonify({"erro": "não encontrado"}), 404
    if not _pode_ver(item):
        return jsonify({"erro": "sem permissão"}), 403
    return jsonify(item)


@app.route("/api/historico/<int:id_>/pdf")
def api_historico_pdf(id_):
    item = db.obter(id_)
    if not item:
        return "não encontrado", 404
    if not _pode_ver(item):
        return "sem permissão", 403
    pdf = gerar_pdf(item["dados"], item["plano"], _visto_de(item))
    d = item["dados"]
    nome = f"plano-{_slug(d.get('disciplina',''))}-{_slug(d.get('serie',''))}-{_slug(d.get('data',''))}-{_slug(d.get('professor',''))}.pdf"
    return send_file(BytesIO(pdf), mimetype="application/pdf", as_attachment=True, download_name=nome)


@app.route("/api/historico/<int:id_>", methods=["DELETE"])
def api_historico_excluir(id_):
    item = db.obter(id_)
    if not item:
        return jsonify({"erro": "não encontrado"}), 404
    if not _pode_ver(item):
        return jsonify({"erro": "sem permissão"}), 403
    db.excluir(id_)
    return jsonify({"ok": True})


@app.route("/api/historico/<int:id_>/visto", methods=["POST"])
def api_historico_visto(id_):
    """Visto eletrônico da supervisão: grava nome, e-mail, data/hora e código; avisa o professor por e-mail."""
    if not _e_supervisao():
        return jsonify({"erro": "sem permissão"}), 403
    item = db.obter(id_)
    if not item:
        return jsonify({"erro": "não encontrado"}), 404
    body = request.get_json(silent=True) or {}
    if body.get("desfazer"):
        db.marcar_visto(id_, "", desfazer=True)
        return jsonify({"ok": True})
    u = usuario_atual() or {}
    por = (u.get("nome") or "").strip() or SUPERVISAO_NOME or "Supervisão Pedagógica"
    quando = fuso.agora_txt()
    codigo = _codigo_visto(id_, quando)
    with db.conexao() as con:
        con.execute(db._q("UPDATE planos SET visto_em=?, visto_por=?, visto_email=?, visto_codigo=? WHERE id=?"),
                    (quando, por, u.get("email") or None, codigo, id_))
    # supervisão em branco no plano? preenche com quem assinou
    if not (item["dados"].get("supervisao") or "").strip():
        item["dados"]["supervisao"] = por
        db.atualizar(id_, item["dados"], item["plano"])
    aviso = ""
    dest = (item.get("professor_email") or item["dados"].get("professor_email") or "").strip()
    if dest and email_util.configurado():
        try:
            d = item["dados"]
            link = _base_url() + f"/?id={id_}"
            dt = datetime.strptime(quando[:19], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y às %H:%M")
            txt = (f"Olá, {d.get('professor','')}!\n\nSeu plano de aula de {d.get('disciplina','')} ({d.get('serie','')}), "
                   f"semana {d.get('data','')}, tema \"{item['plano'].get('tema','')}\", recebeu o visto eletrônico da supervisão.\n\n"
                   f"Visto por: {por}\nEm: {dt}\nCódigo: {codigo}\n\n"
                   f"Baixe a versão assinada em: {link}\n\n"
                   "Observação: após o visto o plano fica travado para edição. Se precisar alterar, peça à supervisão para desfazer o visto.\n\n"
                   "Escola Estadual Presidente Bernardes — Assistente de Plano de Aula")
            html = email_util.template_simples("Plano de aula visado ✔", d.get("professor", ""),
                                               f"Seu plano de <b>{d.get('disciplina','')}</b> ({d.get('serie','')}), semana {d.get('data','')}, "
                                               f"tema <i>{item['plano'].get('tema','')}</i>, recebeu o <b>visto eletrônico da supervisão</b>.<br><br>"
                                               f"Visto por: <b>{por}</b><br>Em: {dt}<br>Código: {codigo}",
                                               link, "Abrir plano assinado")
            email_util.enviar(dest, f"Plano de aula visado – {d.get('disciplina','')} – {d.get('data','')}", txt, html)
        except Exception as e:  # noqa: BLE001
            aviso = f"Visto registrado, mas o e-mail ao professor falhou: {e}"
    elif not dest:
        aviso = "Visto registrado. O professor não tem e-mail cadastrado neste plano, então não foi avisado."
    return jsonify({"ok": True, "visto_em": quando, "visto_por": por, "codigo": codigo, "aviso": aviso})


# ----------------------------------------------------------------------------
# Google Drive
# ----------------------------------------------------------------------------
def _redirect_uri() -> str:
    base = os.getenv("PUBLIC_URL", "").strip().rstrip("/") or request.url_root.rstrip("/")
    if base.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
        base = "https://" + base[len("http://"):]
    return base + "/drive/callback"


@app.route("/api/drive/status")
def api_drive_status():
    st = drive.status()
    st["redirect_uri"] = _redirect_uri()
    return jsonify(st)


@app.route("/drive/conectar")
def drive_conectar():
    if not _e_supervisao():
        return redirect(url_for("sup_login"))
    if not drive.credenciais_ok():
        return "Defina GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET no servidor.", 400
    state = os.urandom(12).hex()
    session["drive_state"] = state
    return redirect(drive.url_autorizacao(_redirect_uri(), state))


@app.route("/drive/callback")
def drive_callback():
    if request.args.get("error"):
        return redirect("/?drive=erro&msg=" + request.args["error"])
    if request.args.get("state") != session.get("drive_state"):
        return "Estado inválido. Tente conectar novamente.", 400
    try:
        drive.trocar_codigo(request.args.get("code", ""), _redirect_uri())
        drive.pasta_raiz()
    except Exception as e:  # noqa: BLE001
        return f"Falha ao conectar ao Google Drive: {e}", 500
    return redirect("/?drive=ok")


@app.route("/api/drive/desconectar", methods=["POST"])
def api_drive_desconectar():
    if not _e_supervisao():
        return jsonify({"erro": "sem permissão"}), 403
    drive.desconectar()
    return jsonify({"ok": True})


@app.route("/api/drive/config", methods=["POST"])
def api_drive_config():
    if not _e_supervisao():
        return jsonify({"erro": "sem permissão"}), 403
    body = request.get_json(force=True) or {}
    try:
        if "auto" in body:
            db.config_set("drive_auto", "1" if body["auto"] else "0")
        if body.get("pasta") is not None and drive.conectado():
            drive.definir_pasta_raiz(body["pasta"])
    except Exception as e:  # noqa: BLE001
        return jsonify({"erro": str(e)}), 400
    return jsonify(drive.status())


@app.route("/api/historico/<int:id_>/drive", methods=["POST"])
def api_historico_drive(id_):
    """Envia (ou reenvia) um plano do histórico para o Drive."""
    item = db.obter(id_)
    if not item:
        return jsonify({"erro": "não encontrado"}), 404
    if not _pode_ver(item):
        return jsonify({"erro": "sem permissão"}), 403
    if not drive.conectado():
        return jsonify({"erro": "Google Drive não conectado. Peça à supervisão para conectar em Configurações."}), 400
    try:
        info = _enviar_drive(id_, item["dados"], item["plano"])
    except Exception as e:  # noqa: BLE001
        return jsonify({"erro": f"Falha ao enviar ao Drive: {e}"}), 502
    return jsonify(info)


# ----------------------------------------------------------------------------
# Usuários (supervisão)
# ----------------------------------------------------------------------------
@app.route("/usuarios")
def usuarios():
    if not _e_supervisao():
        return redirect(url_for("login"))
    return render_template("usuarios.html", e_supervisao=True, usuario=usuario_atual(),
                           dominio=auth.dominio_msg(), email_ok=email_util.configurado())


@app.route("/api/usuarios")
def api_usuarios():
    if not _e_supervisao():
        return jsonify({"erro": "sem permissão"}), 403
    return jsonify(db.usuarios_listar())


@app.route("/api/usuarios", methods=["POST"])
def api_usuarios_criar():
    """Cadastra (um ou vários) e-mails e envia o link de criação de senha."""
    if not _e_supervisao():
        return jsonify({"erro": "sem permissão"}), 403
    body = request.get_json(force=True) or {}
    brutos = body.get("emails") or [body.get("email", "")]
    if isinstance(brutos, str):
        brutos = re.split(r"[\s,;]+", brutos)
    perfil = "supervisao" if body.get("perfil") == "supervisao" else "professor"
    enviar = body.get("enviar", True)
    resultados = []
    for e in brutos:
        e = auth.normalizar_email(e)
        if not e:
            continue
        if not auth.email_valido(e):
            resultados.append({"email": e, "status": "erro", "msg": f"fora do domínio {auth.dominio_msg()}"}); continue
        u = db.usuario_por_email(e)
        if not u:
            u = db.usuario_criar(e, body.get("nome", "") or auth.nome_do_email(e), perfil)
        elif perfil == "supervisao" and u["perfil"] != "supervisao":
            db.usuario_atualizar(u["id"], perfil="supervisao")
        if enviar:
            r = auth.solicitar_acesso(e, _base_url())
            resultados.append({"email": e, "status": "enviado" if r["enviado"] else "link",
                               "msg": "e-mail enviado" if r["enviado"] else (r["erro"] or ""), "link": r["link"]})
        else:
            resultados.append({"email": e, "status": "cadastrado", "msg": "cadastrado sem envio"})
    return jsonify(resultados)


@app.route("/api/usuarios/<int:id_>", methods=["PATCH"])
def api_usuarios_editar(id_):
    if not _e_supervisao():
        return jsonify({"erro": "sem permissão"}), 403
    body = request.get_json(force=True) or {}
    u = db.usuario_por_id(id_)
    if not u:
        return jsonify({"erro": "não encontrado"}), 404
    campos = {}
    if "nome" in body:
        campos["nome"] = body["nome"].strip()
    if "perfil" in body and body["perfil"] in ("professor", "supervisao"):
        campos["perfil"] = body["perfil"]
    if "ativo" in body:
        campos["ativo"] = 1 if body["ativo"] else 0
    # impede remover a última supervisão
    if (campos.get("perfil") == "professor" or campos.get("ativo") == 0) and u["perfil"] == "supervisao" \
            and db.usuarios_total_supervisao() <= 1 and not SUPERVISAO_SENHA:
        return jsonify({"erro": "Não é possível remover a última conta de supervisão."}), 400
    db.usuario_atualizar(id_, **campos)
    return jsonify({"ok": True})


@app.route("/api/usuarios/<int:id_>", methods=["DELETE"])
def api_usuarios_excluir(id_):
    if not _e_supervisao():
        return jsonify({"erro": "sem permissão"}), 403
    u = db.usuario_por_id(id_)
    if not u:
        return jsonify({"erro": "não encontrado"}), 404
    if u["perfil"] == "supervisao" and db.usuarios_total_supervisao() <= 1 and not SUPERVISAO_SENHA:
        return jsonify({"erro": "Não é possível excluir a última conta de supervisão."}), 400
    db.usuario_excluir(id_)
    return jsonify({"ok": True})


@app.route("/api/email/teste", methods=["POST"])
def api_email_teste():
    if not _e_supervisao():
        return jsonify({"erro": "sem permissão"}), 403
    dest = (request.get_json(silent=True) or {}).get("para") or _email_professor()
    if not dest:
        return jsonify({"erro": "Informe o destinatário."}), 400
    try:
        email_util.enviar(dest, "Teste — Assistente de Plano de Aula",
                          "Este é um e-mail de teste. Se você o recebeu, o envio está funcionando.")
    except Exception as e:  # noqa: BLE001
        return jsonify({"erro": str(e)}), 502
    return jsonify({"ok": True, "modo": email_util.descricao()})


@app.route("/api/usuarios/<int:id_>/reenviar", methods=["POST"])
def api_usuarios_reenviar(id_):
    if not _e_supervisao():
        return jsonify({"erro": "sem permissão"}), 403
    u = db.usuario_por_id(id_)
    if not u:
        return jsonify({"erro": "não encontrado"}), 404
    r = auth.solicitar_acesso(u["email"], _base_url())
    return jsonify(r)


# ----------------------------------------------------------------------------
# Biblioteca de referências (documentos do ICE etc.)
# ----------------------------------------------------------------------------
@app.route("/biblioteca")
def biblioteca():
    return render_template("biblioteca.html", e_supervisao=_e_supervisao(), usuario=usuario_atual(),
                           fontes=referencias.FONTES)


@app.route("/api/documentos")
def api_documentos():
    return jsonify(db.documentos_listar(somente_ativos=not _e_supervisao()))


@app.route("/api/documentos", methods=["POST"])
def api_documentos_criar():
    if not _e_supervisao():
        return jsonify({"erro": "Apenas a supervisão pode enviar documentos."}), 403
    f = request.files.get("arquivo")
    if not f or not f.filename:
        return jsonify({"erro": "Selecione um arquivo PDF, DOCX ou TXT."}), 400
    nome = f.filename
    if not nome.lower().endswith((".pdf", ".docx", ".txt", ".md")):
        return jsonify({"erro": "Formato não suportado. Use PDF, DOCX ou TXT."}), 400
    conteudo = f.read()
    if len(conteudo) > 40 * 1024 * 1024:
        return jsonify({"erro": "Arquivo acima de 40 MB."}), 400
    try:
        texto = referencias.extrair_texto(nome, conteudo)
    except Exception as e:  # noqa: BLE001
        return jsonify({"erro": f"Não foi possível ler o arquivo: {e}"}), 400
    trechos = referencias.dividir_em_trechos(texto)
    if not trechos:
        return jsonify({"erro": "O arquivo não contém texto legível (pode ser um PDF só de imagens/escaneado)."}), 400
    titulo = request.form.get("titulo", "").strip() or re.sub(r"\.[^.]+$", "", nome)
    citacao = request.form.get("citacao", "").strip() or f"{titulo}."
    categoria = request.form.get("categoria", "ICE").strip() or "ICE"
    did = db.documento_criar(titulo, citacao, categoria, nome, len(conteudo), trechos)
    return jsonify({"ok": True, "id": did, "n_trechos": len(trechos)})


@app.route("/api/documentos/<int:id_>", methods=["PATCH"])
def api_documentos_editar(id_):
    if not _e_supervisao():
        return jsonify({"erro": "sem permissão"}), 403
    body = request.get_json(force=True) or {}
    campos = {k: body[k] for k in ("titulo", "citacao", "categoria") if k in body}
    if "ativo" in body:
        campos["ativo"] = 1 if body["ativo"] else 0
    db.documento_atualizar(id_, **campos)
    return jsonify({"ok": True})


@app.route("/api/documentos/<int:id_>", methods=["DELETE"])
def api_documentos_excluir(id_):
    if not _e_supervisao():
        return jsonify({"erro": "sem permissão"}), 403
    db.documento_excluir(id_)
    return jsonify({"ok": True})


@app.route("/api/documentos/buscar")
def api_documentos_buscar():
    """Pré-visualização: quais trechos seriam usados para um tema."""
    q = request.args.get("q", "")
    ids = [int(x) for x in request.args.get("ids", "").split(",") if x.isdigit()]
    trechos = referencias.buscar_trechos(q, ids or None, limite=5)
    return jsonify([{"titulo": t["titulo"], "texto": t["texto"][:400]} for t in trechos])


@app.route("/api/sessao/professor", methods=["POST"])
def api_sessao_professor():
    nome = (request.get_json(silent=True) or {}).get("professor", "").strip()
    session["professor"] = nome
    return jsonify({"ok": True})


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "POST" and not _e_supervisao():
        return jsonify({"erro": "Apenas a supervisão pode alterar as configurações."}), 403
    if request.method == "GET":
        cfg = carregar_config()
        return jsonify({
            "provider": cfg["provider"], "model": cfg["model"], "base_url": cfg["base_url"],
            "api_key_mascarada": (cfg["api_key"][:4] + "•••" + cfg["api_key"][-4:]) if cfg["api_key"] else "",
            "configurada": bool(cfg["api_key"]),
        })
    novo = request.get_json(force=True) or {}
    atual = {}
    if CONFIG_FILE.exists():
        try:
            atual = json.loads(CONFIG_FILE.read_text("utf-8"))
        except Exception:
            atual = {}
    for k in ("provider", "model", "base_url"):
        if k in novo:
            atual[k] = novo[k].strip()
    if novo.get("api_key", "").strip():
        atual["api_key"] = novo["api_key"].strip()
    if novo.get("limpar_chave"):
        atual["api_key"] = ""
    CONFIG_FILE.write_text(json.dumps(atual, ensure_ascii=False, indent=2), "utf-8")
    return jsonify({"ok": True, "configurada": bool(atual.get("api_key"))})


if __name__ == "__main__":
    porta = int(os.getenv("PORT", "5000"))
    print(f"Assistente de Plano de Aula rodando em http://localhost:{porta}")
    app.run(host="0.0.0.0", port=porta, debug=False)
