/*
 * daily-workflow inbox page: pure logic, no DOM.
 * Inbox page format 1
 *
 * Copied into ~/.ai/worklog/inbox/assets/ by `worklog render-inbox` on every render.
 * Loaded as a classic script (ES modules do not load from file://) and exposed as globalThis.InboxLogic,
 * so tests/inbox_logic.test.js can load it with node:vm.
 */
(() => {
  'use strict';

  const OUTCOMES = {
    done: 'Done', next: 'Next Actions', today_candidates: 'Today candidates', today: 'Today', calendar: 'Calendar',
    waiting: 'Waiting for', agenda: 'Agenda', reading: 'Reading list', reference: 'Reference',
    someday: 'Someday/Maybe', icebox: 'Icebox', trash: 'Trash', keep: 'Keep',
  };
  const ESTIMATES = ['0.25 x 🍅', '0.5 x 🍅', '1 x 🍅', '2 x 🍅', '3 x 🍅', '4 x 🍅', '5 x 🍅', '6 x 🍅', '10 x 🍅', 'None'];
  const PRIORITIES = ['P1', 'P2', 'P3'];
  const CATEGORIES = { 'Work': ['Work'], 'Home': ['Home'], 'Work+Home': ['Work', 'Home'] };
  // Fields each status uses, in display order (status itself is always shown first).
  const FIELDS = {
    done: ['category', 'estimate', 'priority', 'reminder', 'due'],
    next: ['category', 'estimate', 'priority', 'reminder', 'due', 'project'],
    today_candidates: ['category', 'estimate', 'priority', 'reminder', 'due', 'project'],
    today: ['category', 'estimate', 'priority', 'reminder', 'due', 'project'],
    calendar: ['category', 'estimate', 'priority', 'reminder', 'due', 'project'],
    waiting: ['category', 'priority', 'reminder', 'due', 'project'],
    agenda: ['agenda'],
    reading: [], // the title names the material; apply appends it to the Reading list page
    reference: ['file'], // the knowledge base file the entry goes to
    someday: ['category', 'reminder', 'due', 'project'],
    icebox: ['category', 'reminder', 'due', 'project'],
    trash: [],
    keep: [],
  };
  const CARD_KEYS = ['outcome', 'title', 'category', 'estimate', 'priority', 'reminder', 'due', 'project', 'agenda', 'file'];
  const WAITING_FOLLOW_UP_DAYS = 3;

  const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const ISO = /^\d{4}-\d{2}-\d{2}$/;

  function addDays(iso, n) {
    const [y, m, d] = iso.split('-').map(Number);
    const t = new Date(Date.UTC(y, m - 1, d + n));
    return t.toISOString().slice(0, 10);
  }

  function formatDate(iso, today) {
    if (!iso || !ISO.test(iso)) return iso || '';
    const [y, m, d] = iso.split('-').map(Number);
    const day = new Date(Date.UTC(y, m - 1, d));
    const rel = iso === today ? 'today' : iso === addDays(today, 1) ? 'tomorrow' : DOW[day.getUTCDay()];
    return `${rel} ${MON[m - 1]} ${d}`;
  }

  function categoryLabel(category) {
    const set = new Set(category || []);
    if (set.has('Work') && set.has('Home')) return 'Work+Home';
    return set.has('Home') ? 'Home' : 'Work';
  }

  function normalizeCard(raw) {
    const c = Object.assign({ outcome: 'keep', title: '', category: ['Work'], estimate: '', priority: '',
      reminder: '', due: '', project: '', agenda: '', file: '' }, raw || {});
    if (!OUTCOMES[c.outcome]) c.outcome = 'keep';
    if (typeof c.category === 'string') c.category = CATEGORIES[c.category] || ['Work'];
    const out = {};
    for (const k of CARD_KEYS) out[k] = k === 'category' ? [...c.category] : String(c[k] ?? '');
    return out;
  }

  // Returns a new card with one field changed. Switching to a status without a reminder sets one: Waiting for the
  // follow-up day, Today and Today candidates today. Dates other than YYYY-MM-DD are dropped.
  function setField(card, field, value, today) {
    const c = normalizeCard(card);
    if (field === 'category') c.category = [...(CATEGORIES[value] || ['Work'])];
    else if (field === 'reminder' || field === 'due') c[field] = ISO.test(String(value ?? '')) ? String(value) : '';
    else c[field] = String(value ?? '');
    if (field === 'outcome' && !c.reminder) {
      if (value === 'waiting') c.reminder = addDays(today, WAITING_FOLLOW_UP_DAYS);
      if (value === 'today' || value === 'today_candidates') c.reminder = today;
    }
    return c;
  }

  const sameCard = (a, b) => JSON.stringify(normalizeCard(a)) === JSON.stringify(normalizeCard(b));
  const fieldChanged = (base, card, field) => !!base && JSON.stringify(base[field]) !== JSON.stringify(card[field]);

  function entryChanged(baseCards, cards, note) {
    if (note) return true;
    if (baseCards.length !== cards.length) return true;
    return cards.some((c, j) => !sameCard(baseCards[j], c));
  }

  // Apply skips these: Agenda without a person, Reference without a knowledge base file.
  const incomplete = (card) => (card.outcome === 'agenda' && !card.agenda) || (card.outcome === 'reference' && !card.file);

  // The part of a card that goes into the apply line: the outcome, the title (not for Trash/Keep)
  // and only the fields the outcome uses. Keep is just {"outcome":"keep"}.
  function pick(card) {
    const c = normalizeCard(card);
    const out = { outcome: c.outcome };
    if (c.outcome === 'keep') return out;
    if (c.outcome !== 'trash') out.title = c.title;
    for (const f of FIELDS[c.outcome]) out[f] = f === 'category' ? [...c.category] : c[f];
    return out;
  }

  // One line per entry with at least one non-Keep card, null otherwise.
  // A split entry keeps every card in its position: card 1 is always the original page.
  function applyLine(id, cards, note) {
    if (!cards.length || cards.every((c) => c.outcome === 'keep')) return null;
    if (cards.length === 1) return JSON.stringify(Object.assign({ id }, pick(cards[0]), { note: note || '' }));
    return JSON.stringify({ id, cards: cards.map(pick), note: note || '' });
  }

  function prompt(file, entries) {
    const lines = [`/daily-workflow:inbox apply ${file}`];
    for (const e of entries) {
      const line = applyLine(e.id, e.cards, e.note);
      if (line) lines.push(line);
    }
    return lines.join('\n');
  }

  function summary(card, today) {
    const c = normalizeCard(card);
    if (c.outcome === 'keep') return 'Keep, stays in the Inbox';
    const f = FIELDS[c.outcome];
    const parts = [OUTCOMES[c.outcome]];
    if (f.includes('category')) parts.push(categoryLabel(c.category));
    if (f.includes('estimate') && c.estimate) parts.push(c.estimate);
    if (f.includes('priority') && c.priority) parts.push(c.priority);
    if (f.includes('reminder') && c.reminder) parts.push(formatDate(c.reminder, today));
    if (f.includes('due') && c.due) parts.push('due ' + formatDate(c.due, today));
    if (c.outcome === 'agenda') parts.push(c.agenda ? '→ ' + c.agenda : 'choose person');
    if (c.outcome === 'reference') parts.push(c.file ? '→ ' + c.file : 'choose file');
    if (f.includes('project') && c.project) parts.push(c.project);
    return parts.join(' · ');
  }

  globalThis.InboxLogic = {
    OUTCOMES, ESTIMATES, PRIORITIES, CATEGORIES, FIELDS,
    addDays, formatDate, categoryLabel, normalizeCard, setField,
    sameCard, fieldChanged, entryChanged, incomplete, pick, applyLine, prompt, summary,
  };
})();
