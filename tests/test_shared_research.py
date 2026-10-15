"""Real filesystem boundaries for independently provisioned contributor routes."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "shared_research.py"
spec = importlib.util.spec_from_file_location("shared_research", SOURCE)
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)


class SharedResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {"instance": "fictional-shared-research", "curator": "curator:fixture",
                       "corpus": str(self.root / "corpus"), "receipts": str(self.root / "receipts"),
                       "participants": {p: str(self.root / "inbox" / p) for p in ("one", "two", "three")}}

    def submit(self, participant="one", operation="trial", body="A fictional finding."):
        return shared.submit({"participant": participant, "outbox": self.config["participants"][participant]},
                             operation, "Fixture research", body, ["https://example.org/source"])

    def accept(self, participant="one", operation="trial"):
        return shared.accept(self.config, participant, operation, "topic", "Inspected fixture source")

    def test_three_routes_keep_same_id_independent_and_replay_observes_bytes(self):
        for participant in self.config["participants"]:
            self.submit(participant)
            first = self.accept(participant)
            self.assertEqual(first, self.accept(participant))
            self.assertIsNone(first["index_generation"])
        self.assertEqual(len(list((self.root / "corpus" / "research").rglob("*.md"))), 3)
        receipt = self.accept()
        (self.root / "corpus" / receipt["document"]).write_text("Changed after acceptance")
        with self.assertRaisesRegex(ValueError, "observed corpus"):
            self.accept()

    def test_submission_retry_and_conflicting_source(self):
        self.assertEqual(self.submit(), self.submit())
        with self.assertRaisesRegex(ValueError, "different bytes"):
            self.submit(body="Different bytes")
        self.assertFalse((self.root / "corpus").exists())

    def test_contributor_cannot_claim_another_provisioned_route(self):
        self.submit()
        path = Path(self.config["participants"]["one"]) / "trial.json"
        doc = json.loads(path.read_text()); doc["participant"] = "two"
        path.write_bytes(shared.canonical(doc))
        with self.assertRaisesRegex(ValueError, "participant route"):
            self.accept()
        self.assertFalse((self.root / "corpus" / "research").exists())

    def test_symlink_and_logical_path_traversal_refused(self):
        self.submit()
        path = Path(self.config["participants"]["one"]) / "trial.json"
        original = self.root / "original.json"; path.rename(original); path.symlink_to(original)
        with self.assertRaises(OSError):
            self.accept()
        with self.assertRaises(ValueError):
            shared.accept(self.config, "one", "trial", "../escape", "Reason")

    def test_no_credential_shaped_text_enters_corpus(self):
        self.submit(body="api_" + "key=" + "fixture" * 9)
        with self.assertRaisesRegex(ValueError, "credential-shaped"):
            self.accept()
        self.assertFalse((self.root / "corpus" / "research").exists())

    def test_recover_file_installed_before_receipt_and_curator_lock(self):
        self.submit(); receipt = self.accept()
        receipt_path = Path(self.config["receipts"]) / "one" / "trial.json"
        receipt_path.unlink()
        recovered = self.accept()
        self.assertEqual(receipt["document_sha256"], recovered["document_sha256"])
        import fcntl
        with (self.root / "corpus" / ".mapa" / "lock").open("a") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                self.accept()


if __name__ == "__main__":
    unittest.main()
