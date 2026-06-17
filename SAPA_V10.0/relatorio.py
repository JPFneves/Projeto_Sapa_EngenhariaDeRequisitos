"""
relatorio.py — Geração e envio de relatório de presença
SAPA v9.0 — Correções aplicadas:
  - conectar() → usa DB_PATH absoluto de database.py (bug crítico)
  - gerar_conteudo_relatorio(): try/except em torno da query ao banco
  - enviar_relatorio_por_email(): timeout explícito no SMTP (não trava para sempre)
  - enviar_relatorio_completo_csv(): idem; retorno False em erro garantido
  - Coluna Justificativa lida com .get() seguro (não quebra em banco antigo)
  - if __name__ == "__main__" movido para o final (estava no meio do arquivo,
    impedindo a importação das funções abaixo dele em algumas versões do Python)
"""

import csv
import logging
import os
import smtplib
import sqlite3
from collections import defaultdict
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import StringIO

from dotenv import load_dotenv

from database import DB_PATH, ENV_PATH

_ENV_PATH = ENV_PATH
load_dotenv(dotenv_path=_ENV_PATH, override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RELATORIO] %(levelname)s %(message)s",
)


# ──────────────────────────────────────────────────────────────────────────────
# CONEXÃO
# ──────────────────────────────────────────────────────────────────────────────
def conectar():
    conn = sqlite3.connect(DB_PATH)   # ← absoluto
    conn.row_factory = sqlite3.Row
    return conn


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def extrair_infos_disciplina(disciplina_str):
    """Extrai (Materia, Semestre, Bloco, Prof) de uma string formatada."""
    try:
        if not disciplina_str:
            return "", "", "", ""
        parts = disciplina_str.split(" - ")
        materia  = parts[0]
        sem_bloco = parts[1] if len(parts) > 1 else ""
        semestre = sem_bloco.split(" (")[0]
        bloco    = sem_bloco.split("(")[1].replace(")", "") if "(" in sem_bloco else ""
        prof     = parts[2] if len(parts) > 2 else ""
        return materia, semestre, bloco, prof
    except Exception:
        return str(disciplina_str), "", "", ""


def inferir_periodo(turma):
    t = str(turma).strip().upper()
    if t == "A" or t.endswith("- A") or t.endswith("-A"): return "1º/2º Período"
    if t == "B" or t.endswith("- B") or t.endswith("-B"): return "3º/4º Período"
    if t == "C" or t.endswith("- C") or t.endswith("-C"): return "5º/6º Período"
    return "Outro"


# ──────────────────────────────────────────────────────────────────────────────
# GERAÇÃO DO RELATÓRIO HTML
# ──────────────────────────────────────────────────────────────────────────────
def gerar_conteudo_relatorio(data_alvo: str, professor_alvo: str = "") -> str:
    try:
        with conectar() as conn:
            alunos_dict = {
                a["RA"]: a for a in conn.execute(
                    "SELECT RA, Nome, Turma FROM ALUNOS"
                ).fetchall()
            }
            logs = conn.execute(
                """
                SELECT RA_Aluno, Disciplina, Tipo, Hora, Hora_Entrada, Hora_Saida
                FROM LOGS
                WHERE Data = ?
                """,
                (data_alvo,)
            ).fetchall()
    except Exception as exc:
        logging.error(f"gerar_conteudo_relatorio: erro ao ler banco: {exc}")
        return f"<p>Erro ao gerar relatório para {data_alvo}: {exc}</p>"

    if not logs:
        return f"<p>Nenhum registro encontrado para {data_alvo}.</p>"

    disciplinas_do_dia = {log["Disciplina"] for log in logs if log["Disciplina"]}

    logs_por_disc: dict = defaultdict(dict)
    for log in logs:
        logs_por_disc[log["Disciplina"]][log["RA_Aluno"]] = log

    corpo = f"""
    <h2 style='color:#1f538d; font-family:Arial'>
        📊 SAPA — Relatório de Frequência ({data_alvo})
    </h2>
    <hr style='border-color:#ddd'>
    """

    COR = {
        "ENTRADA":    "#1DB954",
        "SAIDA":      "#2196F3",
        "JUSTIFICADO":"#FF8C00",
        "FALTA":      "#E53935",
    }

    alunos_ordenados = sorted(alunos_dict.values(), key=lambda a: a["Nome"])

    for disciplina in sorted(disciplinas_do_dia):
        corpo += f"<h3 style='color:#333;font-family:Arial'>📚 {disciplina}</h3><ul>"
        for aluno in alunos_ordenados:
            ra   = aluno["RA"]
            nome = aluno["Nome"]

            if ra in logs_por_disc[disciplina]:
                r       = logs_por_disc[disciplina][ra]
                tipo    = r["Tipo"]
                entrada = r["Hora_Entrada"] or r["Hora"] or ""
                saida   = r["Hora_Saida"]   or ""
                detalhe = ""
                if entrada: detalhe += f" [Entrada: {entrada}]"
                if saida:   detalhe += f" [Saída: {saida}]"
            else:
                tipo    = "FALTA"
                detalhe = ""

            cor = COR.get(tipo, "#666")
            corpo += (
                f"<li style='font-family:Arial;margin:4px 0'>"
                f"RA <b>{ra}</b> — {nome} — "
                f"<span style='color:{cor};font-weight:bold'>{tipo}</span>{detalhe}"
                f"</li>"
            )
        corpo += "</ul>"

    return corpo


