// node --test plugins/daily-workflow/tests/inbox_logic.test.js
// Loads the page logic the same way the browser does (a classic script on globalThis).
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'scripts', 'wl', 'assets', 'inbox-logic.js'), 'utf8');
vm.runInThisContext(source, { filename: 'inbox-logic.js' });
const L = globalThis.InboxLogic;
const TODAY = '2026-11-23';
const card = (o) => L.normalizeCard(Object.assign({ outcome: 'next', title: 'Reply to Alice', category: ['Work'],
  estimate: '1 x 🍅', priority: 'P1', reminder: TODAY, due: '', project: 'Hiring', agenda: '', file: '' }, o));
const parse = (line) => JSON.parse(line);

test('single card line has only the fields its status uses', () => {
  const line = parse(L.applyLine('p1', [card()], ''));
  assert.deepEqual(line, { id: 'p1', outcome: 'next', title: 'Reply to Alice', category: ['Work'], estimate: '1 x 🍅',
    priority: 'P1', reminder: TODAY, due: '', project: 'Hiring', note: '' });
  const waiting = parse(L.applyLine('p1', [card({ outcome: 'waiting' })], 'ask Bob'));
  assert.equal('estimate' in waiting, false);
  assert.equal(waiting.note, 'ask Bob');
  assert.deepEqual(parse(L.applyLine('p1', [card({ outcome: 'trash' })], '')), { id: 'p1', outcome: 'trash', note: '' });
  const someday = parse(L.applyLine('p1', [card({ outcome: 'someday' })], ''));
  assert.deepEqual(Object.keys(someday), ['id', 'outcome', 'title', 'category', 'reminder', 'due', 'project', 'note']);
});

test('an entry with only Keep cards has no line', () => {
  assert.equal(L.applyLine('p1', [card({ outcome: 'keep' })], 'note'), null);
  assert.equal(L.applyLine('p1', [card({ outcome: 'keep' }), card({ outcome: 'keep' })], ''), null);
});

test('split entry keeps card positions, Keep on card 1 stays as a placeholder', () => {
  const line = parse(L.applyLine('p1', [card({ outcome: 'keep' }), card({ title: 'Second', outcome: 'done' })], 'shared'));
  assert.equal(line.id, 'p1');
  assert.equal(line.note, 'shared');
  assert.deepEqual(line.cards[0], { outcome: 'keep' });
  assert.equal(line.cards[1].title, 'Second');
  assert.equal(line.cards[1].outcome, 'done');
});

test('agenda without a person stays empty and is incomplete', () => {
  const c = card({ outcome: 'agenda' });
  assert.equal(L.incomplete(c), true);
  assert.deepEqual(parse(L.applyLine('p1', [c], '')), { id: 'p1', outcome: 'agenda', title: 'Reply to Alice', agenda: '', note: '' });
  assert.equal(L.incomplete(card({ outcome: 'agenda', agenda: 'Alice' })), false);
  assert.equal(L.summary(c, TODAY), 'Agenda · choose person');
});

test('Reading list carries only the title, Reference the knowledge base file', () => {
  assert.deepEqual(parse(L.applyLine('p1', [card({ outcome: 'reading', title: 'Retry patterns' })], '')),
    { id: 'p1', outcome: 'reading', title: 'Retry patterns', note: '' });
  const ref = card({ outcome: 'reference', title: 'Deploy freeze', file: 'event-pipeline.md' });
  assert.deepEqual(parse(L.applyLine('p1', [ref], 'add the date')),
    { id: 'p1', outcome: 'reference', title: 'Deploy freeze', file: 'event-pipeline.md', note: 'add the date' });
  assert.equal(L.summary(ref, TODAY), 'Reference · → event-pipeline.md');
  assert.equal(L.summary(card({ outcome: 'reading' }), TODAY), 'Reading list');
  assert.equal(L.OUTCOMES.reading, 'Reading list');
});

test('reference without a file is incomplete', () => {
  const c = card({ outcome: 'reference' });
  assert.equal(L.incomplete(c), true);
  assert.equal(L.summary(c, TODAY), 'Reference · choose file');
  assert.equal(L.incomplete(L.setField(c, 'file', 'notes.md', TODAY)), false);
  assert.equal(L.incomplete(card({ outcome: 'reading' })), false);
  assert.equal(L.normalizeCard({ outcome: 'reference' }).file, '');
});

