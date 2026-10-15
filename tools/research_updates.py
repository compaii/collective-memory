"""Finite, curator-owned map updates and separately observed publication.

The reader remains read-only. Canonical overlays use the librarian's existing
writer lock; accepted research originals and derived Atlas files are untouched.
"""
from contextlib import contextmanager
import datetime as dt
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from shared_research import LIMIT, canonical, check_content, digest, identifier, immutable, read_file


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def document_id(value):
    if (not isinstance(value, str) or not value or len(value) > 1000
            or PurePosixPath(value).is_absolute() or PurePosixPath(value).as_posix() != value
            or any(p in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9._-]+", p) for p in value.split("/"))):
        raise ValueError("Use a bounded corpus-relative document ID")
    return value


def fetch(config, path):
    # Endpoint is an installed receiving binding, never content from a document.
    with urlopen(config["endpoint"].rstrip("/") + path, timeout=15) as response:
        data = response.read(LIMIT * 2 + 1)
    if len(data) > LIMIT * 2:
        raise ValueError("Reader response exceeds the bound")
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("Reader response must be an object")
    return value


def health_stamp(health):
    return {k: health.get(k) for k in ("index_generation", "indexed_snapshot", "current_snapshot",
                                      "ui_generation", "ui_index_generation")}


def coherent(health):
    return (bool(health.get("index_generation")) and health.get("stale") is False
            and health.get("ui_stale") is False and health.get("ui_status") == "ok"
            and health.get("ui_index_generation") == health.get("index_generation")
            and not health.get("last_index_error") and not health.get("ui_error"))


def snapshot(config, documents, reader=fetch):
    """Exact, explicitly selected documents; never an implied complete Atlas."""
    if not 1 <= len(documents) <= 32 or len(set(documents)) != len(documents):
        raise ValueError("Select one to 32 distinct documents; split larger explicit selections")
    for item in documents:
        document_id(item)
    before = reader(config, "/health")
    if not coherent(before):
        raise ValueError("Reader index and UI are not a coherent publication")
    captured, missing = [], []
    for item in documents:
        try:
            doc = reader(config, "/doc?" + urlencode({"id": item}))
        except HTTPError as exc:
            if exc.code != 404:
                raise
            missing.append(item)
            continue
        if doc.get("doc_id") != item or not isinstance(doc.get("body"), str):
            raise ValueError("Reader document differs from the selected identity")
        data = doc["body"].encode()
        if len(data) > LIMIT:
            raise ValueError("Selected source exceeds the per-document bound")
        captured.append({"document": doc, "revision": "sha256:" + digest(data),
                         "sha256": digest(data), "observed_at": now()})
    after = reader(config, "/health")
    if not coherent(after) or health_stamp(before) != health_stamp(after):
        raise ValueError("Publication changed during capture; retry the selection")
    return {"schema": "collective-research.snapshot/v1", "provider": config["instance"],
            "publication": health_stamp(after), "observed_at": now(), "documents": captured,
            "scope": {"kind": "explicit-documents", "requested": documents, "missing": missing,
                      "atlas_included": False, "complete_corpus": False},
            "meaning": "Full retained text for the selected documents, not semantic review or a complete Atlas graph."}


@contextmanager
def writer(config):
    # Same lock as accept() and scripts/librarian.sh in the configured deployment.
    lock_path = Path(config["corpus"]) / ".mapa" / "lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def overlay(config, doc_id):
    document_id(doc_id)
    if doc_id != "mapa/index.md" and not (doc_id.startswith("mapa/proyectos/") and doc_id.endswith(".md")):
        raise ValueError("Only canonical semantic map overlays can be updated; source corrections use new contributions")
    root = Path(config["corpus"]) / ".mapa" / "overlays"
    target = root / doc_id
    current = root
    if root.is_symlink():
        raise ValueError("Overlay root cannot be a symlink")
    for part in PurePosixPath(doc_id).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("Canonical overlay paths cannot traverse symlinks")
    return target


def metadata(body):
    """Validate the existing limited map frontmatter convention, not full YAML."""
    match = re.match(r"^---\n(.*?)\n---(?:\n|$)", body, re.S)
    if not match:
        raise ValueError("Project maps need id, project and JSON source_paths frontmatter")
    result = {}
    for key in ("id", "project", "source_paths"):
        values = re.findall(r"^" + key + r":[ \t]*(.+)$", match[1], re.M)
        if len(values) != 1:
            raise ValueError("Map frontmatter fields must be present and unique")
        result[key] = values[0].strip()
        if not result[key] or len(result[key]) > 16000:
            raise ValueError("Map frontmatter values must be nonempty and bounded")
    sources = json.loads(result["source_paths"])
    if not isinstance(sources, list) or len(sources) > 128 or any(not isinstance(s, str) for s in sources):
        raise ValueError("source_paths must be a bounded JSON list")
    for source in sources:
        document_id(source)
        if not source.startswith(("research/", "mapa/")):
            raise ValueError("Map source references must stay in the selected research/map corpus")
    return result


def update_directory(config, operation):
    return Path(config["receipts"]) / "map-updates" / identifier(operation)


def validate_command(config, value):
    fields = {"schema", "operation", "document", "expected_sha256", "body", "reason"}
    if not isinstance(value, dict) or set(value) != fields or value["schema"] != "collective-research.map-update/v1":
        raise ValueError("Unsupported map update command")
    identifier(value["operation"])
    overlay(config, value["document"])
    expected = value["expected_sha256"]
    if expected is not None and (not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected)):
        raise ValueError("Supply the exact prior SHA256, or null only for a new map")
    if not isinstance(value["body"], str) or not value["body"].strip():
        raise ValueError("An authored map body is required")
    if not isinstance(value["reason"], str) or not value["reason"].strip() or len(value["reason"]) > 8000:
        raise ValueError("A bounded curator reason is required")
    check_content(config, value["body"].encode())
    if value["document"] != "mapa/index.md":
        metadata(value["body"])
    intent = {**value, "curated_by": config["curator"], "instance": config["instance"],
              "audience": "instance-participants", "human_verified": False}
    if len(canonical(intent)) > LIMIT:
        raise ValueError("Map command exceeds the retained operation bound")
    return intent


