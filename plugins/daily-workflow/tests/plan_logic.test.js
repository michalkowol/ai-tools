// node --test plugins/daily-workflow/tests/plan_logic.test.js
// Loads the plan page script the same way the browser does (a classic script on globalThis).
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

vm.runInThisContext(fs.readFileSync(path.join(__dirname, '..', 'scripts', 'wl', 'assets', 'plan.js'), 'utf8'),
  { filename: 'plan.js' });
const L = globalThis.PlanLogic;
const items = [
  { key: 'priorities|https://www.notion.so/a', label: 'Task A', done: false },
  { key: 'code_review|https://github.com/org/shop/pull/412', label: 'org/shop#412 Batch', done: false },
  { key: 'daily_update.today|Ship it', label: 'Ship it', done: true },
];

test('pending ticks skip items the JSON already marks done', () => {
  const ticks = { 'priorities|https://www.notion.so/a': true, 'daily_update.today|Ship it': true };
  assert.deepEqual(L.pending(items, ticks).map((i) => i.label), ['Task A']);
});

test('prompt has the done header and one line per item', () => {
  const lines = L.prompt('plans/2026-11-26.json', items.slice(0, 2)).split('\n');
  assert.equal(lines[0], '/daily-workflow:morning done plans/2026-11-26.json');
  assert.deepEqual(JSON.parse(lines[2]), { key: 'code_review|https://github.com/org/shop/pull/412', label: 'org/shop#412 Batch' });
  assert.equal(lines.length, 3);
});

test('prune drops ticks the JSON already has and keeps unknown keys', () => {
  const ticks = { 'daily_update.today|Ship it': true, 'resolved|gone': true, 'x|off': false };
  assert.deepEqual(L.prune(items, ticks), { 'resolved|gone': true });
});

test('storage key is per plan file', () => {
  assert.equal(L.storageKey('plans/2026-11-26.json'), 'daily-workflow:plan:plans/2026-11-26.json');
});
