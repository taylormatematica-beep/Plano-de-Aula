"""
Envio de e-mails via SMTP (Gmail, Brevo, Outlook ou qualquer servidor).

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


def configurado() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASS)


def enviar(destinatario: str, assunto: str, texto: str, html: str | None = None) -> None:
    """Envia o e-mail. Lança exceção com mensagem amigável em caso de falha."""
    if not configurado():
        raise RuntimeError("Servidor de e-mail não configurado (SMTP_HOST/SMTP_USER/SMTP_PASS).")

    msg = EmailMessage()
    nome, end = parseaddr(SMTP_FROM)
    msg["From"] = formataddr((nome or "Assistente de Plano de Aula", end or SMTP_USER))
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
