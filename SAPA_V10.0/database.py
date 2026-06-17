"""
database.py — Criação e seed do banco SQLite local
SAPA v9.0 — Correções aplicadas:
  - Caminho absoluto do banco (evita bug de working directory)
  - Colunas faltantes adicionadas na criação (Hora_Entrada, Hora_Saida, Justificativa)
  - Coluna Justificativa garantida em LOGS
  - Tabela PROFESSORES com colunas Email / Telefone / senha_hash desde a criação
    (sync_manager tentava inserir essas colunas e falhava silenciosamente)
"""

import sqlite3
import os
import sys
import shutil

# ── Caminho absoluto dinâmico e seguro para escrita ───────────────────────────
def obter_caminho_banco():
    # Caminho padrão na pasta de dados do usuário (AppData/Roaming/SAPA)
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = os.path.expanduser("~")
    
    pasta_app = os.path.join(appdata, "SAPA")
    os.makedirs(pasta_app, exist_ok=True)
    db_appdata = os.path.join(pasta_app, "banco_sapa.db")
    
    # Caminho local ao lado do script/executável
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    if getattr(sys, 'frozen', False):
        diretorio_atual = os.path.dirname(sys.executable)
    db_local = os.path.join(diretorio_atual, "banco_sapa.db")
    
    # Se o banco local existir na pasta atual (desenvolvimento / portátil)
    if os.path.exists(db_local):
        # Testa se conseguimos escrever no arquivo local
        try:
            with open(db_local, 'a+b'):
                pass
            return db_local
        except (OSError, PermissionError):
            # Se não for gravável (ex: Program Files), copia para o AppData se ainda não existir lá
            if not os.path.exists(db_appdata):
                try:
                    shutil.copy2(db_local, db_appdata)
                except Exception:
                    pass
            return db_appdata
    else:
        # Se não existe banco local, usa diretamente o do AppData
        return db_appdata

DB_PATH = obter_caminho_banco()


def obter_caminho_env():
    # Pasta no AppData do usuário (AppData/Roaming/SAPA)
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = os.path.expanduser("~")
    
    pasta_app = os.path.join(appdata, "SAPA")
    os.makedirs(pasta_app, exist_ok=True)
    env_appdata = os.path.join(pasta_app, ".env")
    
    # Se o .env no AppData não existe, procuramos o empacotado para copiar
    if not os.path.exists(env_appdata):
        caminhos_busca = []
        
        # 1. Se estiver congelado pelo PyInstaller, busca na raiz do executável
        if getattr(sys, 'frozen', False):
            caminhos_busca.append(os.path.join(os.path.dirname(sys.executable), ".env"))
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                caminhos_busca.append(os.path.join(meipass, ".env"))
        
        # 2. Modo desenvolvimento (mesmo diretório deste script)
        caminhos_busca.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
        
        # Copia o primeiro que encontrar para o AppData
        for caminho in caminhos_busca:
            if os.path.exists(caminho):
                try:
                    shutil.copy2(caminho, env_appdata)
                    break
                except Exception:
                    pass
                    
    return env_appdata

ENV_PATH = obter_caminho_env()


