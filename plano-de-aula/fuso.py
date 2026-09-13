"""Horário local da escola (padrão America/Sao_Paulo). Altere com a variável FUSO_HORARIO."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo(os.getenv("FUSO_HORARIO", "America/Sao_Paulo"))


def agora() -> datetime:
    """Data/hora atual no fuso da escola (sem tzinfo, para gravar/comparar em texto)."""
    return datetime.now(FUSO).replace(tzinfo=None)


def hoje():
    return agora().date()


def agora_txt() -> str:
    return agora().strftime("%Y-%m-%d %H:%M:%S")
