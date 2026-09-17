# Login individual dos professores (autocadastro)

## Como funciona para o professor
1. Acessa o sistema → **"É seu primeiro acesso?"**
2. Digita o e-mail institucional `nome@educacao.mg.gov.br` (outros domínios são recusados).
3. Recebe um e-mail com o botão **Criar minha senha** (válido por 48 h, uso único).
4. Informa nome completo + senha (mín. 8 caracteres, letras e números) e já entra.
5. Próximos acessos: e-mail + senha. "Esqueci minha senha" repete o fluxo.

Ninguém precisa ser cadastrado previamente. O nome do professor vai automaticamente para o plano e o PDF
(editável em **Minha conta**). O histórico fica vinculado ao e-mail.

---

## O que a supervisão precisa configurar (uma vez)

### 1. E-mail de saída — Brevo (gratuito, 5 min)

> ⚠️ O plano gratuito do Render **bloqueia SMTP** (Gmail direto não funciona — dá "Network is unreachable").
> Por isso usamos o **Brevo**, que envia por API HTTP. 300 e-mails/dia grátis, sem cartão.

1. Crie a conta em **https://www.brevo.com** (pode usar o e-mail da escola). Confirme o e-mail de cadastro.
2. **Remetente:** menu (canto superior direito) → **Senders, Domains & Dedicated IPs** → **Senders** → **Add a sender**
   → nome `Docea`, e-mail da escola (ex.: `escola@gmail.com`) → **Save**.
   Abra o e-mail de confirmação que o Brevo mandou e clique no link. *(O remetente precisa estar "Verified".)*
3. **Chave da API:** https://app.brevo.com/settings/keys/api → **Generate a new API key** → nome `Plano de Aula` → copie a chave (começa com `xkeysib-`).
4. **Render → Environment**:

| Variável | Valor |
|---|---|
| `BREVO_API_KEY` | a chave `xkeysib-...` |
| `EMAIL_FROM` | `Docea <escola@gmail.com>` (o mesmo e-mail validado no passo 2) |

5. Após o redeploy, entre como supervisão → **👥 Usuários** → **✉ Enviar e-mail de teste para mim**.

*(As variáveis `SMTP_*` podem ser removidas; só funcionam em hospedagens que liberam a porta 587.)*

### 2. Quem é supervisão + endereço público

| Variável | Valor |
|---|---|
| `SUPERVISAO_EMAILS` | e-mails da supervisão separados por vírgula |
| `PUBLIC_URL` | `https://SEU-APP.onrender.com` |
| `SUPERVISAO_SENHA` | *(opcional)* acesso de emergência em `/supervisao/login` |

`APP_SENHA` não é mais usada — pode remover.

### 3. Primeiro uso
1. Acesse `/primeiro-acesso` com seu e-mail (listado em `SUPERVISAO_EMAILS`) e crie sua senha — você entra como supervisão.
2. Envie aos professores:

> **Docea** — acesse `https://SEU-APP.onrender.com`, clique em **"É seu primeiro acesso?"**,
> digite seu e-mail @educacao.mg.gov.br e siga o link que chegar (confira o spam). Crie sua senha e pronto.

---

## Tela 👥 Usuários (supervisão)
Mostra quem já criou senha e quem não; permite reenviar link, redefinir senha, promover a supervisão,
desativar ou excluir. Também aceita cadastrar e-mails em lote, se um dia for útil.

## Variáveis opcionais
| Variável | Padrão | Para quê |
|---|---|---|
| `DOMINIO_EMAIL` | `educacao.mg.gov.br` | domínio aceito |
| `DOMINIOS_EXTRAS` | — | outros domínios, separados por vírgula (ex.: para testes) |
| `LINK_VALIDADE_HORAS` | `48` | validade do link |

## Problemas comuns
| Sintoma | Solução |
|---|---|
| "Network is unreachable" / "timed out" | A hospedagem bloqueia SMTP. Use o Brevo (API) conforme a Parte 1. |
| "Brevo: o remetente não está validado" | Em Brevo → Senders, confirme o e-mail usado em `EMAIL_FROM`. |
| "Brevo recusou a chave" | Copie novamente a `BREVO_API_KEY` (sem espaços). |
| E-mail não chega | Verifique spam; use o botão de teste em Usuários; confira `/diagnostico`. |
| Link "expirado" ou "já utilizado" | Professor usa "Esqueci minha senha" para receber outro. |
| Sem SMTP configurado | O sistema segue funcionando: o link aparece na tela da supervisão para repassar manualmente. |
