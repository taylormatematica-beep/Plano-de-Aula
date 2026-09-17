# Docea — assistente pedagógico (Presidente Bernardes)

> Nome anterior: *Assistente de Plano de Aula*. A plataforma planeja, aplica, corrige e devolve resultados; o nome acompanhou o escopo.

O professor informa apenas **matéria, conteúdo, data e série**; o sistema gera, via IA,
o restante do plano (Tema, Habilidade da BNCC, Objetivos, Metodologia, Recursos e Avaliação)
e entrega um **PDF no modelo oficial da escola**.

## 1. Instalação (uma vez, no computador/servidor)
```bash
pip install -r requirements.txt
python app.py
```
Acesse: http://localhost:5000  (na rede da escola: http://IP-DO-COMPUTADOR:5000)

## 2. Ativar a IA (uma vez, pela coordenação)
Clique em **⚙ Configurações** na tela e informe:
- **OpenAI**: chave em https://platform.openai.com/api-keys — modelo sugerido `gpt-4o-mini` (barato: ~R$0,01 por plano)
- **Google Gemini**: chave gratuita em https://aistudio.google.com/app/apikey — modelo `gemini-3.8-flash`
- Também aceita Groq, OpenRouter, Ollama etc. (preencha a URL base)

Alternativa: criar o arquivo `config.json` ou variáveis de ambiente
`AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL`.

Sem chave, o sistema funciona em **modo demonstração** (textos genéricos).

## 3. Uso pelo professor
1. Escolhe a disciplina, digita o conteúdo, escolhe a data e a série.
2. Clica em **Gerar plano de aula** (10–30 s).
3. Revisa a pré-visualização — pode clicar em qualquer texto para ajustar.
4. Clica em **Baixar PDF**.

Campos opcionais: período (data final), nº de aulas na semana, supervisão e observações para a IA
(ex.: "turma com dificuldade em leitura", "usar laboratório", "revisão ENEM").

## Histórico e assinaturas
Veja `ATUALIZACAO-HISTORICO.md` (banco de dados, senha da supervisão, nomes para assinatura).

## Login individual e e-mail
Cada professor entra com e-mail institucional + senha: veja `USUARIOS-E-EMAIL.md`.

## Google Drive
Envio automático dos PDFs: veja `GOOGLE-DRIVE.md`.

## Estrutura
- `app.py` — servidor web (Flask)
- `gerador.py` — prompt e integração com a IA (OpenAI/Gemini)
- `pdf.py` — montagem do PDF no layout da escola
- `templates/index.html` — interface do professor
- `static/logo.png` — logotipo extraído do modelo original

## Fontes de pesquisa e Cadernos do ICE

- A IA fundamenta cada plano na **BNCC (Ensino Médio)**, no **Currículo Referência de Minas Gerais** e nos
  **princípios/metodologias da Escola da Escolha (ICE)** — Protagonismo, 4 Pilares, Pedagogia da Presença,
  Educação Interdimensional, Metodologias de Êxito (Estudo Orientado, Tutoria, Práticas Experimentais, Eletivas…).
- Todo plano traz um quadro **FONTES / REFERÊNCIAS** ao final (na tela e no PDF).
- Em **📚 Referências** (`/biblioteca`) a supervisão pode **enviar os PDFs dos Cadernos do ICE** (ou qualquer
  documento com texto selecionável). O texto é indexado; na hora de gerar, os trechos ligados ao tema da aula
  são entregues à IA e citados nas fontes. Sem envio, o sistema usa uma síntese interna dos cadernos.
- Na tela principal, "Fontes de pesquisa da IA" fica recolhido, com tudo marcado por padrão — o professor
  continua preenchendo só os 4 campos.

## Cota da IA (erro 429)
A chave gratuita do Gemini tem limite de requisições por minuto e por dia, **por modelo**. Quando estoura,
o sistema passa automaticamente para outros modelos da sua chave (inclusive os "lite", que têm cota maior).
Para aumentar a capacidade sem pagar: crie chaves extras em contas Google diferentes (aistudio.google.com/app/apikey)
e coloque-as no Render em `AI_API_KEYS_EXTRA`, separadas por vírgula. O sistema faz rodízio quando uma chave esgota.
Para nunca mais estourar: ative o faturamento da chave no Google AI Studio (custo de centavos por plano).

## Provas e atividades
Em **📝 Provas e atividades**, o professor marca os planos de aula que já gerou, escolhe o tipo, a quantidade de questões
(múltipla escolha / discursivas), se é avaliativa e o valor total. A IA elabora as questões a partir dos conteúdos dos planos.
Ele pode editar tudo, ajustar o valor de cada questão e baixar o **PDF da prova** e o **PDF do gabarito** (com resoluções e critérios).
As provas ficam guardadas e podem ser enviadas ao Drive. A supervisão vê as de todos.

Velocidade: as questões são pedidas à IA em **lotes de 4, todos ao mesmo tempo** (uma prova de 12 questões leva o tempo de uma de 4).
Ajustes opcionais no Render: `AI_LOTE_QUESTOES` (questões por lote, padrão 4) e `AI_LOTES_PARALELOS` (lotes simultâneos, padrão 5).
Cada lote conta como uma requisição na cota da chave — se a cota estourar com frequência, aumente `AI_LOTE_QUESTOES` para 6.

## Correção automática
Na prova (página **Provas e atividades**), clique em **➕ Gerar código de prova**. Você recebe um código de 6 letras e um QR code.
- **Online:** alunos acessam `SEU-SITE/prova`, digitam o código, nome e número, e respondem pelo celular. Múltipla escolha é corrigida na hora.
- **Papel:** aplique a prova impressa e, na página de correção, digite uma linha por aluno: `12; Ana Souza; BCADE`.
- **Discursivas:** a IA sugere nota e comentário com base na resposta esperada e nos critérios; você confirma ou ajusta.
Baixe as notas em Excel e o relatório em PDF (média, % por questão, questões mais erradas, por habilidade).

### Prova em papel com leitura por foto (cartão-resposta)
Na página de correção: **Imprimir cartões** (em branco ou com os nomes dos alunos) → aplique com a prova → tire foto de cada
cartão com o celular → **Enviar fotos** → confira nome/número e as questões destacadas em vermelho → **Lançar**.
Dicas para a foto: cartão inteiro, com os 4 quadrados pretos visíveis, de frente, sem sombra forte. Funciona de cabeça para baixo e deitado.

### Corrigir no celular (câmera ao vivo)
Na página de correção, **📱 Corrigir no celular** (ou leia o QR com o celular). A câmera fica aberta: aponte para o cartão,
o sistema lê sozinho (vibra ao confirmar), você digita o nome (o campo NOME aparece recortado), confirma e passa para o próximo.
Requer HTTPS (o Render já é) e permissão de câmera no navegador.
