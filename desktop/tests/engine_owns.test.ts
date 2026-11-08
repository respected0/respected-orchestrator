// The engine owns models, defaults, history, titles, folders and totals; the screen only draws them and forwards choices.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';

const dir = new URL('../src/', import.meta.url);
const sources = readdirSync(dir).filter((f) => /\.(ts|tsx)$/.test(f)).map((f) => [f, readFileSync(new URL(f, dir), 'utf8')] as const);

test('the screen holds no model name, agent list, history store or session-folder map', () => {
  for (const [file, src] of sources) {
    for (const word of ['deepseek', 'DEFAULT_MODEL', 'orch.history', 'orch.session-roots', 'titleOf', 'usageOf', 'cliIdOf', 'startProblem']) {
      assert.ok(!src.includes(word), `${file} still has ${word}`);
    }
  }
});

test('browser storage keeps only view preferences', () => {
  const allowed = /orch\.(theme|sort|side-hidden|group-order|group-collapsed)|FLAG_KEY|DISMISS_KEY|key\b|KEY\b/;
  for (const [file, src] of sources) {
    for (const line of src.split('\n').filter((l) => /localStorage\.(get|set)Item/.test(l))) {
      assert.match(line, allowed, `${file}: ${line.trim().slice(0, 100)}`);
    }
  }
});
