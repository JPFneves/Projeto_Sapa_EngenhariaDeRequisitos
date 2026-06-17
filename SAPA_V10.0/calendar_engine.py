"""
calendar_engine.py v3.0 — Motor de detecção de aula por data e dia da semana
SAPA v9.0 — Correções aplicadas:
  - get_disciplina_atual(): db_path padrão agora usa DB_PATH absoluto de database.py
    (eliminando o bug de "banco não encontrado" quando working directory ≠ pasta do script)
  - listar_disciplinas_do_dia(): mesma correção
  - Exceção genérica capturada além de OperationalError (ex: banco bloqueado)
"""

import sqlite3
from datetime import datetime, date

from database import DB_PATH   # ← caminho absoluto (CORREÇÃO CRÍTICA)

DIAS_PT = [
    "Segunda-feira", "Terça-feira", "Quarta-feira",
    "Quinta-feira",  "Sexta-feira", "Sábado",       "Domingo"
]


def _parse_data(texto: str):
    """Converte 'DD/MM/AAAA' para date. Retorna None se inválido."""
    if not texto or not texto.strip():
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto.strip(), fmt).date()
        except ValueError:
            continue
    return None


def get_disciplina_atual(db_path: str = None):
    """
    Retorna dict com dados da disciplina ativa AGORA, ou None.

    Retorno: {"id", "mat", "bl", "sem", "prof", "nome_completo"}

    Regra de seleção:
      - Dia_Semana == dia da semana atual (ex: "Segunda-feira")
      - hoje >= Data_Inicio  (se Data_Inicio preenchida)
      - hoje <= Data_Fim     (se Data_Fim preenchida)
      - Se várias disciplinas batem, retorna a com Data_Inicio mais recente
    """
    # CORREÇÃO: usa DB_PATH absoluto por padrão; aceita override para testes
    path = db_path or DB_PATH

    agora   = datetime.now()
    hoje    = agora.date()
    dia_str = DIAS_PT[agora.weekday()]

    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT ID, Nome_Materia, Bloco, Semestre, Professor_Nome,
                       Data_Inicio, Data_Fim
                FROM DISCIPLINAS
                WHERE Dia_Semana = ?
                """,
                (dia_str,)
            ).fetchall()

        if not rows:
            return None

        candidatas = []
        for r in rows:
            data_ini = _parse_data(r["Data_Inicio"])
            data_fim = _parse_data(r["Data_Fim"])

            if data_ini and hoje < data_ini:
                continue   # ainda não começou
            if data_fim and hoje > data_fim:
                continue   # já terminou

            candidatas.append(r)

        if not candidatas:
            return None

        def _chave(r):
            d = _parse_data(r["Data_Inicio"])
            return d if d else date.min

        melhor = max(candidatas, key=_chave)

        nome_completo = (
            f"{melhor['Nome_Materia']} - {melhor['Semestre']}"
            f" ({melhor['Bloco']}) - {melhor['Professor_Nome']}"
        )

        return {
            "id":            melhor["ID"],
            "mat":           melhor["Nome_Materia"],
            "bl":            melhor["Bloco"],
            "sem":           melhor["Semestre"],
            "prof":          melhor["Professor_Nome"],
            "nome_completo": nome_completo,
        }

    except Exception as e:
        # CORREÇÃO: captura qualquer erro (banco bloqueado, corrompido, inexistente)
        print(f"[calendar_engine] get_disciplina_atual: {e}")
        return None


def listar_disciplinas_do_dia(db_path: str = None) -> list:
    """
    Retorna TODAS as disciplinas ativas hoje (para debug ou exibição).
    """
    path = db_path or DB_PATH   # CORREÇÃO: caminho absoluto

    agora   = datetime.now()
    hoje    = agora.date()
    dia_str = DIAS_PT[agora.weekday()]

    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM DISCIPLINAS WHERE Dia_Semana=?", (dia_str,)
            ).fetchall()

        resultado = []
        for r in rows:
            data_ini = _parse_data(r["Data_Inicio"])
            data_fim = _parse_data(r["Data_Fim"])
            if data_ini and hoje < data_ini: continue
            if data_fim and hoje > data_fim: continue
            resultado.append(dict(r))
        return resultado

    except Exception:
        return []
