import test from 'node:test';
import assert from 'node:assert/strict';
import { moveGroup, orderGroups, stepGroup } from '../src/grouporder.ts';

test('saved order wins, vanished groups drop out, new groups append in appearance order', () => {
  assert.deepEqual(orderGroups(['a', 'b', 'c', 'd'], ['c', 'x', 'a']), ['c', 'a', 'b', 'd']);
  assert.deepEqual(orderGroups([], ['a']), []);
});

test('dragging puts the group where the target was, up or down; nonsense changes nothing', () => {
  assert.deepEqual(moveGroup(['a', 'b', 'c'], 'a', 'c'), ['b', 'c', 'a']);
  assert.deepEqual(moveGroup(['a', 'b', 'c'], 'c', 'a'), ['c', 'a', 'b']);
  assert.deepEqual(moveGroup(['a', 'b'], 'a', 'a'), ['a', 'b']);
  assert.deepEqual(moveGroup(['a', 'b'], 'z', 'a'), ['a', 'b']);
});

test('keyboard steps stop at both ends', () => {
  assert.deepEqual(stepGroup(['a', 'b', 'c'], 'b', -1), ['b', 'a', 'c']);
  assert.deepEqual(stepGroup(['a', 'b', 'c'], 'c', 1), ['a', 'b', 'c']);
  assert.deepEqual(stepGroup(['a', 'b', 'c'], 'a', -1), ['a', 'b', 'c']);
});