def replace_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".map-update-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def current_hash(path):
    return digest(read_file(path)) if path.exists() else None


def retained(config, operation):
    folder = update_directory(config, operation)
    intent = json.loads(read_file(folder / "intent.json"))
    if intent["operation"] != operation or intent["instance"] != config["instance"] or intent["curated_by"] != config["curator"]:
        raise ValueError("Retained update belongs to another configured authority")
    if read_file(folder / "after.md") != intent["body"].encode():
        raise ValueError("Retained intended map bytes changed")
    if intent["expected_sha256"] is not None and digest(read_file(folder / "before.md")) != intent["expected_sha256"]:
        raise ValueError("Retained prior map bytes changed")
    return folder, intent


def state(config, operation):
    folder, intent = retained(config, operation)
    receipt_path = folder / "acceptance.json"
    receipt = json.loads(read_file(receipt_path)) if receipt_path.exists() else None
    path = overlay(config, intent["document"])
    observed = current_hash(path)
    desired = digest(intent["body"].encode())
    if receipt and (receipt["intent_sha256"] != digest(canonical(intent)) or receipt["document_sha256"] != desired):
        raise ValueError("Retained acceptance differs from its intended update")
    return {"operation": operation, "document": intent["document"], "acceptance": receipt,
            "source_status": "current" if observed == desired else "missing" if observed is None else "different-revision",
            "current_sha256": observed,
            "observations": [json.loads(read_file(p)) for p in sorted((folder / "observations").glob("*.json"))]}


def status(config, operation):
    with writer(config):
        return state(config, operation)


