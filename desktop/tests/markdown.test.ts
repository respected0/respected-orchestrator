import test from 'node:test';
import assert from 'node:assert/strict';
import { inline, parseMarkdown } from '../src/markdown.ts';

test('block syntax: headings, lists, quotes, rules and fenced code', () => {
  const blocks = parseMarkdown('# Başlık\n\n- bir\n- **iki**\n\n1. ilk\n2. son\n\n> alıntı\n\n---\n\n```ts\nconst a = 1;\n```');
  assert.deepEqual(blocks.map((b) => b.t), ['h', 'list', 'list', 'quote', 'hr', 'code']);
  assert.deepEqual(blocks[0], { t: 'h', level: 1, text: 'Başlık' });
  assert.deepEqual(blocks[1], { t: 'list', ordered: false, items: [[{ t: 'text', v: 'bir' }], [{ t: 'strong', v: 'iki' }]] });
  assert.deepEqual(blocks[2], { t: 'list', ordered: true, items: [[{ t: 'text', v: 'ilk' }], [{ t: 'text', v: 'son' }]] });
  assert.deepEqual(blocks[5], { t: 'code', lang: 'ts', text: 'const a = 1;' });
});

test('paragraphs join wrapped lines and stop at the next block', () => {
  assert.deepEqual(parseMarkdown('bir\niki\n\nüç'), [
    { t: 'p', inlines: [{ t: 'text', v: 'bir iki' }] },
    { t: 'p', inlines: [{ t: 'text', v: 'üç' }] },
  ]);
});

test('inline syntax: code, strong, em and only safe links', () => {
  assert.deepEqual(inline('a `x*y` **b** *c* [d](https://e.f)'), [
    { t: 'text', v: 'a ' }, { t: 'code', v: 'x*y' }, { t: 'text', v: ' ' }, { t: 'strong', v: 'b' },
    { t: 'text', v: ' ' }, { t: 'em', v: 'c' }, { t: 'text', v: ' ' }, { t: 'link', v: 'd', href: 'https://e.f' },
  ]);
  assert.deepEqual(inline('[x](javascript:alert(1))'), [{ t: 'text', v: '[x](javascript:alert(1))' }]);
  assert.deepEqual(inline('[x](/yol)'), [{ t: 'text', v: '[x](/yol)' }]);
});

test('raw HTML and scripts stay text', () => {
  assert.deepEqual(parseMarkdown('<script>alert(1)</script>'), [{ t: 'p', inlines: [{ t: 'text', v: '<script>alert(1)</script>' }] }]);
  assert.deepEqual(inline('<b>kalın</b>'), [{ t: 'text', v: '<b>kalın</b>' }]);
});

test('empty input makes no blocks and an unclosed fence still yields code', () => {
  assert.deepEqual(parseMarkdown('  \n\n'), []);
  assert.deepEqual(parseMarkdown('```\na\n'), [{ t: 'code', lang: '', text: 'a\n' }]);
});
