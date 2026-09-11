"""
Gerador Automático de Plano de Aula — Escola Presidente Bernardes
Execute:  python app.py   e acesse http://localhost:5000
"""
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from io import BytesIO

from gerador import CONFIG_FILE, carregar_config, gerar_plano
from pdf import gerar_pdf
import db

db.init()

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

# ----------------------------------------------------------------------------
# Senha de acesso (opcional). Defina a variável de ambiente APP_SENHA para
# exigir uma senha única compartilhada com os professores.
# ----------------------------------------------------------------------------
import os, hmac  # noqa: E402
from flask import redirect, session, url_for  # noqa: E402

def _env(nome: str) -> str:
    """Lê variável de ambiente removendo espaços e aspas acidentais."""
    return os.getenv(nome, "").strip().strip('"').strip("'").strip()


def _senha_confere(digitada: str, correta: str) -> bool:
    if not correta:
        return False
    return hmac.compare_digest(digitada.strip().encode("utf-8"), correta.encode("utf-8"))


APP_SENHA = _env("APP_SENHA")
SUPERVISAO_SENHA = _env("SUPERVISAO_SENHA")   # libera a área da supervisão
DIRECAO_NOME = _env("DIRECAO_NOME")           # nome impresso no campo Direção
SUPERVISAO_NOME = _env("SUPERVISAO_NOME")     # nome padrão da supervisão
app.secret_key = os.getenv("SECRET_KEY") or (APP_SENHA + "-plano-bernardes") or os.urandom(24)

LOGIN_HTML = """<!doctype html><html lang=pt-BR><meta charset=utf-8><title>Acesso — Plano de Aula</title>
<style>body{font-family:Segoe UI,Arial,sans-serif;background:#f4f4f5;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.c{background:#fff;border:1px solid #d9d9de;border-radius:12px;padding:28px;width:min(360px,92vw);text-align:center}
img{height:50px;margin-bottom:10px}input{width:100%;padding:10px;border:1px solid #d9d9de;border-radius:6px;font-size:15px;margin:12px 0;box-sizing:border-box}
button{width:100%;padding:11px;background:#111;color:#fff;border:none;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer}
.e{color:#a00;font-size:13px}</style>
<div class=c><img src="/static/logo.png"><h3 style="margin:6px 0">Gerador de Plano de Aula</h3>
<p style="font-size:13px;color:#666">Informe a senha de acesso dos professores.</p>
<form method=post><input type=password name=senha placeholder="Senha" autofocus>
{erro}<button>Entrar</button></form></div>"""


@app.before_request
def _exigir_senha():
    if not APP_SENHA:
        return None
    if request.endpoint in ("login", "static") or session.get("ok"):
        return None
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    erro = ""
    if request.method == "POST":
        if _senha_confere(request.form.get("senha", ""), APP_SENHA):
            session["ok"] = True
            return redirect("/")
        erro = "<p class=e>Senha incorreta.</p>"
    return LOGIN_HTML.replace("{erro}", erro)


def _e_supervisao() -> bool:
    return bool(session.get("sup")) or not SUPERVISAO_SENHA


@app.route("/supervisao/login", methods=["GET", "POST"])
def sup_login():
    erro = ""
    if request.method == "POST":
        if _senha_confere(request.form.get("senha", ""), SUPERVISAO_SENHA):
            session["sup"] = True
            return redirect("/historico")
        erro = "<p class=e>Senha incorreta.</p>"
    if not SUPERVISAO_SENHA:
        erro = ("<p class=e>A variável SUPERVISAO_SENHA não está definida no servidor. "
                "Crie-a em Render → Environment e aguarde o redeploy.</p>")
    html = LOGIN_HTML.replace("Informe a senha de acesso dos professores.", "Área da supervisão — informe a senha da supervisão.")
    return html.replace("{erro}", erro)


@app.route("/supervisao/sair")
def sup_sair():
    session.pop("sup", None)
    return redirect("/historico")


@app.route("/diagnostico")
def diagnostico():
    def info_senha(v: str) -> str:
        if not v:
            return "❌ NÃO definida"
        return f"✅ definida — {len(v)} caracteres, começa com «{v[0]}» e termina com «{v[-1]}»"
    cfg = carregar_config()
    linhas = {
        "APP_SENHA (professores)": info_senha(APP_SENHA),
        "SUPERVISAO_SENHA": info_senha(SUPERVISAO_SENHA),
        "SUPERVISAO_NOME": SUPERVISAO_NOME or "❌ vazio",
        "DIRECAO_NOME": DIRECAO_NOME or "❌ vazio",
        "DATABASE_URL": "✅ PostgreSQL" if db.USA_PG else "⚠️ não definida (usando SQLite local — histórico some a cada deploy no Render)",
        "IA": f"{cfg['provider']} · {cfg['model']} · chave {'✅' if cfg['api_key'] else '❌'}",
        "Sessão atual": f"professor logado: {'sim' if session.get('ok') or not APP_SENHA else 'não'} · supervisão: {'sim' if session.get('sup') else 'não'}",
    }
    html = "".join(f"<tr><td style='padding:6px 12px;font-weight:600'>{k}</td><td style='padding:6px 12px'>{v}</td></tr>" for k, v in linhas.items())
    return (f"<!doctype html><meta charset=utf-8><title>Diagnóstico</title>"
            f"<body style='font-family:Segoe UI,Arial;padding:24px'><h2>Diagnóstico do servidor</h2>"
            f"<table style='border-collapse:collapse;background:#f6f6f8;border-radius:8px'>{html}</table>"
            f"<p style='color:#666;font-size:13px'>Se uma senha aparece com tamanho diferente do esperado, "
            f"verifique espaços ou aspas no valor da variável no Render.</p><p><a href='/'>← voltar</a></p>")