def apply_map(config, value):
    intent = validate_command(config, value)
    operation, body = intent["operation"], intent["body"].encode()
    folder = update_directory(config, operation)
    with writer(config):
        path = overlay(config, intent["document"])
        if (folder / "intent.json").exists():
            if read_file(folder / "intent.json") != canonical(intent):
                raise ValueError("Update ID already contains another command")
            retained(config, operation)
            if (folder / "acceptance.json").exists():
                return state(config, operation)  # Historical success never rewrites a later version.
        else:
            observed = current_hash(path)
            if observed != intent["expected_sha256"]:
                raise ValueError("Stale map base; inspect the current source before preparing another update")
            if observed is not None:
                previous = read_file(path)
                if intent["document"] != "mapa/index.md":
                    old_meta, new_meta = metadata(previous.decode()), metadata(intent["body"])
                    if any(old_meta[k] != new_meta[k] for k in ("id", "project")):
                        raise ValueError("A revision cannot silently change map identity or project")
                immutable(folder / "before.md", previous)
            immutable(folder / "after.md", body)
            immutable(folder / "intent.json", canonical(intent))
        observed = current_hash(path)
        if observed not in {intent["expected_sha256"], digest(body)}:
            raise ValueError("Interrupted update conflicts with a later canonical revision")
        if observed != digest(body):
            replace_bytes(path, body)
        receipt = {"schema": "collective-research.map-acceptance/v1", "operation": operation,
                   "document": intent["document"], "previous_sha256": intent["expected_sha256"],
                   "document_sha256": digest(body), "intent_sha256": digest(canonical(intent)),
                   "curated_by": config["curator"], "accepted_at": now(),
                   "status": "accepted-overlay", "changed": intent["expected_sha256"] != digest(body),
                   "index_generation": None}
        immutable(folder / "acceptance.json", canonical(receipt))
        return state(config, operation)


def observe(config, operation, observation, reader_config, reader=fetch):
    """Observe exact reader bytes; never turn a rebuild exit code into success."""
    identifier(observation)
    if reader_config["instance"] != config["instance"]:
        raise ValueError("Publication observation requires the same instance reader")
    with writer(config):
        folder, intent = retained(config, operation)
        acceptance = state(config, operation)["acceptance"]
        if acceptance is None:
            raise ValueError("Recover source acceptance before observing its publication")
        path = folder / "observations" / (observation + ".json")
        if path.exists():
            return json.loads(read_file(path))
        result = {"schema": "collective-research.map-publication/v1", "operation": operation,
                  "observation": observation, "document": intent["document"], "observed_at": now(),
                  "expected_sha256": acceptance["document_sha256"], "observed_sha256": None,
                  "snapshot_sha256": None, "atlas_relationships_verified": False,
                  "source_current": current_hash(overlay(config, intent["document"])) == acceptance["document_sha256"],
                  "publication": None, "status": "unavailable"}
        try:
            before = reader(reader_config, "/health")
            doc = reader(reader_config, "/doc?" + urlencode({"id": intent["document"]}))
            after = reader(reader_config, "/health")
            if doc.get("doc_id") != intent["document"] or not isinstance(doc.get("body"), str):
                raise ValueError("Reader returned another document")
            result["observed_sha256"] = digest(doc["body"].encode())
            result["publication"] = health_stamp(after)
            current_map = Path(config["corpus"]) / "mapa"
            published = Path(config["corpus"]) / intent["document"]
            result["snapshot_sha256"] = current_hash(published)
            if (not coherent(before) or not coherent(after) or health_stamp(before) != health_stamp(after)
                    or current_map.resolve().name != after.get("current_snapshot")):
                result["status"] = "incoherent"
            else:
                result["status"] = "published" if result["observed_sha256"] == result["snapshot_sha256"] == result["expected_sha256"] else "not-visible"
        except (OSError, ValueError) as exc:
            result["failure_kind"] = type(exc).__name__  # Do not copy private endpoints into receipts.
        immutable(path, canonical(result))
        return result
