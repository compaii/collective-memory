"""Filesystem/reader contract qualification, never real research findings."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import research_updates as updates


def map_body(text="Original interpretation", sources=None):
    sources = sources if sources is not None else ["research/topic/one/original.md"]
    return ('---\nid: research.topic\nproject: topic\nsource_paths: ' + json.dumps(sources)
            + '\n---\n# A research question\n\n' + text + '\n')


class ResearchUpdatesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {"instance": "fixture-research", "curator": "fixture-curator",
                       "corpus": str(self.root / "corpus"), "receipts": str(self.root / "receipts")}
        self.reader_config = {"instance": "fixture-research", "endpoint": "http://unused.invalid"}
        self.document = "mapa/proyectos/topic.md"
        self.path = updates.overlay(self.config, self.document)
        self.path.parent.mkdir(parents=True)
        self.path.write_text(map_body())
        self.command = {"schema": "collective-research.map-update/v1", "operation": "iteration-1",
                        "document": self.document, "expected_sha256": updates.digest(self.path.read_bytes()),
                        "body": map_body("Revised relation: this is a method, not confirming evidence."),
                        "reason": "Operator fixture checks a deliberately authored relation correction."}
        self.health = {"index_generation": "1", "ui_index_generation": "1", "ui_generation": "ui-1",
                       "indexed_snapshot": "mapa.fixture", "current_snapshot": "mapa.fixture",
                       "stale": False, "ui_stale": False, "ui_status": "ok"}
        snapshot = self.root / "corpus/.mapa/snapshots/mapa.fixture"
        snapshot.mkdir(parents=True)
        (self.root / "corpus/mapa").symlink_to(snapshot, target_is_directory=True)
        self.published = self.root / "corpus" / self.document
        self.published.parent.mkdir(parents=True)
        self.published.write_text(map_body())
        self.docs = {self.document: {"doc_id": self.document, "kind": "mapa", "body": map_body(), "title": "Question"}}

    def reader(self, config, route):
        if route == "/health":
            return copy.deepcopy(self.health)
        doc_id = parse_qs(urlsplit(route).query)["id"][0]
        if doc_id not in self.docs:
            raise HTTPError("http://unused.invalid", 404, "missing", {}, None)
        return copy.deepcopy(self.docs[doc_id])

    def publish(self):
        self.published.write_text(self.command["body"])
        self.docs[self.document]["body"] = self.command["body"]
        self.health.update(index_generation="2", ui_index_generation="2", ui_generation="ui-2")

    def test_source_acceptance_is_not_snapshot_or_reader_publication(self):
        accepted = updates.apply_map(self.config, self.command)
        self.assertEqual(accepted["source_status"], "current")
        self.assertTrue(accepted["acceptance"]["changed"])
        self.assertIsNone(accepted["acceptance"]["index_generation"])
        self.assertEqual(self.published.read_text(), map_body())
        old = updates.observe(self.config, "iteration-1", "before-build", self.reader_config, self.reader)
        self.assertEqual(old["status"], "not-visible")
        self.publish()
        visible = updates.observe(self.config, "iteration-1", "after-build", self.reader_config, self.reader)
        self.assertEqual(visible["status"], "published")
        self.assertEqual(visible["observed_sha256"], accepted["acceptance"]["document_sha256"])
        self.assertEqual(visible["snapshot_sha256"], visible["observed_sha256"])
        self.assertEqual(visible["publication"]["index_generation"], "2")
        self.assertFalse(visible["atlas_relationships_verified"])
        retained = updates.status(self.config, "iteration-1")
        self.assertEqual(len(retained["observations"]), 2)
        self.assertIsNone(retained["acceptance"]["index_generation"])

    def test_exact_retry_never_overwrites_a_subsequent_revision(self):
        first = updates.apply_map(self.config, self.command)
        self.assertEqual(updates.apply_map(self.config, self.command), first)
        second = {**self.command, "operation": "iteration-2", "body": map_body("Another perspective"),
                  "expected_sha256": first["current_sha256"]}
        updates.apply_map(self.config, second)
        replay = updates.apply_map(self.config, self.command)
        self.assertEqual(replay["source_status"], "different-revision")
        self.assertEqual(replay["acceptance"], first["acceptance"])
        self.assertEqual(self.path.read_text(), second["body"])
        folder = updates.update_directory(self.config, "iteration-1")
        self.assertEqual((folder / "before.md").read_text(), map_body())
        self.assertEqual((folder / "after.md").read_text(), self.command["body"])
        with self.assertRaisesRegex(ValueError, "another command"):
            updates.apply_map(self.config, {**self.command, "body": map_body("Conflicting retry")})

    def test_stale_base_and_single_writer_do_not_apply(self):
        self.path.write_text(map_body("Already advanced elsewhere"))
        with self.assertRaisesRegex(ValueError, "Stale map base"):
            updates.apply_map(self.config, self.command)
        self.assertFalse(updates.update_directory(self.config, "iteration-1").exists())
        with updates.writer(self.config):
            with self.assertRaises(BlockingIOError):
                updates.apply_map(self.config, self.command)

    def test_interrupted_write_recovers_before_receipt_without_a_second_effect(self):
        original = updates.immutable

        def interrupt_receipt(path, data):
            if path.name == "acceptance.json":
                raise OSError("injected interruption after canonical replace")
            return original(path, data)

        with patch.object(updates, "immutable", side_effect=interrupt_receipt):
            with self.assertRaises(OSError):
                updates.apply_map(self.config, self.command)
        self.assertEqual(self.path.read_text(), self.command["body"])
        self.assertIsNone(updates.status(self.config, "iteration-1")["acceptance"])
        with patch.object(updates, "replace_bytes", side_effect=AssertionError("Do not repeat the effect")):
            recovered = updates.apply_map(self.config, self.command)
        self.assertEqual(recovered["acceptance"]["status"], "accepted-overlay")

    def test_interrupted_update_cannot_erase_a_later_unrelated_map(self):
        with patch.object(updates, "replace_bytes", side_effect=OSError("injected before replacement")):
            with self.assertRaises(OSError):
                updates.apply_map(self.config, self.command)
        self.path.write_text(map_body("Another curator's intervening revision"))
        with self.assertRaisesRegex(ValueError, "conflicts with a later"):
            updates.apply_map(self.config, self.command)
        self.assertIn("intervening", self.path.read_text())

    def test_publication_failure_retry_retains_distinct_observations(self):
        updates.apply_map(self.config, self.command)
        broken = lambda *_: (_ for _ in ()).throw(OSError("Private endpoint must not appear"))
        failed = updates.observe(self.config, "iteration-1", "failed-build", self.reader_config, broken)
        self.assertEqual(failed["status"], "unavailable")
        self.assertNotIn("Private endpoint", json.dumps(failed))
        self.publish()
        self.assertEqual(updates.observe(self.config, "iteration-1", "failed-build", self.reader_config, self.reader), failed)
        good = updates.observe(self.config, "iteration-1", "retry-build", self.reader_config, self.reader)
        self.assertEqual(good["status"], "published")
        self.health["ui_stale"] = True
        stale = updates.observe(self.config, "iteration-1", "stale-ui", self.reader_config, self.reader)
        self.assertEqual(stale["status"], "incoherent")

    def test_exact_reader_bytes_do_not_prove_current_map_snapshot(self):
        updates.apply_map(self.config, self.command)
        self.docs[self.document]["body"] = self.command["body"]
        result = updates.observe(self.config, "iteration-1", "reader-only", self.reader_config, self.reader)
        self.assertEqual(result["status"], "not-visible")
        self.assertNotEqual(result["snapshot_sha256"], result["observed_sha256"])

    def test_snapshots_expose_selection_missing_sources_and_generation_change(self):
        missing = "research/topic/one/missing.md"
        capture = updates.snapshot(self.reader_config, [self.document, missing], self.reader)
        self.assertEqual(capture["scope"]["missing"], [missing])
        self.assertFalse(capture["scope"]["atlas_included"])
        self.assertFalse(capture["scope"]["complete_corpus"])
        self.assertEqual(capture["documents"][0]["document"]["body"], map_body())
        self.assertEqual(capture["documents"][0]["revision"], "sha256:" + updates.digest(map_body().encode()))
        calls = []

        def changing(config, route):
            calls.append(route)
            if len(calls) == 3:
                self.health["index_generation"] = self.health["ui_index_generation"] = "2"
            return self.reader(config, route)

        with self.assertRaisesRegex(ValueError, "changed during capture"):
            updates.snapshot(self.reader_config, [self.document], changing)

    def test_source_paths_authority_identity_and_symlink_boundaries(self):
        for doc in ["research/topic/one/original.md", "mapa/../secret.md", "/etc/hosts", "mapa//index.md"]:
            with self.assertRaises(ValueError):
                updates.apply_map(self.config, {**self.command, "document": doc})
        with self.assertRaisesRegex(ValueError, "map identity"):
            updates.apply_map(self.config, {**self.command, "body": self.command["body"].replace("research.topic", "research.other")})
        with self.assertRaises(ValueError):
            updates.apply_map(self.config, {**self.command, "body": map_body(sources=["../../private.md"])})
        with self.assertRaisesRegex(ValueError, "credential-shaped"):
            updates.apply_map(self.config, {**self.command, "body": map_body("api_" + "key=" + "fixture" * 9)})
        original = self.root / "original.md"
        self.path.rename(original)
        self.path.symlink_to(original)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            updates.apply_map(self.config, self.command)
        self.assertEqual(original.read_text(), map_body())

    def test_new_map_requires_absence_and_noop_is_explicit(self):
        # Upstream document IDs can contain spaces, commas and Unicode. Do not
        # confuse logical operation-ID syntax with actual corpus filenames.
        command = {**self.command, "document": "mapa/proyectos/Prueba, relación.md", "expected_sha256": None,
                   "body": map_body(sources=["research/topic/one/Geometry, revisión.md"])}
        created = updates.apply_map(self.config, command)
        self.assertTrue(created["acceptance"]["changed"])
        with self.assertRaisesRegex(ValueError, "Stale map base"):
            updates.apply_map(self.config, {**command, "operation": "different-create"})
        same = updates.apply_map(self.config, {**command, "operation": "no-change", "expected_sha256": created["current_sha256"]})
        self.assertFalse(same["acceptance"]["changed"])


if __name__ == "__main__":
    unittest.main()
