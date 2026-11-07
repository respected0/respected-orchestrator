"""B3-09.04: the gate's own decision logic, tested with forged inputs. Pure functions; nothing is collected or run here."""
import copy
import unittest

from tests.tools.release_gate import (REQUIRED, TEST_GROUPS, build_manifest, evaluate, group_result, roadmap_open_p0, verify_manifest)

META = {"commit_sha": "a" * 40, "tree_clean": True, "elevated": False, "generated_at": "2026-11-07T00:00:00Z", "python": "3.13", "platform": "win32"}
GREEN = {g: {"status": "pass", "detail": "ok"} for g in REQUIRED}
UNSIGNED = {"signed": False, "status": "unsigned", "sha256": "X"}
SIGNED = {"signed": True, "status": "signed", "sha256": "X", "subject": "CN=Respected"}


class DecisionTests(unittest.TestCase):
    def test_all_green_but_unsigned_is_ready_not_publishable_and_names_the_blocker(self):
        d = evaluate(META, GREEN, UNSIGNED)
        self.assertEqual((d["release_ready"], d["signed"], d["publishable"]), (True, False, False))
        self.assertEqual([b["id"] for b in d["blockers"]], ["SIGNING-01"])
        self.assertEqual(d["blockers"][0]["status"], "unsigned")

    def test_signed_and_green_is_publishable_without_blockers(self):
        d = evaluate(META, GREEN, SIGNED)
        self.assertEqual((d["release_ready"], d["signed"], d["publishable"], d["blockers"]), (True, True, True, []))

    def test_a_signature_does_not_rescue_a_red_gate(self):
        for gate in REQUIRED:
            gates = {**GREEN, gate: {"status": "fail", "detail": "x"}}
            d = evaluate(META, gates, SIGNED)
            self.assertEqual((d["release_ready"], d["publishable"]), (False, False), gate)
            self.assertTrue(any(gate in b["text"] for b in d["blockers"]), gate)

    def test_a_missing_or_malformed_gate_is_red(self):
        for gate in REQUIRED:
            self.assertFalse(evaluate(META, {k: v for k, v in GREEN.items() if k != gate}, SIGNED)["release_ready"], gate)
            for junk in (None, "pass", {"status": "PASS"}, {"status": None}, {}):
                self.assertFalse(evaluate(META, {**GREEN, gate: junk}, SIGNED)["release_ready"], (gate, junk))

    def test_unclean_tree_missing_sha_and_elevation_are_red(self):
        for bad in ({"tree_clean": False}, {"tree_clean": None}, {"commit_sha": ""}, {"elevated": True}, {"elevated": None}):
            self.assertFalse(evaluate({**META, **bad}, GREEN, SIGNED)["release_ready"], bad)

    def test_signature_shapes_that_are_not_a_valid_signature(self):
        for sig in (None, {}, {"signed": "yes"}, {"signed": 1}, {"signed": False, "status": "cert_expired"}, {"signed": False, "status": "tampered"}):
            d = evaluate(META, GREEN, sig)
            self.assertFalse(d["signed"], sig)
            self.assertFalse(d["publishable"], sig)

    def test_every_required_gate_has_a_producer(self):
        self.assertTrue(set(TEST_GROUPS) < set(REQUIRED))
        self.assertEqual(len(REQUIRED), len(set(REQUIRED)))


