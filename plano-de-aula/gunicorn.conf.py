# Configuração do servidor (lida automaticamente pelo gunicorn quando está na pasta do app).
# Vale mesmo que o Start Command do Render seja o antigo "gunicorn -w 2 -t 180 -b 0.0.0.0:$PORT app:app".
import os

bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
workers = 2
worker_class = "gthread"   # atende várias pessoas ao mesmo tempo dentro de cada worker
threads = 8
timeout = 180
keepalive = 5
