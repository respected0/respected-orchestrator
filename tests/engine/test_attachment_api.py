"""Screenshot attachments over IPC (B4-07): the renderer can stage and preview, only the native presence connection can commit or share."""
import base64
import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import attachment_api, local_api
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.evidence import save_signed
from tests.engine.test_attachment import png

RUN = "run-20261108000000-abcdef123456"
TOKEN = "tok-0123456789abcdef"
IMAGE = png(extra=[(b"tEXt", b"Comment\x00my secret")], rect=(2, 1, 5, 3))


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.ctx = EngineContext(Path(temp.name).resolve() / "data")
        self.ctx.data_root.mkdir(parents=True, exist_ok=True)
        directory = self.ctx.run_dir(RUN)
        directory.mkdir(parents=True, exist_ok=True)
        save_signed(self.ctx, directory / "status.json", {"run_id": RUN, "status": "queued"})
        self.renderer = local_api.LocalApi(self.ctx, TOKEN)
        self.human = local_api.LocalApi(self.ctx, TOKEN, origin=Origin.HUMAN, only=local_api.HUMAN_COMMANDS)
        self.n = 0
        self.settings(screenshot_enabled=True)

    def settings(self, **values):
        (self.ctx.data_root / "settings.json").write_text(json.dumps(values), "utf-8")

    def call(self, cmd, payload=None, api=None):
        self.n += 1
        return (api or self.renderer).handle({"ipc": local_api.IPC, "id": f"req-{self.n:08}", "session": TOKEN, "cmd": cmd, "payload": payload or {}})

    def upload(self, image=IMAGE, permission="granted", step=40):
        token = self.call("attachment.arm", {"permission": permission})["result"]["token"]
        for seq, i in enumerate(range(0, len(image), step)):
            r = self.call("attachment.part", {"token": token, "seq": seq, "chunk": base64.b64encode(image[i:i + step]).decode()})
            self.assertTrue(r["ok"], r)
        return token

    def stage(self, **kw):
        token = self.upload(**kw)
        return self.call("attachment.stage", {"token": token})


class StageTests(Base):
    def test_off_by_default_and_without_permission_nothing_is_taken(self):
        self.settings()
        self.assertIn("CAPTURE_OFF", self.call("attachment.arm", {"permission": "granted"})["error"]["message"])
        self.settings(screenshot_enabled=True)
        for p in ("denied", None):
            self.assertIn("NO_PERMISSION", self.call("attachment.arm", {"permission": p})["error"]["message"])
        self.assertEqual(self.call("attachment.status")["result"]["state"], "idle")

    def test_stage_strips_metadata_and_the_preview_is_the_cleaned_bytes(self):
        out = self.stage()
        self.assertTrue(out["ok"], out)
        info = out["result"]
        self.assertGreater(info["metadata_removed_bytes"], 0)
        shown = base64.b64decode(self.call("attachment.preview", {"stage_id": info["stage_id"]})["result"]["data"])
        self.assertNotIn(b"secret", shown)
        self.assertEqual(hashlib.sha256(shown).hexdigest(), info["sha256"])

    def test_chunks_out_of_order_wrong_token_or_bad_base64_discard_everything(self):
        token = self.call("attachment.arm", {"permission": "granted"})["result"]["token"]
        self.assertIn("BAD_PART", self.call("attachment.part", {"token": token, "seq": 1, "chunk": "AAAA"})["error"]["message"])
        self.assertIn("NOT_ARMED", self.call("attachment.part", {"token": token, "seq": 0, "chunk": "AAAA"})["error"]["message"])
        token = self.call("attachment.arm", {"permission": "granted"})["result"]["token"]
        self.assertIn("NOT_ARMED", self.call("attachment.part", {"token": "other", "seq": 0, "chunk": "AAAA"})["error"]["message"])
        self.assertIn("NOT_ARMED", self.call("attachment.stage", {"token": token})["error"]["message"])

    def test_a_bad_image_is_refused_and_leaves_no_staging_file(self):
        out = self.stage(image=b"<svg xmlns='http://www.w3.org/2000/svg'/>")
        self.assertIn("BAD_FORMAT", out["error"]["message"])
        self.assertEqual(list((self.ctx.data_root / "staging").glob("*")) if (self.ctx.data_root / "staging").exists() else [], [])

    def test_cancel_drops_the_upload_and_the_staged_file(self):
        info = self.stage()["result"]
        self.call("attachment.cancel", {"stage_id": info["stage_id"]})
        self.assertIn("NOT_FOUND", self.call("attachment.preview", {"stage_id": info["stage_id"]})["error"]["message"])
        self.upload()
        self.assertEqual(self.call("attachment.cancel")["result"], {"state": "idle", "held": 0})

    def test_staging_expires_and_sweeps(self):
        info = self.stage()["result"]
        self.assertEqual(attachment_api.sweep_staging(self.ctx, now=time.time() + 601), 2)
        self.assertIn("NOT_FOUND", self.call("attachment.describe", {"stage_id": info["stage_id"]})["error"]["message"])
        self.assertIn("BAD_ID", self.call("attachment.describe", {"stage_id": "../../etc/passwd"})["error"]["message"])