def conectar():
    """Retorna conexão SQLite com row_factory configurada."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def resetar_banco():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("🗑️ Base de dados antiga removida.")

    with conectar() as conn:
        cursor = conn.cursor()

        # 1. Alunos
        cursor.execute(
            "CREATE TABLE ALUNOS ("
            "  RA INTEGER PRIMARY KEY,"
            "  Nome TEXT NOT NULL,"
            "  Turma TEXT"
            ")"
        )

        # 2. Professores — colunas extras desde o início
        cursor.execute(
            "CREATE TABLE PROFESSORES ("
            "  ID INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  Nome_Professor TEXT NOT NULL UNIQUE,"
            "  Email TEXT,"
            "  Telefone TEXT,"
            "  senha_hash TEXT"
            ")"
        )

        # 3. Disciplinas
        cursor.execute(
            "CREATE TABLE DISCIPLINAS ("
            "  ID INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  Nome_Materia TEXT,"
            "  Professor_Nome TEXT,"
            "  Semestre TEXT,"
            "  Bloco TEXT,"
            "  Data_Inicio TEXT,"
            "  Data_Fim TEXT,"
            "  Dia_Semana TEXT"
            ")"
        )

        # 4. LOGS — schema completo (registro único Entrada+Saída por linha)
        #    CORREÇÃO: Hora_Entrada, Hora_Saida e Justificativa presentes desde
        #    a criação, evitando o ALTER TABLE repetitivo a cada abertura.
        cursor.execute(
            """
            CREATE TABLE LOGS (
                ID            INTEGER PRIMARY KEY AUTOINCREMENT,
                RA_Aluno      INTEGER,
                Data          TEXT,
                Hora          TEXT,
                Hora_Entrada  TEXT,
                Hora_Saida    TEXT,
                Disciplina    TEXT,
                Tipo          TEXT,
                Justificativa TEXT,
                FOREIGN KEY (RA_Aluno) REFERENCES ALUNOS (RA)
            )
            """
        )

        # 5. Grade de horários
        cursor.execute(
            """
            CREATE TABLE grade_horarios (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                disciplina_id INTEGER,
                dia_semana    TEXT,    -- "Segunda-feira" … "Domingo" (padrão do calendar_engine)
                hora_inicio   TEXT,
                hora_fim      TEXT,
                turma         TEXT,
                FOREIGN KEY(disciplina_id) REFERENCES DISCIPLINAS(ID)
            )
            """
        )

        # 6. Fila de sincronização (criada aqui para garantir existência
        #    mesmo que o sync_manager não seja importado)
        cursor.execute(
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
        print("✅ Banco criado com schema completo.")


def inserir_alunos():
    with conectar() as conn:
        cursor = conn.cursor()
        cursor.executescript("""
        DELETE FROM ALUNOS WHERE RA = 15652;

        -- TURMA A
        INSERT OR IGNORE INTO ALUNOS (RA, Nome, Turma) VALUES
        (16152, 'Allan Victor Braga Dias', 'A'),
        (16304, 'Ana Livia Almeida Ramos', 'A'),
        (16182, 'Arthur Belotte Isensee', 'A'),
        (16203, 'Davi Mateus Miranda de Albuquerque', 'A'),
        (16183, 'Douglas Leonardo de Paiva Costa', 'A'),
        (16279, 'Joao Lucas Manoel Paes', 'A'),
        (16369, 'Joao Vitor Gadbem Silva', 'A'),
        (16191, 'Lemuel Baruc Silva Souza', 'A'),
        (16301, 'Lucas de Freitas Alves', 'A'),
        (16284, 'Maria Rita Chaves da Silva', 'A'),
        (16266, 'Thales Calheiros', 'A'),
        (16448, 'Yuri Neves Rocha Roque', 'A');

        -- TURMA B
        INSERT OR IGNORE INTO ALUNOS (RA, Nome, Turma) VALUES
        (16067, 'Ana Carolina Valim Faria', 'B'),
        (15903, 'Benaiah James Putz', 'B'),
        (15811, 'Carlos Alexandre Bastos Xavier', 'B'),
        (15793, 'Gabriel Augusto de Assis Bonifacio', 'B'),
        (15833, 'Gabriel Lucas da Silva Oliveira', 'B'),
        (16080, 'Gabriel Miguel Cordeiro', 'B'),
        (15712, 'Guilherme Augusto Moreira Fedrizzi', 'B'),
        (15652, 'Joao Pedro Faria das Neves da Silva', 'B'),
        (15987, 'Kauan Felipe de Faria', 'B'),
        (15809, 'Lucas Amaro Ribeiro e Silva', 'B'),
        (16061, 'Lucas Eliziario Silva Marques', 'B'),
        (15704, 'Luis Gustavo Bonifacio', 'B'),
        (16035, 'Matheus Lopes Dias Claudino', 'B'),
        (16017, 'Nalberto Pereira Jesus', 'B'),
        (15888, 'Naomi Marra Marcondes Ribeiro', 'B'),
        (15805, 'Otavio Henrique Bastos de Souza', 'B'),
        (15964, 'Vicente Augusto Ribeiro Rosa', 'B'),
        (15650, 'Washington Vicente da Silva', 'B'),
        (15947, 'Wesley Jesus de Souza Campos', 'B');

        -- TURMA C
        INSERT OR IGNORE INTO ALUNOS (RA, Nome, Turma) VALUES
        (15313, 'Lucas Lima Barboza', 'C'),
        (15482, 'Bruno Alexandre de Oliveira', 'C'),
        (15568, 'Davi Rodarte de Souza Junior', 'C'),
        (15421, 'Gustavo da Silva Carvalho', 'C'),
        (15312, 'Gustavo Moreira da Silva', 'C'),
        (15390, 'Gustavo Souza Silva', 'C'),
        (15370, 'Hugo Andre Castor Silva', 'C'),
        (15426, 'Joao David Cattermol Cabizuca', 'C'),
        (15565, 'Jose Pedro Silverio Assis', 'C'),
        (11868, 'Jose Vagner Pereira Junior', 'C'),
        (15294, 'Karla Rodrigues de Sousa', 'C'),
        (15280, 'Mateus Henrique Delfino', 'C'),
        (9053,  'Pedro Vilela Maciel', 'C'),
        (15140, 'Raquel Taveira de Oliveira', 'C');
        """)
        conn.commit()
        print("✅ Alunos inseridos com sucesso!")


if __name__ == "__main__":
    resetar_banco()
    inserir_alunos()
