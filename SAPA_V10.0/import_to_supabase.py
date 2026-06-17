import sqlite3
import requests
import json
import os
import sys

# Change to the v7.0 directory to ensure imports and DB paths work correctly
os.chdir(r"c:\Users\aluno\Downloads\SAPA_v7.0")

from sync_manager import _headers, conectar_local

def run_import():
    url, key, hdrs = _headers()
    if not url or not key:
        print("Erro: Credenciais do Supabase não encontradas no .env!")
        sys.exit(1)

    # Allow partial successes and ignore duplicates (upsert)
    hdrs["Prefer"] = "resolution=ignore-duplicates"

    def push_table(table_name, supabase_table):
        with conectar_local() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()

        if not rows:
            print(f"Tabela local {table_name} está vazia. Pulando.")
            return

        data = [dict(row) for row in rows]

        # Mapeamento e sanitização para schema do Supabase
        formatted_data = []
        if table_name == 'LOGS':
            for d in data:
                # Resolve Nome da Disciplina se for int (bug antigo) ou pega o atual
                disciplina = str(d.get("Disciplina", ""))
                formatted_data.append({
                    "ra_aluno": d.get("RA_Aluno"),
                    "disciplina": disciplina,
                    "data": d.get("Data", ""),
                    "hora_entrada": d.get("Hora_Entrada"),
                    "hora_saida": d.get("Hora_Saida"),
                    "hora": d.get("Hora"),
                    "tipo": d.get("Tipo"),
                    "justificativa": d.get("Justificativa")
                })
        elif table_name == 'ALUNOS':
            for d in data:
                formatted_data.append({
                    "ra": d.get("RA"),
                    "nome": d.get("Nome"),
                    "turma": d.get("Turma")
                })
        elif table_name == 'PROFESSORES':
            for d in data:
                formatted_data.append({
                    "nome_professor": d.get("Nome_Professor"),
                    "email": d.get("Email")
                })
        elif table_name == 'DISCIPLINAS':
            for d in data:
                formatted_data.append({
                    "nome_materia": d.get("Nome_Materia"),
                    "semestre": d.get("Semestre"),
                    "bloco": d.get("Bloco"),
                    "professor_nome": d.get("Professor_Nome"),
                    "dia_semana": d.get("Dia_Semana"),
                    "data_inicio": d.get("Data_Inicio", ""),
                    "data_fim": d.get("Data_Fim", "")
                })

        # Batch insert into Supabase handling conflicts
        # Identify conflict columns
        conflict_col = ""
        if supabase_table == "alunos": conflict_col = "?on_conflict=ra"
        elif supabase_table == "professores": conflict_col = "?on_conflict=nome_professor"

        # We push row by row to handle duplicates individually if bulk fails
        sucesso = 0
        for item in formatted_data:
            # We omit conflict_col because sometimes the unique constraint is not on the column we think.
            # Just push one by one and ignore 409
            r = requests.post(f"{url}/rest/v1/{supabase_table}", json=item, headers=hdrs)
            if r.status_code in [200, 201, 204]:
                sucesso += 1
            elif r.status_code != 409:
                print(f"❌ Erro na tabela '{supabase_table}': {r.text}")

        print(f"✅ Concluído: {sucesso} registros novos importados para '{supabase_table}' (duplicados ignorados).")

    print("Iniciando importação em massa para o Supabase...")
    push_table("ALUNOS", "alunos")
    push_table("PROFESSORES", "professores")
    push_table("DISCIPLINAS", "disciplinas")
    push_table("LOGS", "logs")

    # Limpar a fila de sync que estava com payloads inválidos antigos
    with conectar_local() as conn:
        conn.execute("DELETE FROM sync_queue WHERE enviado=0")
        conn.commit()
    print("🧹 Fila de sincronização (sync_queue) limpada para evitar erros repetidos.")

if __name__ == "__main__":
    run_import()