class AuthorityTests(Base):
    def test_the_renderer_cannot_commit_share_or_revoke(self):
        info = self.stage()["result"]
        for cmd, payload in (("attachment.commit", {"stage_id": info["stage_id"], "run_id": RUN, "sha256": info["sha256"]}),
                             ("attachment.share", {"run_id": RUN, "attachment_id": "att-" + "a" * 16, "provider": "x"}),
                             ("attachment.revoke", {"run_id": RUN, "attachment_id": "att-" + "a" * 16})):
            self.assertEqual(self.call(cmd, payload)["error"]["code"], "FORBIDDEN", cmd)
        self.assertEqual(self.call("attachment.list", {"run_id": RUN})["result"]["attachments"], [])

    def test_the_human_connection_can_only_do_the_privileged_part(self):
        self.assertEqual(self.call("attachment.arm", {"permission": "granted"}, api=self.human)["error"]["code"], "FORBIDDEN")
        self.assertEqual(self.call("attachment.preview", {"stage_id": "stg-" + "a" * 16}, api=self.human)["error"]["code"], "FORBIDDEN")

    def test_workers_cannot_touch_attachments_at_all(self):
        worker = local_api.LocalApi(self.ctx, TOKEN, origin=Origin.WORKER)
        for cmd in ("attachment.status", "attachment.arm", "attachment.list"):
            self.assertEqual(self.call(cmd, {"run_id": RUN}, api=worker)["error"]["code"], "FORBIDDEN", cmd)


class CommitShareTests(Base):
    def commit(self, info, **kw):
        return self.call("attachment.commit", {"stage_id": info["stage_id"], "run_id": RUN, "sha256": kw.get("sha256", info["sha256"]), "redacted_regions": kw.get("regions", 1)}, api=self.human)

    def test_commit_binds_the_previewed_digest_and_consumes_the_staged_file(self):
        info = self.stage()["result"]
        self.assertIn("PREVIEW_REQUIRED", self.commit(info, sha256="0" * 64)["error"]["message"])
        out = self.commit(info)
        self.assertTrue(out["ok"], out)
        self.assertEqual((out["result"]["visibility"], out["result"]["shared_with_model"], out["result"]["redacted_regions"]), ("task_only", False, 1))
        self.assertIn("NOT_FOUND", self.call("attachment.describe", {"stage_id": info["stage_id"]})["error"]["message"])
        listed = self.call("attachment.list", {"run_id": RUN})["result"]["attachments"]
        self.assertEqual([(a["id"], a["consent"]["state"]) for a in listed], [(out["result"]["id"], "none")])

    def test_wrong_run_and_started_runs_are_refused(self):
        info = self.stage()["result"]
        bad = self.call("attachment.commit", {"stage_id": info["stage_id"], "run_id": "run-20261108000000-ffffffffffff", "sha256": info["sha256"]}, api=self.human)
        self.assertIn("WRONG_RUN", bad["error"]["message"])
        save_signed(self.ctx, self.ctx.run_dir(RUN) / "status.json", {"run_id": RUN, "status": "running"})
        self.assertIn("WRONG_RUN", self.commit(info)["error"]["message"])

    def test_share_is_a_second_human_decision_and_revoke_ends_it(self):
        info = self.stage()["result"]
        att = self.commit(info)["result"]["id"]
        shared = self.call("attachment.share", {"run_id": RUN, "attachment_id": att, "provider": "Acme Vision"}, api=self.human)
        self.assertTrue(shared["ok"], shared)
        row = self.call("attachment.list", {"run_id": RUN})["result"]["attachments"][0]
        self.assertEqual((row["consent"]["state"], row["consent"]["provider"]), ("active", "Acme Vision"))
        self.assertTrue(self.call("attachment.revoke", {"run_id": RUN, "attachment_id": att}, api=self.human)["ok"])
        self.assertEqual(self.call("attachment.list", {"run_id": RUN})["result"]["attachments"][0]["consent"]["state"], "revoked")

    def test_delete_removes_everything_of_the_run(self):
        self.commit(self.stage()["result"])
        self.assertEqual(self.call("attachment.delete", {"run_id": RUN})["result"]["removed"], 2)
        self.assertEqual(self.call("attachment.list", {"run_id": RUN})["result"]["attachments"], [])
        self.assertIn("WRONG_RUN", self.call("attachment.delete", {"run_id": "../x"})["error"]["message"])


if __name__ == "__main__":
    unittest.main()
