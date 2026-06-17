import sqlite3
from datetime import datetime
from database import DB_PATH

def limpar_dados():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT ID, Data FROM LOGS").fetchall()
        to_delete = []
        for r in rows:
            try:
                dt = datetime.strptime(r[1], '%d/%m/%Y')
                if dt < datetime(2026, 5, 27):
                    to_delete.append(str(r[0]))
            except:
                pass

        if to_delete:
            conn.execute(f"DELETE FROM LOGS WHERE ID IN ({','.join(to_delete)})")
            conn.commit()
            print(f"Deletados {len(to_delete)} registros anteriores a 27/05/2026.")
        else:
            print("Nenhum registro anterior a 27/05/2026 encontrado.")

if __name__ == '__main__':
    limpar_dados()
