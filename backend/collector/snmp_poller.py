"""Coletor SNMP do SMI (TCC 2.3.1 e 4.3: polling periódico).

A cada 15 s consulta, em paralelo, todos os servidores reais com coleta SNMP ativa e envia as
leituras para POST /ingest/metrics (source "snmp"), o mesmo caminho do agente e do simulador.

Roda na mesma máquina do backend: lê a lista de servidores e as credenciais SNMP direto do banco
(as credenciais nunca saem pela API).

Uso (na pasta backend):
    .venv\\Scripts\\python -m collector.snmp_poller                  # coleta contínua
    .venv\\Scripts\\python -m collector.snmp_poller --test vps-01    # uma consulta, só mostra (não envia)

OIDs usados (explicacao-contrato.txt, seção 5.3):
    CPU          HOST-RESOURCES-MIB hrProcessorLoad          1.3.6.1.2.1.25.3.3.1.2  (média dos núcleos)
    Memória      UCD-SNMP-MIB memTotalReal/memAvailReal/     1.3.6.1.4.1.2021.4.{5,6,14,15}.0
                 memBuffer/memCached (Linux; senão hrStorageRam)
    Disco        HOST-RESOURCES-MIB hrStorageTable           1.3.6.1.2.1.25.2.3.1    (partição mais cheia)
    Temperatura  LM-SENSORS-MIB lmTempSensorsValue           1.3.6.1.4.1.2021.13.16.2.1.3 (milésimos de °C)
    Uptime       HOST-RESOURCES-MIB hrSystemUptime           1.3.6.1.2.1.25.1.1.0    (centésimos de s)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from pysnmp.hlapi.v3arch.asyncio import (
    USM_AUTH_HMAC96_SHA,
    USM_PRIV_CFB128_AES,
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    get_cmd,
    walk_cmd,
)

log = logging.getLogger("smi.snmp")

OID_CPU = "1.3.6.1.2.1.25.3.3.1.2"
OID_MEM = {"total": "1.3.6.1.4.1.2021.4.5.0", "free": "1.3.6.1.4.1.2021.4.6.0",
           "buffer": "1.3.6.1.4.1.2021.4.14.0", "cached": "1.3.6.1.4.1.2021.4.15.0"}
OID_UPTIME = "1.3.6.1.2.1.25.1.1.0"
OID_STORAGE = "1.3.6.1.2.1.25.2.3.1"  # .2 tipo, .3 descrição, .4 unidade, .5 tamanho, .6 usado
OID_TEMP = "1.3.6.1.4.1.2021.13.16.2.1.3"
HR_STORAGE_RAM = "1.3.6.1.2.1.25.2.1.2"
HR_STORAGE_FIXED_DISK = "1.3.6.1.2.1.25.2.1.4"
SKIP_MOUNTS = ("/snap", "/boot/efi", "/run", "/dev", "/sys", "/proc")

TIMEOUT_S = 2
RETRIES = 1
# Contexto SNMPv3. O snmpd do Linux usa o contexto vazio (padrão); só simuladores precisam disto.
CONTEXT_NAME = os.environ.get("SMI_SNMP_CONTEXT", "")


class SnmpFailure(Exception):
    pass


# ---------------------------------------------------------------- cálculos (sem rede, testáveis)
def cpu_percent(loads: list[int]) -> float | None:
    return round(sum(loads) / len(loads), 1) if loads else None


def ram_percent_ucd(total: int | None, free: int | None, buffer: int | None, cached: int | None) -> float | None:
    """memAvailReal é a memória LIVRE; buffers e cache são liberáveis e não contam como uso."""
    if not total or free is None:
        return None
    used = total - free - (buffer or 0) - (cached or 0)
    return round(max(0.0, min(100.0, used / total * 100)), 1)


def storage_rows(table: dict[str, object]) -> list[dict]:
    """Converte o walk da hrStorageTable em linhas {tipo, descricao, unidade, tamanho, usado}."""
    cols = {"2": "type", "3": "descr", "4": "units", "5": "size", "6": "used"}
    rows: dict[str, dict] = {}
    for oid, value in table.items():
        rest = oid[len(OID_STORAGE) + 1:]  # "<coluna>.<índice>"
        col, _, idx = rest.partition(".")
        if col in cols and idx:
            rows.setdefault(idx, {})[cols[col]] = value
    return list(rows.values())


def ram_percent_hr(rows: list[dict]) -> float | None:
    for r in rows:
        if str(r.get("type")) == HR_STORAGE_RAM and int(r.get("size") or 0) > 0:
            return round(int(r["used"]) / int(r["size"]) * 100, 1)
    return None


def disk_percent(rows: list[dict]) -> float | None:
    worst = None
    for r in rows:
        if str(r.get("type")) != HR_STORAGE_FIXED_DISK or int(r.get("size") or 0) <= 0:
            continue
        if str(r.get("descr", "")).startswith(SKIP_MOUNTS):
            continue
        pct = int(r["used"]) / int(r["size"]) * 100
        worst = pct if worst is None else max(worst, pct)
    return round(worst, 1) if worst is not None else None


def temperature(millidegrees: list[int]) -> float | None:
    values = [v / 1000 for v in millidegrees if 0 < v / 1000 < 150]
    return round(max(values), 1) if values else None


# ---------------------------------------------------------------- SNMP
def _auth(server) -> CommunityData | UsmUserData:
    if server.snmp_version == "v3":
        return UsmUserData(server.snmp_username or "", authKey=server.snmp_auth_password,
                           privKey=server.snmp_priv_password,
                           authProtocol=USM_AUTH_HMAC96_SHA, privProtocol=USM_PRIV_CFB128_AES)
    return CommunityData(server.snmp_community or "public", mpModel=1)  # v2c


def _int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None  # noSuchObject / noSuchInstance


@dataclass
class Target:
    engine: SnmpEngine
    auth: object
    transport: object

    async def get(self, *oids: str) -> list:
        err_ind, err_stat, err_idx, binds = await get_cmd(
            self.engine, self.auth, self.transport, ContextData(contextName=CONTEXT_NAME),
            *[ObjectType(ObjectIdentity(o)) for o in oids], lookupMib=False)
        if err_ind:
            raise SnmpFailure(str(err_ind))
        if err_stat:
            raise SnmpFailure(err_stat.prettyPrint())
        return [v for _, v in binds]

    async def walk(self, oid: str) -> dict[str, object]:
        out: dict[str, object] = {}
        async for err_ind, err_stat, _, binds in walk_cmd(
                self.engine, self.auth, self.transport, ContextData(contextName=CONTEXT_NAME), ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False, lookupMib=False):
            if err_ind:
                raise SnmpFailure(str(err_ind))
            if err_stat:
                raise SnmpFailure(err_stat.prettyPrint())
            for name, value in binds:
                out[str(name)] = value
        return out


async def poll(engine: SnmpEngine, server) -> tuple[list[tuple[str, float]], float]:
    """Consulta um servidor. Devolve (leituras, tempo em ms). Sem resposta: reachable=0."""
    started = time.perf_counter()
    try:
        transport = await UdpTransportTarget.create((server.address, server.snmp_port),
                                                    timeout=TIMEOUT_S, retries=RETRIES)
        t = Target(engine, _auth(server), transport)
        uptime = _int((await t.get(OID_UPTIME))[0])  # também serve de teste de alcance
    except SnmpFailure as exc:
        log.warning("%s: sem resposta SNMP (%s)", server.id, exc)
        return [("reachable", 0)], (time.perf_counter() - started) * 1000
    except OSError as exc:
        log.warning("%s: endereço inválido ou rede indisponível (%s)", server.id, exc)
        return [("reachable", 0)], (time.perf_counter() - started) * 1000

    readings: list[tuple[str, float]] = [("reachable", 1)]
    if uptime is not None:
        readings.append(("uptime", uptime // 100))

    async def optional(name, coro):
        try:
            return await coro
        except SnmpFailure as exc:
            log.debug("%s: %s indisponível (%s)", server.id, name, exc)
            return None

    loads, mem, storage, temps = await asyncio.gather(
        optional("cpu", t.walk(OID_CPU)),
        optional("memória", t.get(*OID_MEM.values())),
        optional("disco", t.walk(OID_STORAGE)),
        optional("temperatura", t.walk(OID_TEMP)),
    )
    rows = storage_rows(storage or {})
    cpu = cpu_percent([v for v in (_int(x) for x in (loads or {}).values()) if v is not None])
    ram = ram_percent_ucd(*[_int(v) for v in mem]) if mem else None
    if ram is None:
        ram = ram_percent_hr(rows)  # sem UCD-SNMP-MIB (ex.: Windows)
    disk = disk_percent(rows)
    temp = temperature([v for v in (_int(x) for x in (temps or {}).values()) if v is not None])
    for metric, value in (("cpu", cpu), ("ram", ram), ("disk", disk), ("temp", temp)):
        if value is not None:
            readings.append((metric, value))
    return readings, (time.perf_counter() - started) * 1000


# ---------------------------------------------------------------- laço principal
def load_servers(only: str | None = None) -> list:
    from sqlalchemy import select

    from app.database import SessionLocal
    from app.models import Server

    with SessionLocal() as db:
        q = select(Server).where(Server.mode == "real", Server.enabled.is_(True), Server.snmp_enabled.is_(True))
        if only:
            q = select(Server).where(Server.id == only)
        servers = db.scalars(q).all()
        db.expunge_all()
        return list(servers)


async def cycle(engine: SnmpEngine, client: httpx.AsyncClient | None, servers: list) -> None:
    at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    results = await asyncio.gather(*(poll(engine, s) for s in servers))
    samples = []
    for s, (readings, ms) in zip(servers, results):
        summary = ", ".join(f"{m}={v}" for m, v in readings if m != "uptime")
        log.info("%s (%.0f ms): %s", s.id, ms, summary)
        samples += [{"host_id": s.id, "metric": m, "value": v, "collected_at": at} for m, v in readings]
    if client is None or not samples:
        return
    try:
        r = await client.post("ingest/metrics", json={"source": "snmp", "collector_id": "snmp-poller", "samples": samples})
        if r.status_code != 202:
            log.error("API recusou o lote (%d): %s", r.status_code, r.text[:300])
        else:
            for item in r.json()["rejected"][:3]:
                log.warning("leitura recusada: %s", item["reason"])
    except httpx.HTTPError as exc:
        log.error("API inacessível: %s", exc)


async def main_async(args) -> None:
    from app.config import get_settings

    settings = get_settings()
    engine = SnmpEngine()
    if args.test:
        servers = load_servers(args.test)
        if not servers:
            sys.exit(f"servidor '{args.test}' não encontrado")
        if not servers[0].snmp_enabled:
            sys.exit(f"a coleta SNMP está desativada no cadastro de '{args.test}'")
        await cycle(engine, None, servers)
        return

    log.info("coletor SNMP: a cada %d s, enviando para %s", settings.poll_interval_seconds, settings.collector_api_url)
    async with httpx.AsyncClient(base_url=settings.collector_api_url.rstrip("/") + "/", timeout=30,
                                 headers={"X-Ingest-Token": settings.ingest_token}) as client:
        next_run = time.monotonic()
        while True:
            servers = load_servers()  # cadastros novos entram sem reiniciar o coletor
            if servers:
                await cycle(engine, client, servers)
            elif args.verbose:
                log.info("nenhum servidor real com SNMP ativo")
            next_run += settings.poll_interval_seconds
            await asyncio.sleep(max(0.0, next_run - time.monotonic()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Coletor SNMP do SMI")
    parser.add_argument("--test", metavar="HOST_ID", help="consulta um servidor uma vez e mostra, sem enviar")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # sem uma linha por requisição
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        log.info("coletor SNMP encerrado")


if __name__ == "__main__":
    main()
