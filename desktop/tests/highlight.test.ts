import test from 'node:test';
import assert from 'node:assert/strict';
import { extOf, highlightLine } from '../src/highlight.ts';

const kinds = (line: string, ext: string) => highlightLine(line, ext).filter((t) => t.k !== 'plain').map((t) => `${t.k}:${t.v}`);

test('the tokens always add up to the original line', () => {
  for (const [l, e] of [['const a = "x"; // not', 'ts'], ['def f(x): return 1  # c', 'py'], ['<div class="a">hi</div> <!-- c -->', 'html'], ['', 'ts'], ['   ', 'py'], ["it's 'odd", 'ts']] as const) {
    assert.equal(highlightLine(l, e).map((t) => t.v).join(''), l);
  }
});

test('comments, strings, numbers and keywords are told apart per language', () => {
  assert.deepEqual(kinds('const n = 42; // sayı', 'ts'), ['keyword:const', 'number:42', 'comment:// sayı']);
  assert.deepEqual(kinds('x = "a # b"  # gerçek', 'py'), ['string:"a # b"', 'comment:# gerçek']); // a # inside a string is not a comment
  assert.deepEqual(kinds('<a href="u">', 'html'), ['keyword:<a', 'string:"u"']);
  assert.deepEqual(kinds('a # b', 'ts'), []); // # is not a comment in TypeScript
});

test('extension of a path, also for dotfiles', () => {
  assert.equal(extOf('C:\\p\\src\\main.TSX'), 'tsx');
  assert.equal(extOf('/a/.gitignore'), 'gitignore');
  assert.equal(extOf('Makefile'), 'makefile');
});
