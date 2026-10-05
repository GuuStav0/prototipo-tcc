"""Cria as tabelas e cadastra os servidores de demonstração e as regras padrão.

Uso:  python -m app.seed           (só insere o que ainda não existe)
      python -m app.seed --reset   (apaga o banco e recomeça)
"""

import sys

from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import Server, Trigger

# Os mesmos servidores do mock do front-end (src/data/mockData.js)
SERVERS = [
    ("srv-web-01", "Web / Nginx", "Ubuntu 22.04", "10.0.4.11"),
    ("srv-web-02", "Web / Nginx", "Ubuntu 22.04", "10.0.4.12"),
    ("srv-db-01", "Banco / PostgreSQL", "Debian 12", "10.0.2.21"),
    ("srv-db-02", "Banco / MySQL", "Debian 12", "10.0.2.22"),
    ("srv-app-01", "API Gateway", "Ubuntu 22.04", "10.0.3.31"),
    ("srv-app-02", "API Gateway", "Ubuntu 22.04", "10.0.3.32"),
    ("srv-cache-01", "Cache / Redis", "Alpine 3.19", "10.0.5.41"),
    ("srv-backup-01", "Backup / Bacula", "CentOS 9", "10.0.6.51"),
    ("srv-mail-01", "E-mail / Postfix", "Debian 12", "10.0.7.61"),
    ("srv-monitor-01", "Coletor SNMP", "Ubuntu 22.04", "10.0.1.10"),
]

# Regras padrão (explicacao-contrato.txt, seção 6.3)
TRIGGERS = [
    dict(name="CPU elevada", metric="cpu", operator="gt",
         warning_threshold=80, critical_threshold=90, duration_seconds=60,
         description="Uso médio de CPU acima do limite."),
    dict(name="Memória elevada", metric="ram", operator="gt",
         warning_threshold=80, critical_threshold=90, duration_seconds=60,
         description="Uso de memória acima do limite."),
    dict(name="Disco quase cheio", metric="disk", operator="gt",
         warning_threshold=85, critical_threshold=95, duration_seconds=60,
         description="Partição mais cheia acima do limite."),
    dict(name="Temperatura elevada", metric="temp", operator="gt",
         warning_threshold=65, critical_threshold=75, duration_seconds=60,
         description="Maior temperatura entre os sensores acima do limite."),
    dict(name="Host inalcançável", metric="reachable", operator="lt",
         warning_threshold=None, critical_threshold=1, duration_seconds=45,
         description="O servidor não respondeu à coleta."),
]


def seed(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        existing = set(db.scalars(select(Server.id)))
        for sid, role, os_, ip in SERVERS:
            if sid not in existing:
                db.add(Server(id=sid, name=sid, address=ip, role=role, os=os_,
                              snmp_community="public"))
        names = set(db.scalars(select(Trigger.name).where(Trigger.host_id.is_(None))))
        for t in TRIGGERS:
            if t["name"] not in names:
                db.add(Trigger(**t))
        db.commit()
        print(f"{db.query(Server).count()} servidores, {db.query(Trigger).count()} regras.")


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