class GroupTests(unittest.TestCase):
    OUT = {"tests.engine.test_x.A.t1": "ok", "tests.engine.test_x.A.t2": "ok", "tests.engine.test_xy.B.t": "fail", "tests.engine.test_z.C.t": "ok"}

    def test_all_ok_passes_and_counts(self):
        r = group_result(self.OUT, ("tests.engine.test_x", "tests.engine.test_z"))
        self.assertEqual((r["status"], r["tests"]), ("pass", 3))

    def test_prefix_does_not_match_a_longer_module_name(self):
        self.assertEqual(group_result(self.OUT, ("tests.engine.test_x",))["status"], "pass")  # test_xy is another module

    def test_skip_fail_error_and_empty_groups_are_red(self):
        for value in ("skip", "fail", "error"):
            r = group_result({**self.OUT, "tests.engine.test_x.A.t1": value}, ("tests.engine.test_x",))
            self.assertEqual(r["status"], "fail", value)
            self.assertIn(value, r["problems"][0])
        r = group_result(self.OUT, ("tests.engine.test_missing",))
        self.assertEqual(r["status"], "fail")
        self.assertIn("no tests ran", r["problems"][0])
        self.assertEqual(group_result(self.OUT, ("tests.engine.test_x", "tests.engine.test_missing"))["status"], "fail")


class RoadmapTests(unittest.TestCase):
    TEXT = """| `B3-01.01` | a | P0 / L | `x` |
| `B3-01.02` | b | P0 / M | `x` |
| `B3-01.03` | c | P1 / M | `x` |
| `B3-09.04` | gate | P0 / L | `x` |
#### B3-01.01 — a

- [x] **Tamamlandı** — ok
#### B3-01.02 — b

- [ ] **Tamamlandı** — todo
#### B3-01.03 — c

- [ ] **Tamamlandı** — todo
#### B3-09.04 — gate

- [ ] **Tamamlandı** — todo
"""

    def test_only_open_p0_cards_other_than_the_gate_itself_count(self):
        self.assertEqual(roadmap_open_p0(self.TEXT), (["B3-01.02"], 4))

    def test_a_card_without_a_checkbox_counts_as_open(self):
        self.assertEqual(roadmap_open_p0(self.TEXT.replace("#### B3-01.01 — a\n\n- [x] **Tamamlandı** — ok\n", ""))[0], ["B3-01.01", "B3-01.02"])

    def test_the_real_roadmap_parses_into_many_cards(self):
        from pathlib import Path
        text = (Path(__file__).resolve().parents[2] / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        open_ids, total = roadmap_open_p0(text)
        self.assertGreaterEqual(total, 30)
        self.assertNotIn("B3-09.04", open_ids)


class ManifestTests(unittest.TestCase):
    def manifest(self, sig=UNSIGNED):
        return build_manifest(META, copy.deepcopy(GREEN), sig)

    def test_untouched_manifest_verifies(self):
        self.assertEqual(verify_manifest(self.manifest(), META["commit_sha"]), [])

    def test_wrong_commit(self):
        self.assertTrue(any("checkout is" in p for p in verify_manifest(self.manifest(), "b" * 40)))

    def test_flipping_a_decision_flag_is_caught_even_with_the_hash_recomputed(self):
        red = build_manifest(META, {**GREEN, "full_suite": {"status": "fail", "detail": "x"}}, UNSIGNED)
        forged = {k: v for k, v in red.items() if k != "body_sha256"}
        forged["release_ready"] = True
        from tests.tools.release_gate import sha256_text
        import json
        forged["body_sha256"] = sha256_text(json.dumps(forged, sort_keys=True, ensure_ascii=True))
        problems = verify_manifest(forged, META["commit_sha"])
        self.assertTrue(any("release_ready" in p for p in problems), problems)

    def test_editing_a_gate_or_the_signature_breaks_the_hash(self):
        m = self.manifest()
        m["gates"]["full_suite"]["detail"] = "edited"
        self.assertTrue(any("edited" in p for p in verify_manifest(m, META["commit_sha"])))
        m = self.manifest()
        m["signature"] = SIGNED
        self.assertTrue(verify_manifest(m, META["commit_sha"]))

    def test_garbage_is_rejected(self):
        for junk in (None, [], {}, {"schema": 2}, "x"):
            self.assertTrue(verify_manifest(junk, META["commit_sha"]), junk)


if __name__ == "__main__":
    unittest.main()
