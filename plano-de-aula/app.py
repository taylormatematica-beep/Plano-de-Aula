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

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

# ----------------------------------------------------------------------------
# Senha de acesso (opcional). Defina a variável de ambiente APP_SENHA para
# exigir uma senha única compartilhada com os professores.
# ----------------------------------------------------------------------------
import os, hmac  # noqa: E402
from flask import redirect, session, url_for  # noqa: E402

APP_SENHA = os.getenv("APP_SENHA", "").strip()
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
        if hmac.compare_digest(request.form.get("senha", ""), APP_SENHA):
            session["ok"] = True
            return redirect("/")
        erro = "<p class=e>Senha incorreta.</p>"
    return LOGIN_HTML.replace("{erro}", erro)


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
    )


@app.route("/api/gerar", methods=["POST"])
def api_gerar():
    dados = request.get_json(force=True) or {}
    obrig = ["disciplina", "conteudo", "data", "serie"]
    faltando = [c for c in obrig if not str(dados.get(c, "")).strip()]
    if faltando:
        return jsonify({"erro": f"Preencha: {', '.join(faltando)}"}), 400

    dados["data"] = _formatar_data(dados["data"])
    if dados.get("data_fim"):
        dados["data"] = f"{dados['data']} a {_formatar_data(dados['data_fim'])}"
    try:
        plano = gerar_plano(dados)
    except Exception as e:  # noqa: BLE001
        return jsonify({"erro": f"Falha ao consultar a IA: {e}"}), 502
    return jsonify({"dados": dados, "plano": plano})


@app.route("/api/pdf", methods=["POST"])
def api_pdf():
    body = request.get_json(force=True) or {}
    dados, plano = body.get("dados", {}), body.get("plano", {})
    pdf = gerar_pdf(dados, plano)
    nome = f"plano-de-aula-{_slug(dados.get('disciplina','')) or 'x'}-{_slug(dados.get('serie',''))}-{_slug(dados.get('data',''))}.pdf"
    return send_file(BytesIO(pdf), mimetype="application/pdf", as_attachment=True, download_name=nome)


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
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
