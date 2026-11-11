import test from 'node:test';
import assert from 'node:assert/strict';
import { displayPath, orderInstructions, scopeText, type Instruction } from '../src/instructionmodel.ts';

const at = (path: string, name: string, folder: string, scope: string, exists = true): Instruction => ({ path, name, folder, scope, exists });

test('scope labels are Turkish and unknown scopes stay as they came', () => {
  assert.equal(scopeText('root'), 'Proje kökü');
  assert.equal(scopeText('subfolder'), 'Alt klasör');
  assert.equal(scopeText('user'), 'Kullanıcı');
  assert.equal(scopeText('other'), 'other');
});

test('display path is relative to the project root and home-level files use ~', () => {
  const root = String.raw`C:\proje`;
  assert.equal(displayPath(at(String.raw`C:\proje\AGENTS.md`, 'AGENTS.md', String.raw`C:\proje`, 'root'), root), 'AGENTS.md');
  assert.equal(displayPath(at(String.raw`C:\proje\docs\api\CLAUDE.md`, 'CLAUDE.md', String.raw`C:\proje\docs\api`, 'subfolder'), root), 'docs/api/CLAUDE.md');
  assert.equal(displayPath(at(String.raw`C:\proje\AGENTS.md`, 'AGENTS.md', String.raw`D:\başka`, 'subfolder'), root), 'D:/başka/AGENTS.md');
  assert.equal(displayPath(at(String.raw`C:\Users\x\.claude\CLAUDE.md`, 'CLAUDE.md', String.raw`C:\Users\x\.claude`, 'user'), root), '~/.claude/CLAUDE.md');
  assert.equal(displayPath(at(String.raw`C:\Users\x\.codex\AGENTS.md`, 'AGENTS.md', String.raw`C:\Users\x\.codex`, 'user'), root), '~/.codex/AGENTS.md');
});

test('root files come first, then subfolders by path, then user files; duplicates drop', () => {
  const root = String.raw`C:\p`;
  const list = [
    at(String.raw`C:\Users\x\.codex\AGENTS.md`, 'AGENTS.md', String.raw`C:\Users\x\.codex`, 'user'),
    at(String.raw`C:\p\b\AGENTS.md`, 'AGENTS.md', String.raw`C:\p\b`, 'subfolder'),
    at(String.raw`C:\p\CLAUDE.md`, 'CLAUDE.md', String.raw`C:\p`, 'root'),
    at(String.raw`C:\p\a\CLAUDE.md`, 'CLAUDE.md', String.raw`C:\p\a`, 'subfolder'),
    at(String.raw`C:\p\AGENTS.md`, 'AGENTS.md', String.raw`C:\p`, 'root'),
    at(String.raw`C:\p\a\claude.md`, 'claude.md', String.raw`C:\p\a`, 'subfolder'),
  ];
  assert.deepEqual(orderInstructions(list, root).map((i) => displayPath(i, root)), [
    'AGENTS.md', 'CLAUDE.md', 'a/CLAUDE.md', 'b/AGENTS.md', '~/.codex/AGENTS.md',
  ]);
  assert.equal(orderInstructions([...list, list[0]], root).length, 5);
});