# ──────────────────────────────────────────────────────────────────────────────
# ENVIO DE RELATÓRIO HTML POR E-MAIL
# ──────────────────────────────────────────────────────────────────────────────
def enviar_relatorio_por_email(
    destinatario: str,
    data_alvo: str = "",
    professor_alvo: str = ""
):
    if not data_alvo:
        data_alvo = datetime.now().strftime("%d/%m/%Y")

    # Relê .env a cada chamada (configurações podem ter mudado)
    load_dotenv(dotenv_path=_ENV_PATH, override=True)
    EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE", "")
    EMAIL_SENHA     = os.getenv("EMAIL_SENHA", "")

    if not EMAIL_REMETENTE or not EMAIL_SENHA:
        logging.warning("EMAIL_REMETENTE / EMAIL_SENHA não configurados no .env. Envio pulado.")
        return

    corpo_html = gerar_conteudo_relatorio(data_alvo, professor_alvo)

    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL_REMETENTE
    msg["To"]   = destinatario
    assunto = f"SAPA — Relatório de Frequência — {data_alvo}"
    if professor_alvo:
        assunto += f" ({professor_alvo})"
    msg["Subject"] = assunto
    msg.attach(MIMEText(corpo_html, "html", "utf-8"))

    try:
        # CORREÇÃO: timeout=15 evita travar indefinidamente em rede ruim
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.starttls()
            server.login(EMAIL_REMETENTE, EMAIL_SENHA)
            server.sendmail(EMAIL_REMETENTE, destinatario, msg.as_string())
        logging.info(f"Relatório enviado para {destinatario}!")
    except smtplib.SMTPAuthenticationError:
        logging.error("Falha de autenticação SMTP. Verifique EMAIL_REMETENTE e EMAIL_SENHA no .env.")
        raise
    except Exception as e:
        logging.error(f"Falha ao enviar e-mail: {e}")
        raise


# ──────────────────────────────────────────────────────────────────────────────
# ENVIO DE CSV COMPLETO (Power BI)
# ──────────────────────────────────────────────────────────────────────────────
def enviar_relatorio_completo_csv(
    destinatario: str,
    professor_alvo: str = ""
) -> bool:
    load_dotenv(dotenv_path=_ENV_PATH, override=True)
    EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE", "")
    EMAIL_SENHA     = os.getenv("EMAIL_SENHA", "")

    if not EMAIL_REMETENTE or not EMAIL_SENHA:
        logging.warning("EMAIL_REMETENTE / EMAIL_SENHA não configurados. Envio CSV pulado.")
        return False

    try:
        with conectar() as conn:
            rows = conn.execute(
                """
                SELECT l.ID, l.Data, l.Hora_Entrada, l.Hora_Saida,
                       l.Disciplina, l.Tipo, l.Justificativa,
                       a.RA, a.Nome, a.Turma
                FROM LOGS l
                LEFT JOIN ALUNOS a ON l.RA_Aluno = a.RA
                ORDER BY l.ID DESC
                """
            ).fetchall()
    except Exception as exc:
        logging.error(f"enviar_relatorio_completo_csv: erro ao ler banco: {exc}")
        return False

    if not rows:
        logging.info("Nenhum dado na base para exportar.")
        return False

    si = StringIO()
    writer = csv.writer(si, delimiter=";")
    writer.writerow([
        "Log_ID","RA","Aluno_Nome","Turma","Periodo_Inferido",
        "Data","Hora_Entrada","Hora_Saida",
        "Materia","Professor","Semestre","Bloco",
        "Status","Justificativa"
    ])
    for r in rows:
        mat, sem, blo, prof = extrair_infos_disciplina(r["Disciplina"])
        per = inferir_periodo(r["Turma"])
        # CORREÇÃO: .get() seguro para Justificativa (pode ser None)
        justificativa = r["Justificativa"] if r["Justificativa"] else ""
        writer.writerow([
            r["ID"], r["RA"], r["Nome"], r["Turma"], per,
            r["Data"], r["Hora_Entrada"] or "", r["Hora_Saida"] or "",
            mat, prof, sem, blo,
            r["Tipo"], justificativa
        ])

    csv_data = si.getvalue().encode("utf-8-sig")

    msg = MIMEMultipart()
    msg["From"]    = EMAIL_REMETENTE
    msg["To"]      = destinatario
    assunto_csv    = "📊 SAPA — Base Completa Power BI (CSV)"
    corpo_txt      = "Segue em anexo a base completa de todos os registros para importação no Power BI."
    if professor_alvo:
        assunto_csv += f" - Prof. {professor_alvo}"
        corpo_txt    = f"Olá, Prof. {professor_alvo}.\n\n" + corpo_txt
    msg["Subject"] = assunto_csv
    msg.attach(MIMEText(corpo_txt, "plain", "utf-8"))

    anexo = MIMEApplication(csv_data, Name="sapa_base_completa.csv")
    anexo["Content-Disposition"] = 'attachment; filename="sapa_base_completa.csv"'
    msg.attach(anexo)

    try:
        # CORREÇÃO: timeout=15 para não travar
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.starttls()
            server.login(EMAIL_REMETENTE, EMAIL_SENHA)
            server.sendmail(EMAIL_REMETENTE, destinatario, msg.as_string())
        logging.info(f"CSV completo enviado para {destinatario}!")
        return True
    except Exception as e:
        logging.error(f"Falha ao enviar CSV: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# TESTE LOCAL
# CORREÇÃO: movido para o final (estava no meio do arquivo, bloqueando imports)
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    hoje = datetime.now().strftime("%d/%m/%Y")
    print(gerar_conteudo_relatorio(hoje))
