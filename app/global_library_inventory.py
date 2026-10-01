from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json

from app.database import database_connection
from app.library_registry import (
    LibraryRegistryError,
    claim_source_family,
    get_source_family_claim,
    get_source_family_claims,
    register_source_backup,
    register_source_family,
    register_source_family_members,
    register_source_media,
    release_source_family_claim,
    release_source_family_reservation,
)


def occurrence_key(library_id: str, job_id: str, family_key: str) -> str:
    return f"{library_id}:{job_id}:{family_key}"


def backup_key(library_id: str, job_id: str) -> str:
    return f"{library_id}:{job_id}"


def family_content_fingerprint(members: list[dict[str, Any]]) -> str:
    normalized = sorted(
        (
            str(row.get("sha256") or row.get("sha256_original") or "").strip().lower(),
            int(row.get("size_bytes") or 0),
            str(row.get("media_type") or "").strip().lower(),
        )
        for row in members
        if str(row.get("sha256") or row.get("sha256_original") or "").strip()
    )
    if not normalized:
        raise LibraryRegistryError(
            "Dateifamilie besitzt keine prüfbaren SHA256-Mitglieder."
        )
    payload = json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "family-members-sha256:" + hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def register_analysis_inventory(
    registry_path: Path,
    *,
    library_id: str,
    job_id: str,
    source_identity: str,
    source_path: str,
    analysis: dict[str, Any],
    checksums: dict[str, str],
    sizes: dict[str, int],
) -> dict[str, Any]:
    backup_id = backup_key(library_id, job_id)
    register_source_backup(
        registry_path,
        backup_id=backup_id,
        source_kind="import",
        source_identity=source_identity or job_id,
        backup_path=source_path or job_id,
        metadata={"library_id": library_id, "job_id": job_id},
    )

    members_by_family: dict[str, list[dict[str, Any]]] = {}
    for row in analysis.get("files") or []:
        family_key = str(row.get("family_key") or "").strip()
        relative = str(row.get("relative_path") or "").strip()
        checksum = str(checksums.get(relative) or "").strip()
        if not family_key or not relative or not checksum:
            continue
        members_by_family.setdefault(family_key, []).append(
            {
                "relative_path": relative,
                "sha256": checksum,
                "size_bytes": int(sizes.get(relative) or 0),
                "media_type": str(row.get("media_type") or ""),
            }
        )

    occurrences: dict[str, dict[str, Any]] = {}
    for family_key, members in members_by_family.items():
        fingerprint = family_content_fingerprint(members)
        source_key = occurrence_key(library_id, job_id, family_key)
        family = register_source_family(
            registry_path,
            source_family_key=source_key,
            backup_id=backup_id,
            family_key=family_key,
            content_fingerprint=fingerprint,
            metadata={"library_id": library_id, "job_id": job_id},
        )
        media_ids: list[str] = []
        for member in members:
            media = register_source_media(
                registry_path,
                backup_id=backup_id,
                relative_path=str(member["relative_path"]),
                size_bytes=int(member["size_bytes"]),
                sha256=str(member["sha256"]),
                media_type=str(member["media_type"]),
            )
            media_ids.append(str(media["media_id"]))
        register_source_family_members(
            registry_path,
            source_family_key=source_key,
            media_ids=media_ids,
        )
        claim = get_source_family_claim(registry_path, source_key)
        occurrences[family_key] = {
            "source_family_key": source_key,
            "canonical_family_id": str(family["canonical_family_id"]),
            "claim": claim,
        }

    return {
        "backup_id": backup_id,
        "families": occurrences,
    }


def admitted_family_keys(
    inventory: dict[str, Any],
    library_id: str,
) -> tuple[set[str], list[dict[str, Any]]]:
    allowed: set[str] = set()
    blocked: list[dict[str, Any]] = []
    for family_key, row in (inventory.get("families") or {}).items():
        claim = row.get("claim")
        if claim is None or str(claim.get("library_id") or "") == library_id:
            allowed.add(str(family_key))
            continue
        blocked.append(
            {
                "family_key": str(family_key),
                "owner_library_id": str(claim.get("library_id") or ""),
                "claim_state": str(claim.get("claim_state") or ""),
            }
        )
    return allowed, blocked


