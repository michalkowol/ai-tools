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
  { key: 'priorities|https://www.notion.so/a', label: 'Task A', done: false, sent: [] },
  { key: 'code_review|https://github.com/org/shop/pull/412', label: 'org/shop#412 Batch', done: false, sent: ['ping Alice'] },
  { key: 'daily_update.today|Ship it', label: 'Ship it', done: true, sent: [] },
];

test('pending ticks skip items the JSON already marks done', () => {
  const ticks = { 'priorities|https://www.notion.so/a': true, 'daily_update.today|Ship it': true };
  assert.deepEqual(L.pending(items, ticks).map((i) => i.label), ['Task A']);
});

test('lines carry new ticks and new notes, the note for the whole plan last', () => {
  const ticks = { 'priorities|https://www.notion.so/a': true, 'daily_update.today|Ship it': true };
  const notes = {
    'priorities|https://www.notion.so/a': '  set the reminder to 1 Dec ',
    'code_review|https://github.com/org/shop/pull/412': 'ping Alice',
    'daily_update.today|Ship it': 'mention the release',
    plan: 'move everything unfinished to tomorrow',
  };
  assert.deepEqual(L.lines(items, ticks, notes, []), [
    { key: 'priorities|https://www.notion.so/a', label: 'Task A', done: true, note: 'set the reminder to 1 Dec' },
    { key: 'daily_update.today|Ship it', label: 'Ship it', note: 'mention the release' },
    { key: 'plan', label: 'Whole plan', note: 'move everything unfinished to tomorrow' },
  ]);
  assert.deepEqual(L.lines(items, {}, { plan: 'same' }, ['same']), []);
  assert.equal(L.summary(L.lines(items, ticks, notes, [])), '1 done · 3 notes');
  assert.equal(L.summary(L.lines(items, {}, { plan: 'x' }, [])), '1 note');
});

test('prompt has the apply header and one JSON line per item', () => {
  const lines = L.prompt('plans/2026-11-26.json', [
    { key: 'priorities|https://www.notion.so/a', label: 'Task A', done: true },
    { key: 'plan', label: 'Whole plan', note: 'a "quoted" note' },
  ]).split('\n');
  assert.equal(lines[0], '/daily-workflow:morning apply plans/2026-11-26.json');
  assert.deepEqual(JSON.parse(lines[1]), { key: 'priorities|https://www.notion.so/a', label: 'Task A', done: true });
  assert.deepEqual(JSON.parse(lines[2]), { key: 'plan', label: 'Whole plan', note: 'a "quoted" note' });
  assert.equal(lines.length, 3);
});

test('prune notes drops what the plan already stores and keeps unknown keys', () => {
  const notes = { 'code_review|https://github.com/org/shop/pull/412': 'ping Alice', 'resolved|gone': 'keep me',
    'priorities|https://www.notion.so/a': '   ', plan: 'stored' };
  assert.deepEqual(L.pruneNotes(items, notes, ['stored']), { 'resolved|gone': 'keep me' });
  assert.equal(L.pendingNote('code_review|https://github.com/org/shop/pull/412', ['ping Alice'], { 'code_review|https://github.com/org/shop/pull/412': 'ping Alice again' }), 'ping Alice again');
});

test('prune drops ticks the JSON already has and keeps unknown keys', () => {
  const ticks = { 'daily_update.today|Ship it': true, 'resolved|gone': true, 'x|off': false };
  assert.deepEqual(L.prune(items, ticks), { 'resolved|gone': true });
});

test('storage keys are per plan file', () => {
  assert.equal(L.storageKey('plans/2026-11-26.json'), 'daily-workflow:plan:plans/2026-11-26.json');
  assert.equal(L.notesKey('plans/2026-11-26.json'), 'daily-workflow:plan-notes:plans/2026-11-26.json');
});
