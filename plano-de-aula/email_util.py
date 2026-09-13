"""
Envio de e-mails.

Dois modos (o primeiro configurado é usado):

1) API HTTP — funciona em hospedagens que bloqueiam SMTP (Render gratuito, Railway...).
   BREVO_API_KEY   chave "xkeysib-..." de https://app.brevo.com/settings/keys/api   (300 e-mails/dia grátis)
   RESEND_API_KEY  chave "re_..." de https://resend.com  (100/dia grátis; exige domínio próprio verificado)
   EMAIL_FROM      remetente, ex.: "Assistente de Plano de Aula <escola@gmail.com>"
                   (no Brevo, o e-mail precisa estar validado em Senders)

2) SMTP clássico (Gmail com senha de app, Outlook etc.) — só em hospedagens que liberam a porta 587/465.
Variáveis de ambiente:
  SMTP_HOST      ex.: smtp.gmail.com   |  smtp-relay.brevo.com  |  smtp.office365.com
  SMTP_PORT      587 (STARTTLS, padrão) ou 465 (SSL)
  SMTP_USER      usuário/login do SMTP (normalmente o e-mail)
  SMTP_PASS      senha (no Gmail: "senha de app" de 16 letras)
  SMTP_FROM      remetente exibido, ex.: "Assistente de Plano de Aula <escola@gmail.com>"
                 (opcional; padrão = SMTP_USER)
"""
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip().replace(" ", "")  # senha de app do Gmail vem com espaços
SMTP_FROM = os.getenv("SMTP_FROM", "").strip() or SMTP_USER
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
EMAIL_FROM = os.getenv("EMAIL_FROM", "").strip() or SMTP_FROM


def modo() -> str:
    if BREVO_API_KEY:
        return "brevo"
    if RESEND_API_KEY:
        return "resend"
    if SMTP_HOST and SMTP_USER and SMTP_PASS:
        return "smtp"
    return ""


def configurado() -> bool:
    return bool(modo())


def descricao() -> str:
    m = modo()
    if m == "brevo":
        return f"Brevo (API) · remetente {EMAIL_FROM or '⚠️ EMAIL_FROM vazio'}"
    if m == "resend":
        return f"Resend (API) · remetente {EMAIL_FROM or '⚠️ EMAIL_FROM vazio'}"
    if m == "smtp":
        return f"SMTP {SMTP_HOST}:{SMTP_PORT} como {SMTP_USER}"
    return "não configurado"


def _remetente() -> tuple[str, str]:
    nome, end = parseaddr(EMAIL_FROM)
    return (nome or "Assistente de Plano de Aula", end or SMTP_USER)


