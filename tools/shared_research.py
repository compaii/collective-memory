#!/usr/bin/env python3
"""Explicit contributions to a selected corpus; read APIs stay upstream-owned.

Participant authority comes from separately provisioned filesystem access. This
does not sign Matrix identities or perform HMK publication, LLM work or indexing.
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlencode
from urllib.request import urlopen

LIMIT = 512 * 1024
ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}\Z")


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("Use a bounded logical identifier")
    return value


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def read_file(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        import stat
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("A regular file is required")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            data = handle.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError("Contribution exceeds the size limit")
        return data
    finally:
        os.close(fd)


def immutable(path, data):
    """Publish complete bytes without overwriting a prior operation ID."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            if read_file(path) != data:
                raise ValueError("Operation ID already contains different bytes")
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.unlink(temporary)


def submit(config, operation, title, body, sources):
    identifier(operation)
    participant = identifier(config["participant"])
    if not title.strip() or len(title) > 240 or not body.strip():
        raise ValueError("A bounded title and nonempty research text are required")
    if not sources or len(sources) > 32 or any(not isinstance(s, str) or not s.strip() or len(s) > 2000 for s in sources):
        raise ValueError("Provide bounded attributed source references")
    doc = {"schema": "collective-research.proposal/v1", "id": operation,
           "participant": participant, "title": title, "body": body, "sources": sources}
    data = canonical(doc)
    if len(data) > LIMIT:
        raise ValueError("Contribution exceeds the size limit")
    immutable(Path(config["outbox"]) / (operation + ".json"), data)
    return {"id": operation, "participant": participant, "sha256": digest(data),
            "status": "submitted", "indexed": False}


def inspect(config, participant, operation):
    participant, operation = identifier(participant), identifier(operation)
    route = config["participants"][participant]
    data = read_file(Path(route) / (operation + ".json"))
    doc = json.loads(data)
    fields = {"schema", "id", "participant", "title", "body", "sources"}
    if set(doc) != fields or doc["schema"] != "collective-research.proposal/v1":
        raise ValueError("Unsupported proposal envelope")
    if doc["participant"] != participant or doc["id"] != operation:
        raise ValueError("Proposal differs from its provisioned participant route")
    if not isinstance(doc["title"], str) or not doc["title"].strip() or len(doc["title"]) > 240:
        raise ValueError("Invalid title")
    if not isinstance(doc["body"], str) or not doc["body"].strip():
        raise ValueError("Invalid body")
    if not isinstance(doc["sources"], list) or not 1 <= len(doc["sources"]) <= 32:
        raise ValueError("Invalid source references")
    if any(not isinstance(s, str) or not s.strip() or len(s) > 2000 for s in doc["sources"]):
        raise ValueError("Invalid source reference")
    return doc, digest(data)


def accept(config, participant, operation, research, reason):
    """Manual curator action. Reindex remains the upstream librarian's action."""
    identifier(research)
    if not reason.strip():
        raise ValueError("Record the curator's reason")
    root = Path(config["corpus"])
    lock_path = root / ".mapa" / "lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        doc, proposal_hash = inspect(config, participant, operation)
        relative = Path("research") / research / participant / (operation + ".md")
        metadata = {"schema": "collective-research.contribution/v1", "instance": config["instance"],
                    "participant_route": participant, "proposal_sha256": proposal_hash,
                    "sources": doc["sources"], "curated_by": config["curator"], "reason": reason,
                    "audience": "instance-participants", "human_verified": False}
        rendered = ("<!-- " + json.dumps(metadata, ensure_ascii=False, sort_keys=True).replace("-->", "-- >")
                    + " -->\n# " + doc["title"].replace("\n", " ") + "\n\n" + doc["body"] + "\n").encode()
        # Reuse the engine's reject-only credential scanner before corpus intake.
        import sys
        os.environ.setdefault("MAPA_ROOT", str(root))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mapa"))
        from tier1 import SECRET_PATTERNS
        if len(rendered) > LIMIT:
            raise ValueError("Rendered contribution exceeds the size limit")
        if any(pattern.search(rendered.decode()) for pattern in SECRET_PATTERNS):
            raise ValueError("Contribution contains credential-shaped content")
        receipt_path = Path(config["receipts"]) / participant / (operation + ".json")
        if receipt_path.exists():
            receipt = json.loads(read_file(receipt_path))
            if (receipt["proposal_sha256"] != proposal_hash or receipt["document"] != str(relative)
                    or receipt["document_sha256"] != digest(rendered)
                    or read_file(root / relative) != rendered):
                raise ValueError("Retained acceptance differs from source or observed corpus bytes")
            return receipt
        immutable(root / relative, rendered)
        receipt = {"schema": "collective-research.acceptance/v1", "participant_route": participant,
                   "operation": operation, "proposal_sha256": proposal_hash, "document": str(relative),
                   "document_sha256": digest(rendered), "curated_by": config["curator"], "reason": reason,
                   "accepted_at": dt.datetime.now(dt.timezone.utc).isoformat(), "status": "accepted-corpus",
                   "index_generation": None}
        immutable(receipt_path, canonical(receipt))
        return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=Path(__file__).with_name("client.json"))
    commands = p.add_subparsers(dest="command", required=True)
    s = commands.add_parser("submit"); s.add_argument("--id", required=True)
    s.add_argument("--title", required=True); s.add_argument("--file", required=True, type=Path)
    s.add_argument("--source", required=True, action="append")
    s = commands.add_parser("inspect"); s.add_argument("participant"); s.add_argument("id")
    s = commands.add_parser("accept"); s.add_argument("participant"); s.add_argument("id")
    s.add_argument("--research", required=True); s.add_argument("--reason", required=True)
    s = commands.add_parser("search"); s.add_argument("query")
    s = commands.add_parser("read"); s.add_argument("id")
    commands.add_parser("health")
    a = p.parse_args(); config = json.loads(read_file(a.config))
    if a.command == "submit":
        result = submit(config, a.id, a.title, read_file(a.file).decode(), a.source)
    elif a.command == "inspect":
        result = inspect(config, a.participant, a.id)[0]
    elif a.command == "accept":
        result = accept(config, a.participant, a.id, a.research, a.reason)
    else:
        path = "/health" if a.command == "health" else ("/search?" + urlencode({"q": a.query, "k": 15})
                if a.command == "search" else "/doc?" + urlencode({"id": a.id}))
        with urlopen(config["endpoint"].rstrip("/") + path, timeout=30) as response:
            result = json.load(response)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
