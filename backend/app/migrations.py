"""Migrações simples do SQLite.

`create_all` cria tabelas novas, mas não adiciona colunas a tabelas existentes. Cada item
abaixo adiciona uma coluna que ainda não existir, preservando os dados.
"""

from sqlalchemy import inspect, text

# (tabela, coluna, definição SQL)
COLUMNS = [
    # etapa 5: servidores que já existiam são os de demonstração -> simulados
    ("servers", "mode", "VARCHAR(10) NOT NULL DEFAULT 'simulated'"),
    ("servers", "last_report_at", "DATETIME"),
]


def upgrade(engine) -> list[str]:
    """Aplica o que faltar e devolve a lista do que foi feito."""
    done = []
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, column, ddl in COLUMNS:
            if not insp.has_table(table):
                continue  # tabela nova: create_all já cria com a coluna
            if column not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                done.append(f"{table}.{column}")
    return done
