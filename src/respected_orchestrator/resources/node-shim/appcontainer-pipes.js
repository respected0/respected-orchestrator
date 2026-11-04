// AppContainer cannot create named pipes outside \\.\pipe\LOCAL\; libuv's uv_spawn only knows \\?\pipe\uv\ and then
// retries on ACCESS_DENIED forever, so any child_process call with piped stdio hangs. Pipes are made under LOCAL\ here.
// Also, JS fs.realpath lstat()s every component from the drive root, which an AppContainer may not read (EPERM);
// the native variant resolves the final path in one call and works.
'use strict';
const cp = require('child_process');
const net = require('net');
const fs = require('fs');
const crypto = require('crypto');
const { PassThrough } = require('stream');
const os = require('os');
const path = require('path');

const B = String.fromCharCode(92);
// JS fs.realpath lstat()s every component from the drive root, which an AppContainer may not read (EPERM); the
// native variant resolves the final path in one call. Callers that use `.native` keep working.
const nativeSync = fs.realpathSync.native;
const nativeAsync = fs.realpath.native;
nativeSync.native = nativeSync;
nativeAsync.native = nativeAsync;
fs.realpathSync = nativeSync;
fs.realpath = nativeAsync;
fs.promises.realpath = (target, options) => new Promise((ok, no) => nativeAsync(target, options, (e, v) => (e ? no(e) : ok(v))));

const realSpawn = cp.ChildProcess.prototype.spawn;

// One piped stdio slot: the child inherits a client fd, the parent talks to the server end through a PassThrough.
function makePipe(childReads) {
  const name = B + B + '.' + B + 'pipe' + B + 'LOCAL' + B + 'respected-' + process.pid + '-' + crypto.randomBytes(8).toString('hex');
  const server = net.createServer();
  server.listen(name); // the pipe instance exists once listen() returns
  const stream = new PassThrough();
  server.once('connection', (socket) => {
    server.close();
    if (childReads) stream.pipe(socket); else socket.pipe(stream);
  });
  return { fd: fs.openSync(name, childReads ? 'r' : 'w'), stream };
}

cp.ChildProcess.prototype.spawn = function (options) {
  let stdio = options.stdio || 'pipe';
  if (typeof stdio === 'string') stdio = [stdio, stdio, stdio];
  const isPipe = (s) => s === undefined || s === null || s === 'pipe' || s === 'overlapped';
  if (stdio.includes('ipc')) {
    throw Object.assign(new Error('spawn EACCES: IPC channels are not available in the worker sandbox'), { code: 'EACCES' });
  }
  const pipes = stdio.map((s, i) => (isPipe(s) ? makePipe(i === 0) : null));
  const wrapped = stdio.map((s, i) => (pipes[i] ? pipes[i].fd : s));
  let result;
  try {
    result = realSpawn.call(this, Object.assign({}, options, { stdio: wrapped }));
  } finally {
    for (const pipe of pipes) if (pipe) fs.closeSync(pipe.fd);
  }
  pipes.forEach((pipe, i) => {
    if (pipe) this[['stdin', 'stdout', 'stderr'][i] || 'stdio'] = pipe.stream;
  });
  this.stdio = [this.stdin || null, this.stdout || null, this.stderr || null];
  // 'close' waits for the output streams, as it does with libuv pipes.
  const outputs = pipes.slice(1).filter(Boolean).map((p) => p.stream);
  const emit = this.emit;
  let open = outputs.length;
  let held = null;
  this.emit = function (event, ...args) {
    if (event === 'close' && open) { held = args; return true; }
    return emit.call(this, event, ...args);
  };
  for (const stream of outputs) {
    stream.once('close', () => { if (--open === 0 && held) { const args = held; held = null; emit.call(this, 'close', ...args); } });
  }
  return result;
};

// spawnSync/execSync/execFileSync reach libuv through this binding; piped slots go through temp files instead.
const syncBinding = process.binding('spawn_sync');
const realSync = syncBinding.spawn;
syncBinding.spawn = function (options) {
  const slots = options.stdio.map((s, i) => {
    if (!s || s.type !== 'pipe') return null;
    const file = path.join(process.env.RESPECTED_WORKER_TMP || os.tmpdir(), 'respected-sync-' + process.pid + '-' + crypto.randomBytes(8).toString('hex'));
    if (i === 0) fs.writeFileSync(file, s.input || '');
    return { file, fd: fs.openSync(file, i === 0 ? 'r' : 'w') };
  });
  const stdio = options.stdio.map((s, i) => (slots[i] ? { type: 'fd', fd: slots[i].fd } : s));
  try {
    const result = realSync.call(this, Object.assign({}, options, { stdio }));
    if (result.output === undefined || result.output === null) result.output = [];
    slots.forEach((slot, i) => { if (slot && i > 0) { fs.closeSync(slot.fd); slot.fd = -1; result.output[i] = fs.readFileSync(slot.file); } });
    return result;
  } finally {
    slots.forEach((slot) => { if (slot) { if (slot.fd >= 0) fs.closeSync(slot.fd); fs.rmSync(slot.file, { force: true }); } });
  }
};