def _database_family_rows(
    database_path: Path,
) -> list[dict[str, Any]]:
    with database_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT
                ff.id AS family_id,
                ff.job_id,
                ff.family_key,
                j.source_signature,
                j.source_fingerprint,
                j.source_device_id,
                j.source_path,
                f.id AS file_id,
                f.original_relative_path,
                f.size_bytes,
                f.sha256_original,
                f.media_type
            FROM file_families ff
            JOIN jobs j ON j.id = ff.job_id
            JOIN files f ON f.family_id = ff.id
            WHERE COALESCE(TRIM(f.sha256_original), '') <> ''
            ORDER BY ff.job_id, ff.id, f.id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def backfill_library_inventory(
    registry_path: Path,
    *,
    database_path: Path,
    library_id: str,
    claim_all_owned: bool,
) -> dict[str, int]:
    rows = _database_family_rows(database_path)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(
            (str(row["job_id"]), str(row["family_key"])),
            [],
        ).append(row)

    backup_registered: set[str] = set()
    family_count = 0
    media_count = 0
    claim_count = 0

    for (job_id, family_key), members in grouped.items():
        first = members[0]
        backup_id = backup_key(library_id, job_id)
        if backup_id not in backup_registered:
            identity = str(
                first.get("source_signature")
                or first.get("source_fingerprint")
                or first.get("source_device_id")
                or first.get("source_path")
                or job_id
            )
            register_source_backup(
                registry_path,
                backup_id=backup_id,
                source_kind="existing_library",
                source_identity=identity,
                backup_path=str(first.get("source_path") or job_id),
                metadata={"library_id": library_id, "job_id": job_id},
            )
            backup_registered.add(backup_id)

        normalized_members = [
            {
                "relative_path": str(row["original_relative_path"]),
                "sha256": str(row["sha256_original"]),
                "size_bytes": int(row["size_bytes"] or 0),
                "media_type": str(row["media_type"] or ""),
            }
            for row in members
        ]
        source_key = occurrence_key(library_id, job_id, family_key)
        family = register_source_family(
            registry_path,
            source_family_key=source_key,
            backup_id=backup_id,
            family_key=family_key,
            content_fingerprint=family_content_fingerprint(normalized_members),
            metadata={"library_id": library_id, "job_id": job_id},
        )
        media_ids: list[str] = []
        for member in normalized_members:
            media = register_source_media(
                registry_path,
                backup_id=backup_id,
                relative_path=str(member["relative_path"]),
                size_bytes=int(member["size_bytes"]),
                sha256=str(member["sha256"]),
                media_type=str(member["media_type"]),
            )
            media_ids.append(str(media["media_id"]))
            media_count += 1
        register_source_family_members(
            registry_path,
            source_family_key=source_key,
            media_ids=media_ids,
        )
        family_count += 1

        if claim_all_owned:
            claim_source_family(
                registry_path,
                source_family_key=source_key,
                library_id=library_id,
                event_id=None,
                claim_state="owned",
            )
            claim_count += 1

    return {
        "family_count": family_count,
        "media_count": media_count,
        "claim_count": claim_count,
    }


