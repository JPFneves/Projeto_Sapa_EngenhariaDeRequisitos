"""
auth.py — Autenticação de professores via bcrypt
SAPA v9.0 — Correções aplicadas:
  - conectar() → usa DB_PATH absoluto de database.py (bug crítico)
  - verificar_login(): bloco try/except em torno da conexão ao banco
    (banco ausente não trava o login com backdoor do .env)
  - verificar_login(): retorna False explicitamente em caso de erro,
    sem propagar exceção para a UI
"""

import sqlite3
import bcrypt

from database import DB_PATH   # ← caminho absoluto (CORREÇÃO CRÍTICA)


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def gerar_hash(senha: str) -> str:
    """Retorna bcrypt hash da senha."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_login(email: str, senha_digitada: str) -> bool:
    """
    Verifica se as credenciais batem com um professor no banco.
    Retorna False silenciosamente em caso de erro (banco ausente, etc.)
    para não travar o fluxo de login que tem backdoor via .env.
    """
    if not email or not senha_digitada:
        return False

    try:
        with conectar() as conn:
            prof = conn.execute(
                "SELECT senha_hash FROM PROFESSORES WHERE Email = ?", (email,)
            ).fetchone()
    except Exception:
        # Banco ausente ou inacessível — login via .env ainda funciona
        return False

    if not prof or not prof["senha_hash"]:
        return False

    try:
        return bcrypt.checkpw(
            senha_digitada.encode("utf-8"),
            prof["senha_hash"].encode("utf-8")
        )
    except ValueError:
        # Hash antigo em texto puro (senha temporária) — comparação direta
        return senha_digitada == prof["senha_hash"]
    except Exception:
        return False
