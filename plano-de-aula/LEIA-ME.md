# Gerador Automático de Plano de Aula — Presidente Bernardes

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
- **Google Gemini**: chave gratuita em https://aistudio.google.com/app/apikey — modelo `gemini-1.5-flash`
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

## Estrutura
- `app.py` — servidor web (Flask)
- `gerador.py` — prompt e integração com a IA (OpenAI/Gemini)
- `pdf.py` — montagem do PDF no layout da escola
- `templates/index.html` — interface do professor
- `static/logo.png` — logotipo extraído do modelo original
