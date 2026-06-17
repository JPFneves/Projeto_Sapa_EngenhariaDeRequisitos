from database import DB_PATH

def conectar():
    return sqlite3.connect(DB_PATH)

def cadastrar_aluno():
    try:
        ra = int(input("Digite o RA do aluno: "))
        nome = input("Digite o NOME COMPLETO do aluno: ")
        turma = input("Digite a TURMA (ex: ADS 3 SEM - A): ")

        # O 'with' abre e fecha o banco com segurança automática
        with conectar() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO ALUNOS (RA, Nome, Turma) VALUES (?, ?, ?)",
                (ra, nome, turma)
            )
            conn.commit()
            print(f"✅ Aluno {nome} cadastrado com sucesso na turma {turma}!")

    except sqlite3.IntegrityError:
        print("❌ Erro: Já existe um aluno cadastrado com esse RA!")

    except ValueError:
        print("❌ Erro: O RA precisa ser apenas números!")

if __name__ == "__main__":
    cadastrar_aluno()