def backfill_library_claims(
    registry_path: Path,
    *,
    database_path: Path,
    library_id: str,
) -> dict[str, int]:
    with database_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT
                COALESCE(ff_direct.job_id, ff_file.job_id) AS job_id,
                COALESCE(ff_direct.family_key, ff_file.family_key) AS family_key,
                root.id AS event_id,
                root.status AS event_status
            FROM event_assignments ea
            JOIN events assigned ON assigned.id = ea.event_id
            JOIN events root
              ON root.id = COALESCE(assigned.parent_event_id, assigned.id)
            LEFT JOIN file_families ff_direct
              ON ff_direct.id = ea.family_id
            LEFT JOIN files file_row
              ON file_row.id = ea.file_id
            LEFT JOIN file_families ff_file
              ON ff_file.id = file_row.family_id
            WHERE root.status IN ('draft', 'planned', 'applied', 'archived')
              AND COALESCE(ff_direct.id, ff_file.id) IS NOT NULL
            ORDER BY job_id, family_key, event_id
            """
        ).fetchall()

    # Falls historische Sonderfälle dieselbe Familie mehrfach referenzieren,
    # gewinnt der stärkere Zustand: owned vor reserved.
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        key = (str(row["job_id"]), str(row["family_key"]))
        state = (
            "owned"
            if str(row["event_status"]) in {"applied", "archived"}
            else "reserved"
        )
        previous = selected.get(key)
        if (
            previous is None
            or (
                state == "owned"
                and str(previous["claim_state"]) != "owned"
            )
        ):
            selected[key] = {
                "event_id": str(row["event_id"]),
                "claim_state": state,
            }

    reserved = 0
    owned = 0
    for (job_id, family_key), row in selected.items():
        claim_source_family(
            registry_path,
            source_family_key=occurrence_key(
                library_id,
                job_id,
                family_key,
            ),
            library_id=library_id,
            event_id=str(row["event_id"]),
            claim_state=str(row["claim_state"]),
        )
        if row["claim_state"] == "owned":
            owned += 1
        else:
            reserved += 1

    return {
        "reserved_count": reserved,
        "owned_count": owned,
        "claim_count": reserved + owned,
    }


def source_family_keys_for_ids(
    database_path: Path,
    library_id: str,
    family_ids: list[int] | set[int],
) -> dict[int, str]:
    requested = sorted({int(value) for value in family_ids if int(value) > 0})
    if not requested:
        return {}

    placeholders = ",".join("?" for _ in requested)
    with database_connection(database_path) as connection:
        rows = connection.execute(
            f"""
            SELECT id, job_id, family_key
            FROM file_families
            WHERE id IN ({placeholders})
            ORDER BY id
            """,
            tuple(requested),
        ).fetchall()

    found = {int(row["id"]) for row in rows}
    missing = sorted(set(requested) - found)
    if missing:
        raise LibraryRegistryError(
            "Mindestens eine Dateifamilie wurde nicht gefunden: "
            + ", ".join(str(value) for value in missing)
        )

    return {
        int(row["id"]): occurrence_key(
            library_id,
            str(row["job_id"]),
            str(row["family_key"]),
        )
        for row in rows
    }


def reserve_family_ids(
    registry_path: Path,
    *,
    database_path: Path,
    library_id: str,
    event_id: str,
    family_ids: list[int] | set[int],
) -> dict[str, Any]:
    mapping = source_family_keys_for_ids(
        database_path,
        library_id,
        family_ids,
    )
    claims = get_source_family_claims(
        registry_path,
        list(mapping.values()),
    )
    newly_reserved: list[str] = []

    try:
        for family_id, source_key in mapping.items():
            claim = claims.get(source_key)
            if claim is not None:
                owner = str(claim.get("library_id") or "")
                state = str(claim.get("claim_state") or "")
                claim_event = str(claim.get("event_id") or "")
                if owner != library_id:
                    raise LibraryRegistryError(
                        "Mindestens eine Dateifamilie ist bereits einer "
                        "anderen Bibliothek vorbehalten."
                    )
                if (
                    state == "reserved"
                    and claim_event
                    and claim_event != event_id
                ):
                    raise LibraryRegistryError(
                        "Mindestens eine Dateifamilie ist bereits für ein "
                        "anderes Ereignis dieser Bibliothek reserviert."
                    )
                # owned bleibt owned; eine bestehende Reservierung desselben
                # Ereignisses wird nicht unnötig neu geschrieben.
                continue

            claim_source_family(
                registry_path,
                source_family_key=source_key,
                library_id=library_id,
                event_id=event_id,
                claim_state="reserved",
            )
            newly_reserved.append(source_key)
    except Exception:
        for source_key in reversed(newly_reserved):
            try:
                release_source_family_reservation(
                    registry_path,
                    source_family_key=source_key,
                    library_id=library_id,
                )
            except Exception:
                pass
        raise

    return {
        "family_ids": sorted(mapping),
        "source_family_keys": mapping,
        "newly_reserved": newly_reserved,
    }


def release_new_reservations(
    registry_path: Path,
    *,
    library_id: str,
    source_family_keys: list[str],
) -> int:
    released = 0
    for source_key in reversed(list(source_family_keys)):
        try:
            if release_source_family_reservation(
                registry_path,
                source_family_key=source_key,
                library_id=library_id,
            ):
                released += 1
        except LibraryRegistryError:
            # Ein zwischenzeitlich zu owned hochgestufter Claim darf durch
            # Rollback niemals wieder freigegeben werden.
            continue
    return released


def promote_family_ids_owned(
    registry_path: Path,
    *,
    database_path: Path,
    library_id: str,
    event_id: str,
    family_ids: list[int] | set[int],
) -> int:
    mapping = source_family_keys_for_ids(
        database_path,
        library_id,
        family_ids,
    )
    for source_key in mapping.values():
        claim_source_family(
            registry_path,
            source_family_key=source_key,
            library_id=library_id,
            event_id=event_id,
            claim_state="owned",
        )
    return len(mapping)


def release_family_ids_claims(
    registry_path: Path,
    *,
    database_path: Path,
    library_id: str,
    family_ids: list[int] | set[int],
    allowed_states: set[str],
) -> int:
    mapping = source_family_keys_for_ids(
        database_path,
        library_id,
        family_ids,
    )
    claims = get_source_family_claims(
        registry_path,
        list(mapping.values()),
    )
    released = 0
    for source_key in mapping.values():
        claim = claims.get(source_key)
        if claim is None:
            continue
        if str(claim.get("library_id") or "") != library_id:
            raise LibraryRegistryError(
                "Eine freizugebende Dateifamilie gehört zu einer anderen Bibliothek."
            )
        if str(claim.get("claim_state") or "") not in allowed_states:
            continue
        if release_source_family_claim(
            registry_path,
            source_family_key=source_key,
            library_id=library_id,
            allowed_states=allowed_states,
        ):
            released += 1
    return released


def blocked_family_ids(
    registry_path: Path,
    *,
    database_path: Path,
    library_id: str,
    job_id: str | None = None,
) -> set[int]:
    params: list[Any] = []
    sql = "SELECT id, job_id, family_key FROM file_families"
    if job_id is not None:
        sql += " WHERE job_id = ?"
        params.append(str(job_id))
    sql += " ORDER BY id"

    with database_connection(database_path) as connection:
        rows = connection.execute(sql, params).fetchall()

    keyed = {
        occurrence_key(
            library_id,
            str(row["job_id"]),
            str(row["family_key"]),
        ): int(row["id"])
        for row in rows
    }
    claims = get_source_family_claims(
        registry_path,
        list(keyed),
    )
    return {
        keyed[source_key]
        for source_key, claim in claims.items()
        if str(claim.get("library_id") or "") != library_id
    }


def _event_occurrences(
    database_path: Path,
    library_id: str,
    event_id: str,
) -> list[str]:
    with database_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT
                COALESCE(ff_direct.job_id, ff_file.job_id) AS job_id,
                COALESCE(ff_direct.family_key, ff_file.family_key) AS family_key
            FROM event_assignments ea
            JOIN events assigned ON assigned.id = ea.event_id
            LEFT JOIN file_families ff_direct ON ff_direct.id = ea.family_id
            LEFT JOIN files file_row ON file_row.id = ea.file_id
            LEFT JOIN file_families ff_file ON ff_file.id = file_row.family_id
            WHERE (
                assigned.id = ?
                OR assigned.parent_event_id = ?
            )
              AND COALESCE(ff_direct.id, ff_file.id) IS NOT NULL
            ORDER BY job_id, family_key
            """,
            (event_id, event_id),
        ).fetchall()

    return [
        occurrence_key(
            library_id,
            str(row["job_id"]),
            str(row["family_key"]),
        )
        for row in rows
    ]


def claim_event_families(
    registry_path: Path,
    *,
    database_path: Path,
    library_id: str,
    event_id: str,
    claim_state: str,
) -> int:
    occurrences = _event_occurrences(database_path, library_id, event_id)
    for source_key in occurrences:
        claim_source_family(
            registry_path,
            source_family_key=source_key,
            library_id=library_id,
            event_id=event_id,
            claim_state=claim_state,
        )
    return len(occurrences)


def release_event_reservations(
    registry_path: Path,
    *,
    database_path: Path,
    library_id: str,
    event_id: str,
) -> int:
    released = 0
    for source_key in _event_occurrences(database_path, library_id, event_id):
        claim = get_source_family_claim(registry_path, source_key)
        if (
            claim
            and str(claim.get("library_id") or "") == library_id
            and str(claim.get("claim_state") or "") == "reserved"
            and str(claim.get("event_id") or "") == event_id
        ):
            if release_source_family_reservation(
                registry_path,
                source_family_key=source_key,
                library_id=library_id,
            ):
                released += 1
    return released
