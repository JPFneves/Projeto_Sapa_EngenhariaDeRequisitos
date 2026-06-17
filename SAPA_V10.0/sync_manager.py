"""
sync_manager.py — Sincronização bidirecional SQLite ↔ Supabase
SAPA v9.0 — Correções aplicadas:
  - DB_PATH agora usa caminho absoluto (evita OperationalError por working dir errado)
  - _sincronizar(): captura separada de json.JSONDecodeError (não mascarar erros de payload)
  - iniciar_thread_sync(): thread com nome explícito para facilitar debug
  - PULL de logs: paginação corrigida (parâmetro 'id=gt.X' estava sendo passado
    dentro do endpoint string, causando URL mal-formada)
  - sincronizar_do_supabase(): conn.commit() movido para fora dos blocos individuais
    e chamado uma vez no final — evita commits parciais que corrompem a consistência
  - _pull_tabela(): timeout aumentado para 12s (redes universitárias são lentas)
  - enfileirar_log(): fallback seguro se disciplina_id=0 (não quebra o banco)
"""

import sqlite3
import json
import os
import logging
import requests
from datetime import datetime
from threading import Thread
from time import sleep
from dotenv import load_dotenv

from database import ENV_PATH
_ENV_PATH = ENV_PATH
load_dotenv(dotenv_path=_ENV_PATH, override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SYNC] %(levelname)s %(message)s",
)

# ── Caminho absoluto do banco ─────────────────────────────────────────────────
from database import DB_PATH
DB_LOCAL  = DB_PATH


# ──────────────────────────────────────────────────────────────────────────────
# CONEXÃO LOCAL
# ──────────────────────────────────────────────────────────────────────────────
def conectar_local():
    conn = sqlite3.connect(DB_LOCAL)
    conn.row_factory = sqlite3.Row
    return conn


