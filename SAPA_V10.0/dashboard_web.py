import os
import sqlite3
import pandas as pd
from flask import Flask, jsonify, request, send_file, render_template_string
from io import StringIO, BytesIO

app = Flask(__name__)

# Caminho do banco atual do projeto SAPA
from database import DB_PATH

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def extract_disciplina_info(disciplina_str):
    """
    Ex: 'ALGORITMO E LOGICA DE PROGRAMACAO - 1 SEMESTRE (BLOCO A) - PROFESSOR JOAO'
    Tenta extrair as partes. Se não conseguir, retorna dicionário padrão.
    """
    try:
        if not disciplina_str: return {"materia": "", "semestre": "", "bloco": "", "prof": ""}
        parts = disciplina_str.split(' - ')
        materia = parts[0]
        # parts[1] tem "1 SEMESTRE (BLOCO A)"
        sem_bloco = parts[1]
        semestre = sem_bloco.split(' (')[0]
        bloco = sem_bloco.split('(')[1].replace(')', '') if '(' in sem_bloco else ""
        prof = parts[2] if len(parts) > 2 else ""
        return {"materia": materia, "semestre": semestre, "bloco": bloco, "prof": prof}
    except Exception:
        return {"materia": str(disciplina_str), "semestre": "", "bloco": "", "prof": ""}

def get_dataframe():
    """Gera o dataframe consolidado (Achatado/Flat) para o Dashboard e Power BI"""
    query = """
        SELECT
            l.ID as Log_ID,
            l.Data,
            l.Hora_Entrada,
            l.Hora_Saida,
            l.Disciplina as Disciplina_Completa,
            l.Tipo as Status,
            l.Justificativa,
            a.RA,
            a.Nome as Aluno_Nome,
            a.Turma
        FROM LOGS l
        LEFT JOIN ALUNOS a ON l.RA_Aluno = a.RA
    """
    with get_db_connection() as conn:
        df = pd.read_sql_query(query, conn)

    if df.empty:
        return df

    # Enriquecimento dos dados
    # Converter 'Data' (DD/MM/YYYY) para datetime
    df['Data_Obj'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
    df['Mes'] = df['Data_Obj'].dt.strftime('%m/%Y')
    df['Dia_Semana'] = df['Data_Obj'].dt.day_name(locale='pt_BR.utf8') # ou apenas dt.day_name() e mapear

    # Mapear dias da semana manualmente para evitar problemas de locale no Windows
    dias_map = {
        'Monday': 'Segunda-feira', 'Tuesday': 'Terça-feira', 'Wednesday': 'Quarta-feira',
        'Thursday': 'Quinta-feira', 'Friday': 'Sexta-feira', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    df['Dia_Semana'] = df['Data_Obj'].dt.day_name().map(dias_map)

    # Extrair campos da Disciplina
    infos = df['Disciplina_Completa'].apply(extract_disciplina_info)
    df['Materia'] = infos.apply(lambda x: x['materia'])
    df['Semestre'] = infos.apply(lambda x: x['semestre'])
    df['Bloco'] = infos.apply(lambda x: x['bloco'])
    df['Professor'] = infos.apply(lambda x: x['prof'])

    # Inferir Período pela Turma
    def inferir_periodo(turma):
        t = str(turma).upper()
        if ' - A' in t: return '1º/2º Período'
        if ' - B' in t: return '3º/4º Período'
        if ' - C' in t: return '5º/6º Período'
        return 'Outro'

    df['Periodo_Inferido'] = df['Turma'].apply(inferir_periodo)

    return df

@app.route('/')
def dashboard():
    # Retorna o HTML que vamos criar logo a seguir
    return send_file(os.path.join(BASE_DIR, 'templates', 'dashboard.html'))

@app.route('/static/<path:path>')
def send_static(path):
    return send_file(os.path.join(BASE_DIR, 'static', path))

@app.route('/api/dados_dashboard')
def dados_dashboard():
    df = get_dataframe()
    if df.empty:
        return jsonify({"vazio": True})

    # 1. Faltas Mensais
    df_faltas = df[df['Status'] == 'FALTA']
    faltas_mensais = df_faltas.groupby('Mes').size().to_dict() if not df_faltas.empty else {}

    # 2. Faltas por Disciplina
    faltas_disciplina = df_faltas.groupby('Materia').size().sort_values(ascending=False).head(5).to_dict() if not df_faltas.empty else {}

    # 3. Faltas por Professor
    faltas_professor = df_faltas.groupby('Professor').size().to_dict() if not df_faltas.empty else {}

    # 4. Faltas por Turma/Periodo
    faltas_turma = df_faltas.groupby('Periodo_Inferido').size().to_dict() if not df_faltas.empty else {}

    # 5. Dia da semana com mais faltas
    faltas_dias = df_faltas.groupby('Dia_Semana').size().to_dict() if not df_faltas.empty else {}

    # KPIs Gerais
    total_logs = len(df)
    total_faltas = len(df_faltas)
    taxa_ausencia = round((total_faltas / total_logs * 100), 1) if total_logs > 0 else 0

    return jsonify({
        "vazio": False,
        "kpis": {
            "total_registros": int(total_logs),
            "total_faltas": int(total_faltas),
            "taxa_ausencia": float(taxa_ausencia)
        },
        "graficos": {
            "faltas_mensais": faltas_mensais,
            "faltas_disciplina": faltas_disciplina,
            "faltas_professor": faltas_professor,
            "faltas_turma": faltas_turma,
            "faltas_dias": faltas_dias
        }
    })

@app.route('/api/exportar_powerbi')
def exportar_powerbi():
    df = get_dataframe()
    if df.empty:
        return jsonify({"error": "Nenhum dado encontrado"}), 404

    # Organizar as colunas pro Power BI
    colunas_export = [
        'Log_ID', 'RA', 'Aluno_Nome', 'Turma', 'Periodo_Inferido',
        'Data', 'Dia_Semana', 'Mes', 'Hora_Entrada', 'Hora_Saida',
        'Materia', 'Professor', 'Semestre', 'Bloco',
        'Status', 'Justificativa'
    ]
    df_export = df[colunas_export]

    # Converter para CSV
    csv_buffer = StringIO()
    csv_buffer.write('\ufeff') # BOM para o Excel não quebrar acentos
    df_export.to_csv(csv_buffer, index=False, sep=';', encoding='utf-8')

    mem = BytesIO()
    mem.write(csv_buffer.getvalue().encode('utf-8'))
    mem.seek(0)

    return send_file(
        mem,
        mimetype='text/csv',
        as_attachment=True,
        download_name='sapa_powerbi_dataset.csv'
    )

if __name__ == '__main__':
    print("Iniciando Dashboard Web SAPA na porta 5000...")

    # Inicia o tunel do Ngrok automaticamente
    try:
        from pyngrok import ngrok
        # Abre o tunel na porta 5000
        public_url = ngrok.connect("5000").public_url
        print(f"\n" + "="*60)
        print(f"SEU PAINEL ONLINE ESTA PRONTO!")
        print(f"Acesse de qualquer rede/celular: {public_url}")
        print("="*60 + "\n")
    except Exception as e:
        print(f"Nao foi possivel iniciar o Ngrok automaticamente: {e}")
        print(f"O painel ficara disponivel apenas localmente em http://127.0.0.1:5000")

    app.run(host='0.0.0.0', port=5000, debug=False)

