"""Cálculos do coletor SNMP (sem rede). O teste com um agente SNMP de verdade está descrito em
docs/vps/GUIA-VPS.md (comando --test)."""

from collector.snmp_poller import (
    HR_STORAGE_FIXED_DISK, HR_STORAGE_RAM, OID_STORAGE,
    cpu_percent, disk_percent, ram_percent_hr, ram_percent_ucd, storage_rows, temperature,
)


def test_cpu_is_average_of_cores():
    assert cpu_percent([12, 30]) == 21.0
    assert cpu_percent([]) is None


def test_ram_discounts_buffers_and_cache():
    # 8 GB total, 2 GB livres, 0,5 GB buffers, 2,5 GB cache -> 3 GB em uso
    assert ram_percent_ucd(8_000_000, 2_000_000, 500_000, 2_500_000) == 37.5
    assert ram_percent_ucd(None, 1, 0, 0) is None
    assert ram_percent_ucd(1000, 900, None, None) == 10.0


def _table(rows):
    out = {}
    for idx, (typ, descr, units, size, used) in rows.items():
        for col, value in zip((2, 3, 4, 5, 6), (typ, descr, units, size, used)):
            out[f"{OID_STORAGE}.{col}.{idx}"] = value
    return out


def test_disk_uses_fullest_real_partition_and_ram_fallback():
    rows = storage_rows(_table({
        1: (HR_STORAGE_RAM, "Physical memory", 1024, 8_000_000, 6_000_000),
        31: (HR_STORAGE_FIXED_DISK, "/", 4096, 25_000_000, 7_500_000),      # 30%
        32: (HR_STORAGE_FIXED_DISK, "/boot/efi", 512, 1000, 900),           # 90%, ignorada
        33: (HR_STORAGE_FIXED_DISK, "/var/lib", 4096, 1_000_000, 450_000),  # 45%
        34: (HR_STORAGE_FIXED_DISK, "/snap/core", 4096, 100, 100),          # ignorada
    }))
    assert disk_percent(rows) == 45.0
    assert ram_percent_hr(rows) == 75.0
    assert disk_percent([]) is None


def test_temperature_from_lm_sensors_millidegrees():
    assert temperature([45_000, 52_500]) == 52.5
    assert temperature([0, 200_000]) is None  # leituras absurdas descartadas
    assert temperature([]) is None