def _enviar_brevo(destinatario: str, assunto: str, texto: str, html: str | None) -> None:
    import requests
    nome, end = _remetente()
    if not end:
        raise RuntimeError("Defina EMAIL_FROM com o e-mail validado no Brevo (Senders).")
    body = {"sender": {"name": nome, "email": end}, "to": [{"email": destinatario}],
            "subject": assunto, "textContent": texto}
    if html:
        body["htmlContent"] = html
    r = requests.post("https://api.brevo.com/v3/smtp/email", json=body, timeout=30,
                      headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json", "accept": "application/json"})
    if r.status_code >= 400:
        try:
            msg = r.json().get("message") or r.text
        except Exception:
            msg = r.text
        if r.status_code == 401:
            raise RuntimeError("Brevo recusou a chave (BREVO_API_KEY inválida).")
        if "sender" in msg.lower():
            raise RuntimeError(f"Brevo: o remetente {end} não está validado. Em Brevo → Senders, adicione e confirme esse e-mail.")
        raise RuntimeError(f"Brevo: {msg[:200]}")


def _enviar_resend(destinatario: str, assunto: str, texto: str, html: str | None) -> None:
    import requests
    nome, end = _remetente()
    if not end:
        raise RuntimeError("Defina EMAIL_FROM com um e-mail do domínio verificado no Resend.")
    body = {"from": f"{nome} <{end}>", "to": [destinatario], "subject": assunto, "text": texto}
    if html:
        body["html"] = html
    r = requests.post("https://api.resend.com/emails", json=body, timeout=30,
                      headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"})
    if r.status_code >= 400:
        try:
            msg = r.json().get("message") or r.text
        except Exception:
            msg = r.text
        raise RuntimeError(f"Resend: {msg[:200]}")


def enviar(destinatario: str, assunto: str, texto: str, html: str | None = None) -> None:
    """Envia o e-mail. Lança exceção com mensagem amigável em caso de falha."""
    m = modo()
    if not m:
        raise RuntimeError("Envio de e-mail não configurado (BREVO_API_KEY ou SMTP_*).")
    if m == "brevo":
        return _enviar_brevo(destinatario, assunto, texto, html)
    if m == "resend":
        return _enviar_resend(destinatario, assunto, texto, html)

    msg = EmailMessage()
    msg["From"] = formataddr(_remetente())
    msg["To"] = destinatario
    msg["Subject"] = assunto
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30, context=ssl.create_default_context()) as s:
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
                s.ehlo()
                if s.has_extn("starttls"):
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                if s.has_extn("auth"):
                    s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise RuntimeError("O servidor de e-mail recusou o login. No Gmail, use uma 'senha de app' "
                           "(https://myaccount.google.com/apppasswords), não a senha normal.")
    except smtplib.SMTPRecipientsRefused:
        raise RuntimeError(f"O servidor recusou o destinatário {destinatario}.")
    except (smtplib.SMTPException, OSError) as e:
        if "unreachable" in str(e).lower() or "timed out" in str(e).lower():
            raise RuntimeError("A hospedagem bloqueia SMTP (Render gratuito). Use a API do Brevo: "
                               "defina BREVO_API_KEY e EMAIL_FROM (veja USUARIOS-E-EMAIL.md).")
        raise RuntimeError(f"Falha ao enviar e-mail: {e}")


def template_link(titulo: str, nome: str, texto_intro: str, link: str, validade: str) -> tuple[str, str]:
    """Devolve (texto, html) do e-mail de criação/redefinição de senha."""
    saudacao = f"Olá, {nome}!" if nome else "Olá!"
    texto = (
        f"{saudacao}\n\n{texto_intro}\n\n{link}\n\n"
        f"O link é válido por {validade} e pode ser usado uma única vez.\n"
        "Se você não solicitou este acesso, ignore este e-mail.\n\n"
        "Escola Estadual Presidente Bernardes — Ensino Médio Integral\nAssistente de Plano de Aula"
    )
    html = f"""<!doctype html><html><body style="margin:0;background:#f4f4f5;font-family:Segoe UI,Arial,sans-serif;color:#222">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:28px 12px">
<table width="520" cellpadding="0" cellspacing="0" style="background:#fff;border:1px solid #d9d9de;border-radius:12px;max-width:100%">
<tr><td style="padding:22px 28px 0;border-top:4px solid #e10600;border-radius:12px 12px 0 0">
  <div style="font-weight:700;font-size:15px;letter-spacing:.02em">PRESIDENTE BERNARDES <span style="font-weight:400;color:#666;font-size:12px">· ENSINO MÉDIO INTEGRAL</span></div>
</td></tr>
<tr><td style="padding:18px 28px 6px"><h2 style="margin:0 0 10px;font-size:20px">{titulo}</h2>
  <p style="margin:0 0 10px;font-size:15px">{saudacao}</p>
  <p style="margin:0 0 18px;font-size:15px;line-height:1.5">{texto_intro}</p>
  <p style="text-align:center;margin:0 0 18px"><a href="{link}" style="display:inline-block;background:#111;color:#fff;text-decoration:none;padding:12px 26px;border-radius:8px;font-weight:600;font-size:15px">Criar minha senha</a></p>
  <p style="font-size:12px;color:#666;line-height:1.5;margin:0 0 6px">Se o botão não funcionar, copie e cole este endereço no navegador:<br><a href="{link}" style="color:#1a56b8;word-break:break-all">{link}</a></p>
  <p style="font-size:12px;color:#666;line-height:1.5;margin:0">O link é válido por {validade} e pode ser usado uma única vez. Se você não solicitou este acesso, ignore este e-mail.</p>
</td></tr>
<tr><td style="padding:14px 28px 22px;font-size:11px;color:#999;border-top:1px solid #eee;margin-top:10px">Assistente de Plano de Aula · Escola Estadual Presidente Bernardes</td></tr>
</table></td></tr></table></body></html>"""
    return texto, html
