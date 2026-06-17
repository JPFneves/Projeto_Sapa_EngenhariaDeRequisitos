from database import DB_PATH

def atualizar_horario():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE grade_horarios SET hora_fim = '22:00' WHERE hora_fim = '21:30'")
        conn.commit()
    print("Horário atualizado com sucesso!")

if __name__ == '__main__':
    atualizar_horario()