def _headers():
    """Relê credenciais do .env a cada chamada — garante que mudanças são aplicadas."""
    load_dotenv(dotenv_path=_ENV_PATH, override=True)
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_KEY", "")
    return url, key, {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


# ──────────────────────────────────────────────────────────────────────────────
# INICIALIZAR FILA LOCAL
# ──────────────────────────────────────────────────────────────────────────────
def inicializar_fila_local():
    with conectar_local() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_queue (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                payload    TEXT    NOT NULL,
                tentativas INTEGER NOT NULL DEFAULT 0,
                enviado    INTEGER NOT NULL DEFAULT 0,
                criado_em  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()


# ──────────────────────────────────────────────────────────────────────────────
# PUSH: local → Supabase
# ──────────────────────────────────────────────────────────────────────────────
def enfileirar_sync(tabela: str, dados: dict):
    """Enfileira qualquer dado para envio ao Supabase."""
    pacote = {"tabela_destino": tabela, "dados": dados}
    try:
        with conectar_local() as conn:
            conn.execute(
                "INSERT INTO sync_queue (payload) VALUES (?)",
                (json.dumps(pacote),),
            )
            conn.commit()
        logging.info(f"Enfileirado para nuvem: tabela '{tabela}'")
    except Exception as exc:
        # CORREÇÃO: nunca deixar enfileiramento quebrar a thread principal
        logging.warning(f"Falha ao enfileirar '{tabela}': {exc}")


def enfileirar_log(ra_aluno: int, disciplina_id: int, tipo: str):
    disciplina_nome = ""

    # CORREÇÃO: só consulta se disciplina_id é válido
    if disciplina_id and disciplina_id > 0:
        try:
            with conectar_local() as conn:
                r = conn.execute(
                    "SELECT Nome_Materia||' - '||Semestre||' ('||Bloco||') - '||Professor_Nome "
                    "FROM DISCIPLINAS WHERE ID=?",
                    (disciplina_id,),
                ).fetchone()
                if r:
                    disciplina_nome = r[0]
        except Exception as exc:
            logging.warning(f"enfileirar_log: erro ao buscar disciplina {disciplina_id}: {exc}")

    agora = datetime.now()
    data  = agora.strftime("%d/%m/%Y")
    hora  = agora.strftime("%H:%M:%S")

    enfileirar_sync(
        "logs",
        {
            "ra_aluno":      ra_aluno,
            "disciplina":    disciplina_nome,
            "data":          data,
            "hora_entrada":  hora if tipo == "ENTRADA"    else None,
            "hora_saida":    hora if tipo == "SAIDA"      else None,
            "hora":          hora if tipo == "FALTA"      else None,
            "tipo":          tipo,
            "registrado_em": agora.isoformat(),
        },
    )


def _sincronizar():
    try:
        with conectar_local() as conn:
            pendentes = conn.execute(
                "SELECT * FROM sync_queue WHERE enviado=0 AND tentativas<5"
            ).fetchall()
    except Exception as exc:
        logging.warning(f"_sincronizar: erro ao ler fila local: {exc}")
        return

    if not pendentes:
        return

    url, key, hdrs = _headers()
    if not url or not key:
        return

    for item in pendentes:
        # CORREÇÃO: separar JSONDecodeError de outros erros de rede
        try:
            payload = json.loads(item["payload"])
        except (json.JSONDecodeError, KeyError) as exc:
            logging.error(f"Payload corrompido ID {item['id']}: {exc} — descartando.")
            with conectar_local() as conn:
                conn.execute("UPDATE sync_queue SET enviado=1 WHERE id=?", (item["id"],))
                conn.commit()
            continue

        tabela = payload.get("tabela_destino", "logs")
        dados  = payload.get("dados", payload)

        try:
            r = requests.post(
                f"{url}/rest/v1/{tabela}",
                json=dados,
                headers=hdrs,
                timeout=8,
            )
            if r.status_code in (200, 201, 204, 409):
                with conectar_local() as conn:
                    conn.execute(
                        "UPDATE sync_queue SET enviado=1 WHERE id=?", (item["id"],)
                    )
                    conn.commit()
                logging.info(f"Sincronizado ID {item['id']} ({tabela})")
            else:
                raise Exception(f"HTTP {r.status_code}: {r.text[:120]}")
        except Exception as exc:
            try:
                with conectar_local() as conn:
                    conn.execute(
                        "UPDATE sync_queue SET tentativas=tentativas+1 WHERE id=?",
                        (item["id"],),
                    )
                    conn.commit()
            except Exception as inner:
                logging.warning(f"Não foi possível atualizar tentativas ID {item['id']}: {inner}")
            logging.warning(f"Falha sync ID {item['id']}: {exc}")


def iniciar_thread_sync(intervalo_segundos: int = 15):
    def _loop():
        while True:
            try:
                _sincronizar()
            except Exception as exc:
                # CORREÇÃO: garante que a thread NUNCA morre silenciosamente
                logging.error(f"Erro inesperado na thread de sync: {exc}")
            sleep(intervalo_segundos)

    t = Thread(target=_loop, daemon=True, name="SAPA-SyncPush")
    t.start()
    logging.info("Motor de sincronização PUSH iniciado.")


# ──────────────────────────────────────────────────────────────────────────────
# PULL: Supabase → SQLite local
# ──────────────────────────────────────────────────────────────────────────────
def _pull_tabela(url: str, hdrs: dict, endpoint: str, params: dict = None, limit: int = 1000):
    """
    Baixa até `limit` registros de uma tabela do Supabase.
    CORREÇÃO: parâmetros de query passados via dict (não concatenados na URL),
    evitando URLs mal-formadas no pull de logs com filtro 'id=gt.X'.
    """
    _params = {"limit": limit}
    if params:
        _params.update(params)
    try:
        r = requests.get(
            f"{url}/rest/v1/{endpoint}",
            headers=hdrs,
            params=_params,
            timeout=12,          # CORREÇÃO: 12s (redes universitárias lentas)
        )
        if r.status_code == 200:
            return r.json()
        logging.warning(f"PULL {endpoint}: HTTP {r.status_code}")
    except Exception as exc:
        logging.warning(f"PULL {endpoint} falhou: {exc}")
    return []


def sincronizar_do_supabase():
    """
    Baixa do Supabase e insere localmente tudo que não existe ainda.
    Seguro para rodar sempre que o programa abre.
    """
    url, key, hdrs = _headers()
    if not url or not key:
        logging.info("PULL ignorado: Supabase não configurado.")
        return

    logging.info("Iniciando PULL do Supabase → SQLite local...")
    erros = 0

    with conectar_local() as conn:

        # ── 1. ALUNOS ─────────────────────────────────────────────────────────
        alunos = _pull_tabela(url, hdrs, "alunos")
        inseridos = 0
        for a in alunos:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO ALUNOS (RA, Nome, Turma) VALUES (?,?,?)",
                    (a.get("ra"), a.get("nome", ""), a.get("turma", "")),
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inseridos += 1
            except Exception as exc:
                erros += 1
                logging.warning(f"PULL aluno {a.get('ra')}: {exc}")
        logging.info(f"Alunos: {inseridos} novos de {len(alunos)} na nuvem")

        # ── 2. PROFESSORES ────────────────────────────────────────────────────
        profs = _pull_tabela(url, hdrs, "professores")
        inseridos = 0
        for p in profs:
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO PROFESSORES
                    (Nome_Professor, Email, Telefone, senha_hash)
                    VALUES (?,?,?,?)
                    """,
                    (
                        p.get("nome_professor", ""),
                        p.get("email", ""),
                        p.get("telefone", ""),
                        p.get("senha_hash", ""),
                    ),
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inseridos += 1
            except Exception as exc:
                erros += 1
                logging.warning(f"PULL professor {p.get('nome_professor')}: {exc}")
        logging.info(f"Professores: {inseridos} novos de {len(profs)} na nuvem")

        # ── 3. DISCIPLINAS ────────────────────────────────────────────────────
        discs = _pull_tabela(url, hdrs, "disciplinas")
        id_map_disc: dict[int, int] = {}
        inseridos = 0
        for d in discs:
            try:
                existe = conn.execute(
                    """
                    SELECT ID FROM DISCIPLINAS
                    WHERE Nome_Materia=? AND Professor_Nome=?
                      AND Semestre=? AND Bloco=?
                    """,
                    (
                        d.get("nome_materia", ""),
                        d.get("professor_nome", ""),
                        d.get("semestre", ""),
                        d.get("bloco", ""),
                    ),
                ).fetchone()
                if existe:
                    id_map_disc[d.get("id")] = existe[0]
                else:
                    cursor = conn.execute(
                        """
                        INSERT INTO DISCIPLINAS
                        (Nome_Materia, Professor_Nome, Semestre, Bloco,
                         Data_Inicio, Data_Fim, Dia_Semana)
                        VALUES (?,?,?,?,?,?,?)
                        """,
                        (
                            d.get("nome_materia", ""),
                            d.get("professor_nome", ""),
                            d.get("semestre", ""),
                            d.get("bloco", ""),
                            d.get("data_inicio", ""),
                            d.get("data_fim", ""),
                            d.get("dia_semana", ""),
                        ),
                    )
                    id_map_disc[d.get("id")] = cursor.lastrowid
                    inseridos += 1
            except Exception as exc:
                erros += 1
                logging.warning(f"PULL disciplina {d.get('nome_materia')}: {exc}")
        logging.info(f"Disciplinas: {inseridos} novas de {len(discs)} na nuvem")

        # ── 4. GRADE DE HORÁRIOS ──────────────────────────────────────────────
        grade = _pull_tabela(url, hdrs, "grade_horarios")
        inseridos = 0
        for g in grade:
            try:
                disc_id_local = id_map_disc.get(g.get("disciplina_id"))
                if not disc_id_local:
                    continue
                existe = conn.execute(
                    """
                    SELECT id FROM grade_horarios
                    WHERE disciplina_id=? AND dia_semana=?
                      AND hora_inicio=? AND turma=?
                    """,
                    (
                        disc_id_local,
                        g.get("dia_semana"),
                        g.get("hora_inicio", ""),
                        g.get("turma", ""),
                    ),
                ).fetchone()
                if not existe:
                    conn.execute(
                        """
                        INSERT INTO grade_horarios
                        (disciplina_id, dia_semana, hora_inicio, hora_fim, turma)
                        VALUES (?,?,?,?,?)
                        """,
                        (
                            disc_id_local,
                            g.get("dia_semana"),
                            g.get("hora_inicio", ""),
                            g.get("hora_fim", ""),
                            g.get("turma", ""),
                        ),
                    )
                    inseridos += 1
            except Exception as exc:
                erros += 1
                logging.warning(f"PULL grade {g}: {exc}")
        logging.info(f"Grade: {inseridos} novos de {len(grade)} na nuvem")

        # ── 5. LOGS ───────────────────────────────────────────────────────────
        # CORREÇÃO: filtro passado como parâmetro de query (não concatenado na URL)
        max_id_local = conn.execute(
            "SELECT COALESCE(MAX(ID),0) FROM LOGS"
        ).fetchone()[0]

        logs_nuvem = _pull_tabela(
            url, hdrs,
            "logs",
            params={"order": "id.asc", "id": f"gt.{max_id_local}"},
            limit=5000,
        )
        inseridos = 0
        for l in logs_nuvem:
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO LOGS
                    (RA_Aluno, Data, Hora, Hora_Entrada, Hora_Saida,
                     Disciplina, Tipo, Justificativa)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        l.get("ra_aluno"),
                        l.get("data", ""),
                        l.get("hora") or l.get("hora_entrada", ""),
                        l.get("hora_entrada", ""),
                        l.get("hora_saida"),
                        l.get("disciplina", ""),
                        l.get("tipo", "FALTA"),
                        l.get("justificativa"),
                    ),
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inseridos += 1
            except Exception as exc:
                erros += 1
                logging.warning(f"PULL log {l.get('id')}: {exc}")
        logging.info(f"Logs: {inseridos} novos de {len(logs_nuvem)} na nuvem")

        # CORREÇÃO: commit único ao final — garante consistência transacional
        conn.commit()

    if erros == 0:
        logging.info("✅ PULL concluído sem erros.")
    else:
        logging.warning(f"⚠️  PULL concluído com {erros} erro(s) — verifique os logs.")


def iniciar_pull_background():
    """
    Roda o pull em thread separada para não travar a abertura da UI.
    A UI abre imediatamente; os dados chegam em alguns segundos.
    """
    t = Thread(target=sincronizar_do_supabase, daemon=True, name="SAPA-PullInit")
    t.start()