test('switching to Waiting for sets a reminder only when there is none', () => {
  assert.equal(L.setField(card({ reminder: '' }), 'outcome', 'waiting', TODAY).reminder, '2026-11-26');
  assert.equal(L.setField(card({ reminder: '2026-11-24' }), 'outcome', 'waiting', TODAY).reminder, '2026-11-24');
  assert.equal(L.setField(card({ reminder: '' }), 'outcome', 'next', TODAY).reminder, '');
});

test('category labels map to Notion values', () => {
  assert.deepEqual(L.setField(card(), 'category', 'Work+Home', TODAY).category, ['Work', 'Home']);
  assert.equal(L.categoryLabel(['Home', 'Work']), 'Work+Home');
  assert.equal(L.categoryLabel(['Home']), 'Home');
});

test('dates from the calendar: past dates kept, anything but YYYY-MM-DD dropped', () => {
  assert.equal(L.setField(card(), 'reminder', '2026-01-05', TODAY).reminder, '2026-01-05');
  assert.equal(L.setField(card({ due: '2026-12-01' }), 'due', '', TODAY).due, '');
  assert.equal(L.setField(card(), 'due', '5.12.2026', TODAY).due, '');
  assert.equal(L.formatDate('2026-11-24', TODAY), 'tomorrow Nov 24');
  assert.equal(L.addDays('2026-12-30', 3), '2027-01-02');
});

test('Calendar, Today and Today candidates use the Next Actions fields', () => {
  for (const outcome of ['calendar', 'today', 'today_candidates']) {
    assert.deepEqual(L.FIELDS[outcome], L.FIELDS.next);
    assert.deepEqual(Object.keys(parse(L.applyLine('p1', [card({ outcome })], ''))),
      ['id', 'outcome', 'title', 'category', 'estimate', 'priority', 'reminder', 'due', 'project', 'note']);
  }
  assert.equal(L.OUTCOMES.today_candidates, 'Today candidates');
});

test('Today and Today candidates without a reminder get today, Calendar does not', () => {
  assert.equal(L.setField(card({ reminder: '' }), 'outcome', 'today', TODAY).reminder, TODAY);
  assert.equal(L.setField(card({ reminder: '' }), 'outcome', 'today_candidates', TODAY).reminder, TODAY);
  assert.equal(L.setField(card({ reminder: '2026-11-30' }), 'outcome', 'today', TODAY).reminder, '2026-11-30');
  assert.equal(L.setField(card({ reminder: '' }), 'outcome', 'calendar', TODAY).reminder, '');
});

test('prompt has the apply header and one line per non-Keep entry', () => {
  const text = L.prompt('inbox/2026-11-23-0931.json', [
    { id: 'p1', cards: [card()], note: '' },
    { id: 'p2', cards: [card({ outcome: 'keep' })], note: '' },
    { id: 'p3', cards: [card({ outcome: 'trash' })], note: '' },
  ]);
  const lines = text.split('\n');
  assert.equal(lines[0], '/daily-workflow:inbox apply inbox/2026-11-23-0931.json');
  assert.deepEqual(lines.slice(1).map((l) => parse(l).id), ['p1', 'p3']);
});

test('entryChanged notices edits, added cards and notes', () => {
  const base = [card()];
  assert.equal(L.entryChanged(base, [card()], ''), false);
  assert.equal(L.entryChanged(base, [card({ title: 'Other' })], ''), true);
  assert.equal(L.entryChanged(base, [card(), card()], ''), true);
  assert.equal(L.entryChanged(base, [card()], 'note'), true);
  assert.equal(L.fieldChanged(base[0], card({ priority: 'P3' }), 'priority'), true);
  assert.equal(L.fieldChanged(undefined, card(), 'priority'), false);
});

test('unknown outcome falls back to Keep', () => {
  assert.equal(L.normalizeCard({ outcome: 'bogus' }).outcome, 'keep');
});