@app.route("/sair")
def sair():
    session.clear()
    return redirect(url_for("login"))

DISCIPLINAS = [
    "Língua Portuguesa", "Literatura", "Redação", "Língua Inglesa", "Língua Espanhola", "Arte",
    "Educação Física", "Matemática", "Física", "Química", "Biologia",
    "História", "Geografia", "Filosofia", "Sociologia",
    "Projeto de Vida", "Eletiva", "Estudo Orientado", "Tecnologia e Inovação",
]
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
        series=SERIES,
        hoje=date.today().isoformat(),
        ia_configurada=bool(cfg["api_key"]),
        provider=cfg["provider"],
        model=cfg["model"],
        supervisao_nome=SUPERVISAO_NOME,
        direcao_nome=DIRECAO_NOME,
        e_supervisao=_e_supervisao(),
    )


@app.route("/api/gerar", methods=["POST"])
def api_gerar():
    dados = request.get_json(force=True) or {}
    obrig = ["professor", "disciplina", "conteudo", "data", "serie"]
    faltando = [c for c in obrig if not str(dados.get(c, "")).strip()]
    if faltando:
        return jsonify({"erro": f"Preencha: {', '.join(faltando)}"}), 400

    dados["data"] = _formatar_data(dados["data"])
    if dados.get("data_fim"):
        dados["data"] = f"{dados['data']} a {_formatar_data(dados['data_fim'])}"
    try:
        plano = gerar_plano(dados)
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
    if body.get("id"):
        try:
            db.atualizar(int(body["id"]), dados, plano)   # guarda as edições feitas na tela
        except Exception:
            pass
    pdf = gerar_pdf(dados, plano)
    nome = f"plano-de-aula-{_slug(dados.get('disciplina','')) or 'x'}-{_slug(dados.get('serie',''))}-{_slug(dados.get('data',''))}.pdf"
    return send_file(BytesIO(pdf), mimetype="application/pdf", as_attachment=True, download_name=nome)


# ----------------------------------------------------------------------------
# Histórico
# ----------------------------------------------------------------------------
@app.route("/historico")
def historico():
    sup = _e_supervisao()
    return render_template(
        "historico.html",
        e_supervisao=sup,
        tem_senha_sup=bool(SUPERVISAO_SENHA),
        professor_atual=session.get("professor", ""),
        professores=db.professores() if sup else [],
        disciplinas=DISCIPLINAS, series=SERIES,
    )


@app.route("/api/historico")
def api_historico():
    sup = _e_supervisao()
    prof = request.args.get("professor", "").strip()
    if not sup:
        # professor comum: só vê os seus (nome informado na sessão ou no filtro)
        prof = prof or session.get("professor", "")
        if not prof:
            return jsonify([])
    itens = db.listar(professor=prof or None, disciplina=request.args.get("disciplina", ""),
                      serie=request.args.get("serie", ""), busca=request.args.get("busca", ""))
    return jsonify(itens)


@app.route("/api/historico/<int:id_>")
def api_historico_item(id_):
    item = db.obter(id_)
    if not item:
        return jsonify({"erro": "não encontrado"}), 404
    if not _e_supervisao() and item["professor"].lower() != session.get("professor", "").lower():
        return jsonify({"erro": "sem permissão"}), 403
    return jsonify(item)


@app.route("/api/historico/<int:id_>/pdf")
def api_historico_pdf(id_):
    item = db.obter(id_)
    if not item:
        return "não encontrado", 404
    if not _e_supervisao() and item["professor"].lower() != session.get("professor", "").lower():
        return "sem permissão", 403
    pdf = gerar_pdf(item["dados"], item["plano"])
    d = item["dados"]
    nome = f"plano-{_slug(d.get('disciplina',''))}-{_slug(d.get('serie',''))}-{_slug(d.get('data',''))}-{_slug(d.get('professor',''))}.pdf"
    return send_file(BytesIO(pdf), mimetype="application/pdf", as_attachment=True, download_name=nome)


@app.route("/api/historico/<int:id_>", methods=["DELETE"])
def api_historico_excluir(id_):
    item = db.obter(id_)
    if not item:
        return jsonify({"erro": "não encontrado"}), 404
    if not _e_supervisao() and item["professor"].lower() != session.get("professor", "").lower():
        return jsonify({"erro": "sem permissão"}), 403
    db.excluir(id_)
    return jsonify({"ok": True})


@app.route("/api/historico/<int:id_>/visto", methods=["POST"])
def api_historico_visto(id_):
    if not _e_supervisao():
        return jsonify({"erro": "sem permissão"}), 403
    body = request.get_json(silent=True) or {}
    db.marcar_visto(id_, SUPERVISAO_NOME or "Supervisão", desfazer=bool(body.get("desfazer")))
    return jsonify({"ok": True})


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
    print(f"Gerador de Plano de Aula rodando em http://localhost:{porta}")
    app.run(host="0.0.0.0", port=porta, debug=False)
