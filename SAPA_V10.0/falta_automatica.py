"""
falta_automatica.py — Robô de faltas automáticas às 22:35
SAPA v9.0 — Correções aplicadas:
  - conectar() → usa DB_PATH absoluto de database.py (bug crítico)
  - processar_faltas_automaticas(): bloco try/except completo no nível da função
    (qualquer exceção não mata o scheduler, apenas loga e segue)
  - INSERT de falta garante Hora_Entrada preenchida (coluna NOT NULL no schema)
  - Log de execução com print() trocado por logging (padrão do projeto)
  - enviar_relatorio_por_email() chamado em thread separada para não bloquear
    o scheduler durante o SMTP
"""

import logging
import os
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR

from database import DB_PATH, conectar as _db_conectar
from sync_manager import enfileirar_log

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [FALTA] %(levelname)s %(message)s",
)


def conectar():
    """Wrapper local — garante caminho absoluto via database.py."""
    return _db_conectar()


def processar_faltas_automaticas():
    """
    Registra FALTA para cada aluno que não tem ENTRADA na disciplina do dia.
    Executado pelo scheduler às 22:35 de seg–sex.
    O bloco try/except externo garante que NUNCA derruba o scheduler.
    """
    try:
        _executar_faltas()
    except Exception as exc:
        logging.error(f"Erro inesperado no robô de faltas: {exc}", exc_info=True)


def _executar_faltas():
    from relatorio import enviar_relatorio_por_email   # import local: evita circular

    agora         = datetime.now()
    data_hj       = agora.strftime("%d/%m/%Y")
    # CORREÇÃO: usa TEXT igual ao calendar_engine ("Segunda-feira" … "Domingo")
    # Antes usava weekday() inteiro (0-6), incompatível com o campo dia_semana TEXT
    _DIAS_PT      = ["Segunda-feira","Terça-feira","Quarta-feira",
                     "Quinta-feira","Sexta-feira","Sábado","Domingo"]
    dia_semana_hj = _DIAS_PT[agora.weekday()]

    logging.info(f"Robô SAPA: processando faltas de {data_hj}...")

    with conectar() as conn:
        conn.row_factory = __import__("sqlite3").Row
        aulas_do_dia = conn.execute(
            """
            SELECT g.turma, g.disciplina_id,
                   d.Nome_Materia || ' - ' || d.Semestre
                   || ' (' || d.Bloco || ') - ' || d.Professor_Nome AS nome_disc
            FROM grade_horarios g
            JOIN DISCIPLINAS d ON g.disciplina_id = d.ID
            WHERE g.dia_semana = ?
            """,
            (dia_semana_hj,)
        ).fetchall()

    if not aulas_do_dia:
        logging.info("Sem aulas na grade para hoje. Nada a fazer.")
        return

    total_faltas = 0

    with conectar() as conn:
        conn.row_factory = __import__("sqlite3").Row

        for aula in aulas_do_dia:
            turma     = aula["turma"]
            disc_id   = aula["disciplina_id"]
            nome_disc = aula["nome_disc"]

            logging.info(f"Verificando turma {turma} | {nome_disc}")

            alunos = [r["RA"] for r in conn.execute(
                "SELECT RA FROM ALUNOS WHERE Turma = ?", (turma,))]

            presentes = {r["RA_Aluno"] for r in conn.execute(
                """
                SELECT DISTINCT RA_Aluno FROM LOGS
                WHERE Data = ? AND Disciplina = ? AND Tipo = 'ENTRADA'
                """,
                (data_hj, nome_disc)
            )}

            ausentes = [ra for ra in alunos if ra not in presentes]

            hora_atual = agora.strftime("%H:%M:%S")
            for ra in ausentes:
                # CORREÇÃO: Hora_Entrada preenchida (coluna definida no schema)
                conn.execute(
                    """
                    INSERT INTO LOGS
                    (RA_Aluno, Data, Hora, Hora_Entrada, Disciplina, Tipo)
                    VALUES (?, ?, ?, ?, ?, 'FALTA')
                    """,
                    (ra, data_hj, hora_atual, hora_atual, nome_disc)
                )
                enfileirar_log(ra_aluno=int(ra), disciplina_id=disc_id, tipo="FALTA")
                logging.info(f"  FALTA: RA {ra}")
                total_faltas += 1

        conn.commit()

    logging.info(f"✅ {total_faltas} faltas registradas.")

    # CORREÇÃO: envio de e-mail em thread separada — não bloqueia o scheduler
    destinatario = os.getenv("EMAIL_RELATORIO", "")
    if destinatario:
        def _enviar():
            try:
                enviar_relatorio_por_email(destinatario=destinatario, data_alvo=data_hj)
            except Exception as ex:
                logging.warning(f"Falha ao enviar relatório automático: {ex}")
        threading.Thread(target=_enviar, daemon=True, name="SAPA-EmailFaltas").start()


def _listener_erros(event):
    logging.error(f"[SCHEDULER] Erro no job '{event.job_id}': {event.exception}")


def iniciar_robo_faltas():
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        processar_faltas_automaticas,
        trigger="cron",
        day_of_week="mon-fri",
        hour=22,
        minute=35,
        id="falta_automatica",
        replace_existing=True,
    )
    scheduler.add_listener(_listener_erros, EVENT_JOB_ERROR)
    scheduler.start()
    logging.info("Robô de faltas automáticas ativo (22:35, seg-sex).")
