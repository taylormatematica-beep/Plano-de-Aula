"""
Autenticação por usuário (e-mail institucional + senha).

- Domínio permitido: DOMINIO_EMAIL (padrão educacao.mg.gov.br)
- Primeiro acesso: o professor informa o e-mail → recebe link para criar a senha.
- Esqueci a senha: mesmo fluxo.
- Perfis: 'professor' e 'supervisao'. E-mails listados em SUPERVISAO_EMAILS
  viram supervisão automaticamente ao criar a conta.
"""
import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

import db
import email_util
import fuso

DOMINIO = (os.getenv("DOMINIO_EMAIL", "educacao.mg.gov.br").strip().lower().lstrip("@")) or "educacao.mg.gov.br"
DOMINIOS_EXTRAS = [d.strip().lower().lstrip("@") for d in os.getenv("DOMINIOS_EXTRAS", "").split(",") if d.strip()]
SUPERVISAO_EMAILS = {e.strip().lower() for e in os.getenv("SUPERVISAO_EMAILS", "").split(",") if e.strip()}
VALIDADE_HORAS = int(os.getenv("LINK_VALIDADE_HORAS", "48") or 48)
SENHA_MIN = 8

_RE_EMAIL = re.compile(r"^[a-z0-9][a-z0-9._%+-]*@([a-z0-9.-]+\.[a-z]{2,})$")


class AuthErro(Exception):
    pass


# --------------------------------------------------------------------------- #
# Validações
# --------------------------------------------------------------------------- #
def normalizar_email(email: str) -> str:
    return (email or "").strip().lower()


def email_valido(email: str) -> bool:
    email = normalizar_email(email)
    m = _RE_EMAIL.match(email)
    if not m:
        return False
    dominio = m.group(1)
    return dominio == DOMINIO or dominio in DOMINIOS_EXTRAS


def dominio_msg() -> str:
    return f"@{DOMINIO}"


def nome_do_email(email: str) -> str:
    """maria.silva@... -> 'Maria Silva' (sugestão editável)."""
    local = normalizar_email(email).split("@")[0]
    partes = re.split(r"[._\-]+", re.sub(r"\d+", "", local))
    return " ".join(p.capitalize() for p in partes if p)


def senha_forte(senha: str) -> str | None:
    if len(senha) < SENHA_MIN:
        return f"A senha deve ter pelo menos {SENHA_MIN} caracteres."
    if not re.search(r"[A-Za-z]", senha) or not re.search(r"\d", senha):
        return "A senha deve conter letras e números."
    return None


# --------------------------------------------------------------------------- #
# Tokens de criação/redefinição de senha
# --------------------------------------------------------------------------- #
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def gerar_token(usuario_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expira = (fuso.agora() + timedelta(hours=VALIDADE_HORAS)).strftime("%Y-%m-%d %H:%M:%S")
    db.token_criar(usuario_id, _hash_token(token), expira)
    return token


def validar_token(token: str) -> dict:
    """Devolve o registro do token se válido; senão lança AuthErro."""
    t = db.token_obter(_hash_token(token or ""))
    if not t:
        raise AuthErro("Link inválido. Solicite um novo link de acesso.")
    if t.get("usado_em"):
        raise AuthErro("Este link já foi utilizado. Se precisar, solicite um novo.")
    if datetime.strptime(t["expira_em"], "%Y-%m-%d %H:%M:%S") < fuso.agora():
        raise AuthErro("Este link expirou. Solicite um novo link de acesso.")
    return t


# --------------------------------------------------------------------------- #
# Fluxos
# --------------------------------------------------------------------------- #
def solicitar_acesso(email: str, base_url: str, exigir_cadastro: bool = False) -> dict:
    """
    Primeiro acesso / esqueci a senha. Cria o usuário (se domínio ok) e envia o link.
    Retorna {"enviado": bool, "link": str|None, "erro": str|None, "novo": bool}.
    """
    email = normalizar_email(email)
    if not email_valido(email):
        raise AuthErro(f"Use seu e-mail institucional {dominio_msg()}.")

    u = db.usuario_por_email(email)
    novo = False
    if not u:
        if exigir_cadastro:
            raise AuthErro("Este e-mail não está cadastrado. Procure a supervisão.")
        perfil = "supervisao" if email in SUPERVISAO_EMAILS else "professor"
        u = db.usuario_criar(email, nome_do_email(email), perfil)
        novo = True
    if not u.get("ativo", 1):
        raise AuthErro("Este acesso está desativado. Procure a supervisão.")

    token = gerar_token(u["id"])
    link = f"{base_url.rstrip('/')}/senha/{token}"
    primeira = not u.get("senha_hash")
    titulo = "Crie sua senha de acesso" if primeira else "Redefinição de senha"
    intro = ("Você foi cadastrado(a) no Docea, o assistente pedagógico da Escola Presidente Bernardes. "
             "Clique no botão abaixo para criar sua senha e começar a usar o sistema."
             if primeira else
             "Recebemos um pedido para redefinir a senha da sua conta no Docea (assistente pedagógico). "
             "Clique no botão abaixo para escolher uma nova senha.")
    texto, html = email_util.template_link(titulo, u.get("nome") or "", intro, link, f"{VALIDADE_HORAS} horas")

    resultado = {"enviado": False, "link": None, "erro": None, "novo": novo, "primeira": primeira}
    if email_util.configurado():
        try:
            email_util.enviar(email, f"{titulo} — Docea", texto, html)
            resultado["enviado"] = True
        except Exception as e:  # noqa: BLE001
            resultado["erro"] = str(e)
            resultado["link"] = link      # fallback: supervisão pode repassar manualmente
    else:
        resultado["erro"] = "E-mail não configurado no servidor."
        resultado["link"] = link
    return resultado


def definir_senha(token: str, senha: str, nome: str | None = None) -> dict:
    t = validar_token(token)
    erro = senha_forte(senha)
    if erro:
        raise AuthErro(erro)
    u = db.usuario_por_id(t["usuario_id"])
    if not u:
        raise AuthErro("Usuário não encontrado.")
    db.usuario_definir_senha(u["id"], generate_password_hash(senha), nome or None)
    db.token_usar(t["id"])
    return db.usuario_por_id(u["id"])


def autenticar(email: str, senha: str) -> dict:
    email = normalizar_email(email)
    u = db.usuario_por_email(email)
    if not u or not u.get("senha_hash"):
        raise AuthErro("E-mail não cadastrado ou senha ainda não criada. Use \"Primeiro acesso\".")
    if not u.get("ativo", 1):
        raise AuthErro("Este acesso está desativado. Procure a supervisão.")
    if not check_password_hash(u["senha_hash"], senha or ""):
        raise AuthErro("Senha incorreta.")
    db.usuario_tocar(u["id"])
    return u


def trocar_senha(usuario_id: int, atual: str, nova: str):
    u = db.usuario_por_id(usuario_id)
    if not u or not check_password_hash(u.get("senha_hash") or "", atual or ""):
        raise AuthErro("Senha atual incorreta.")
    erro = senha_forte(nova)
    if erro:
        raise AuthErro(erro)
    db.usuario_definir_senha(usuario_id, generate_password_hash(nova))
