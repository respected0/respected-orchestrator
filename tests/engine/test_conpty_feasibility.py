"""B3-03.02 gate: can a real interactive (ConPTY) process run INSIDE the AppContainer with the same negative guarantees?

Every test drives a real AppContainer child attached to a pseudoconsole. No test passes by skipping on Windows: if the
sandbox cannot start, setUp raises and the test fails (unsupported_elevated is the only legitimate refusal, and it is asserted).
"""
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

if os.name == "nt":
    sys.path.insert(0, str(Path(__file__).parent))
    import conpty_experiment as ce
    from respected_orchestrator.engine import appcontainer as ac


@unittest.skipUnless(os.name == "nt", "ConPTY + AppContainer are Windows-only")
class ConPtyInAppContainerTests(unittest.TestCase):
    def setUp(self):
        if ac._is_elevated():
            self.fail("run unelevated: the worker boundary is not enforced in an elevated session")
        self.tmp = Path(tempfile.mkdtemp(prefix="pty-gate-"))
        self.ws = self.tmp / "ws"
        self.outside = self.tmp / "outside"
        self.ws.mkdir()
        self.outside.mkdir()
        (self.outside / "secret.txt").write_text("TOP-SECRET")
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            p.close()

    def run_child(self, code, network="deny", wait=30, send=None):
        script = self.ws / f"child_{len(self.procs)}.py"
        script.write_text(code, encoding="utf-8")
        proc = ce.spawn_pty([sys.executable, str(script)], self.ws, dict(os.environ), allowed_roots=(self.ws,),
                            readonly_roots=(Path(sys.base_prefix),), network_mode=network)
        self.procs.append(proc)
        if send:
            send(proc)
        code = proc.wait(wait)
        time.sleep(0.4)
        return code, proc.text()

    def test_real_tty_and_only_channel_is_the_pty(self):
        # Parent's stdout is a captured pipe: nothing the child prints may reach it.
        runner = (
            "import sys,os,time;sys.path[:0]=[%r,%r];from pathlib import Path;import conpty_experiment as ce;"
            "from respected_orchestrator.engine import appcontainer as ac;ws=Path(%r);"
            "(ws/'c.py').write_text('import sys;print(\"CHILD-SAYS-HI\",sys.stdout.isatty(),sys.stdin.isatty(),flush=True)');"
            "p=ce.spawn_pty([sys.executable,str(ws/'c.py')],ws,dict(os.environ),allowed_roots=(ws,),readonly_roots=(Path(sys.base_prefix),),network_mode='deny');"
            "p.wait(30);time.sleep(0.4);sys.stderr.write('PTY:'+p.text());p.close()"
        ) % (str(Path(__file__).parents[2] / "src"), str(Path(__file__).parent), str(self.ws))
        done = subprocess.run([sys.executable, "-c", runner], capture_output=True, text=True, timeout=90)
        self.assertEqual(done.stdout, "", f"child leaked into the parent's stdout: {done.stdout!r}")
        self.assertIn("CHILD-SAYS-HI True True", done.stderr)  # reached the broker through the PTY, and it is a real tty

    def test_outside_file_access_is_denied_inside_the_pty(self):
        code, out = self.run_child(
            f"p={str(self.outside / 'secret.txt')!r}\n"
            "try:\n    print('READ-OK', open(p).read())\nexcept OSError as e:\n    print('READ-DENIED', e.errno)\n"
            f"try:\n    open({str(self.outside / 'new.txt')!r}, 'w').write('x'); print('WRITE-OK')\n"
            "except OSError as e:\n    print('WRITE-DENIED', e.errno)\n"
            "open('inside.txt','w').write('ok'); print('INSIDE-OK')\n")
        self.assertIn("READ-DENIED", out)
        self.assertIn("WRITE-DENIED", out)
        self.assertNotIn("TOP-SECRET", out)
        self.assertIn("INSIDE-OK", out)
        self.assertFalse((self.outside / "new.txt").exists())
        self.assertEqual((self.ws / "inside.txt").read_text(), "ok")

    def test_network_is_default_deny(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        accepted = []

        def accept():
            server.settimeout(8)
            try:
                accepted.append(server.accept())
            except OSError:
                pass
        threading.Thread(target=accept, daemon=True).start()
        try:
            code, out = self.run_child(
                "import socket\ns=socket.socket();s.settimeout(5)\n"
                f"try:\n    s.connect(('127.0.0.1',{port})); print('NET-OPEN')\n"
                "except OSError as e:\n    print('NET-DENIED')\n")
        finally:
            server.close()
        self.assertIn("NET-DENIED", out)
        self.assertNotIn("NET-OPEN", out)
        self.assertEqual(accepted, [])

    def test_child_of_the_pty_process_is_sandboxed_too(self):
        (self.ws / "grand.py").write_text(f"print(open({str(self.outside / 'secret.txt')!r}).read())", encoding="utf-8")
        code, out = self.run_child(
            "import subprocess,sys\n"
            "r=subprocess.run([sys.executable,'grand.py'],capture_output=True,text=True)\n"
            "print('GRANDCHILD-RC', r.returncode, 'TOP-SECRET' in r.stdout)\n")
        self.assertIn("GRANDCHILD-RC 1 False", out)

    def test_resize_reaches_the_child(self):
        def go(proc):
            time.sleep(1.5)
            proc.resize(120, 40)
        code, out = self.run_child(
            "import os,time\nprint('SIZE0', tuple(os.get_terminal_size()), flush=True)\ntime.sleep(4)\n"
            "print('SIZE1', tuple(os.get_terminal_size()), flush=True)\n", send=go)
        self.assertIn("SIZE0 (100, 30)", out)
        self.assertIn("SIZE1 (120, 40)", out)

    RAW_CHILD = (
        "import time,ctypes,msvcrt\n"
        "from ctypes import wintypes\n"
        "k=ctypes.WinDLL('kernel32');h=k.GetStdHandle(-10)\n"
        "m=wintypes.DWORD();k.GetConsoleMode(h,ctypes.byref(m));k.SetConsoleMode(h,m.value&~0x7)\n"
        "print('READY',flush=True)\n"
        "t=time.time()\n"
        "while time.time()-t<20 and not msvcrt.kbhit():\n"
        "    time.sleep(0.05)\n"
        "print('RAW-READ', hex(ord(msvcrt.getwch())) if msvcrt.kbhit() else 'none', flush=True)\n"
    )
    COOKED_CHILD = (
        "import signal,time\n"
        "g=[]\n"
        "signal.signal(signal.SIGINT,lambda *a:g.append(1))\n"
        "print('READY',flush=True)\n"
        "for i in range(100):\n"
        "    time.sleep(0.1)\n"
        "    if g:\n"
        "        print('SIGINT-SEEN',flush=True)\n"
        "        break\n"
        "print('LOOP-END',flush=True)\n"
    )

    def wait_for(self, proc, marker, seconds=15):
        deadline = time.monotonic() + seconds
        while marker not in proc.text() and time.monotonic() < deadline:
            time.sleep(0.1)

    def test_ctrl_c_byte_reaches_a_raw_mode_program(self):
        """Agent TUIs run in raw mode and read 0x03 themselves: interrupt-by-input works for them."""
        def go(proc):
            self.wait_for(proc, "READY")
            proc.send(bytes([3]))
        code, out = self.run_child(self.RAW_CHILD, wait=40, send=go)
        self.assertIn("RAW-READ 0x3", out)

    def test_ctrl_c_signal_is_not_delivered_inside_the_appcontainer_so_hard_stop_is_the_interrupt(self):
        """Measured limit (ADR-024): a cooked-mode child never gets SIGINT from ConPTY inside the AppContainer.
        The supported interrupt is the byte for raw-mode agents plus a hard stop (kill) for everything else."""
        script = self.ws / "cooked.py"
        script.write_text(self.COOKED_CHILD, encoding="utf-8")
        proc = ce.spawn_pty([sys.executable, str(script)], self.ws, dict(os.environ), allowed_roots=(self.ws,),
                            readonly_roots=(Path(sys.base_prefix),), network_mode="deny")
        self.procs.append(proc)
        self.wait_for(proc, "READY")
        proc.send(bytes([3]))
        time.sleep(3)
        self.assertIsNone(proc.base.poll(), "child died from the ctrl-c byte: ConPTY signal delivery now works, update ADR-024")
        self.assertNotIn("SIGINT-SEEN", proc.text())
        proc.base.kill()
        self.assertIsNotNone(proc.wait(10))  # the hard stop works

    def test_one_megabyte_of_output_arrives_without_deadlock(self):
        code, out = self.run_child("import sys\nfor i in range(1024):\n    sys.stdout.write(('%04d' % i) + 'x' * 1019 + '\\n')\n"
                                   "sys.stdout.flush()\nprint('DONE-1MB', flush=True)\n", wait=60)
        self.assertEqual(code, 0)
        self.assertIn("DONE-1MB", out)
        self.assertGreaterEqual(len(out), 1024 * 1024)

    def test_terminal_escapes_stay_on_the_pty_channel_for_the_broker_to_filter(self):
        code, out = self.run_child("print('\\x1b]0;evil-title\\x07\\x1b[31mred\\x1b[0m')\n")
        self.assertIn("\x1b]0;evil-title\x07", out)  # raw control sequences DO arrive: the broker/renderer must filter (B3-03.05)
        self.assertIn("red", out)

    def test_input_written_by_the_broker_reaches_the_child(self):
        def go(proc):
            deadline = time.monotonic() + 15
            while "ASK" not in proc.text() and time.monotonic() < deadline:
                time.sleep(0.1)
            proc.send(b"hello broker\r")
        code, out = self.run_child("print('ASK', flush=True)\nline=input()\nprint('GOT:'+line, flush=True)\n", wait=40, send=go)
        self.assertIn("GOT:hello broker", out)


if __name__ == "__main__":
    unittest.main()
