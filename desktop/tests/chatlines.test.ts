import test from 'node:test';
import assert from 'node:assert/strict';
import { toMessages } from '../src/chatlines.ts';

test('user lines become user messages, agent lines are merged', () => {
  assert.deepEqual(toMessages(['> merhaba', '', 'selam', 'nasıl yardım', '', '> peki']), [
    { who: 'user', text: 'merhaba' }, { who: 'agent', text: 'selam\nnasıl yardım' }, { who: 'user', text: 'peki' },
  ]);
  assert.deepEqual(toMessages(['', '']), []);
});
