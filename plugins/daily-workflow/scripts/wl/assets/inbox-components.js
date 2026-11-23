/*
 * daily-workflow inbox page: components.
 * Inbox page format 1
 *
 * Copied into ~/.ai/worklog/inbox/assets/ by `worklog render-inbox` on every render. Do not edit the copy.
 * Light DOM custom elements (no shadow DOM), styled by inbox.css. Needs inbox-logic.js loaded first.
 *
 * Content (written by the renderer, plain text and attributes only):
 *   <inbox-app file date generated-at [captured] [skipped]>
 *     <inbox-agenda name>                         an Agenda card the user can pick
 *     <inbox-missing source>reason</inbox-missing>  a source that failed during capture
 *     <inbox-entry entry-id age [page-url] [waiting] [result]>
 *       <inbox-original [href] [label]>original title</inbox-original>
 *       <inbox-card outcome category estimate priority reminder due project agenda>proposed title</inbox-card>
 *       <inbox-why>AI reason</inbox-why>
 *     </inbox-entry>
 *   </inbox-app>
 *
 * <inbox-app> reads the content once, hides it and renders one entry at a time, the summary and the
 * apply prompt. Every value is inserted as text, links only for http(s).
 * Load with <script defer src="..."> so all markup is parsed before upgrade.
 */
(() => {
  'use strict';
  const L = globalThis.InboxLogic;

  const h = (tag, attrs = {}, ...children) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const c of children.flat()) if (c != null && c !== false) el.append(c);
    return el;
  };
  const safeUrl = (u) => (typeof u === 'string' && /^https?:\/\//.test(u) ? u : null);
  const kbd = (k) => h('kbd', {}, k);

  // ---------------------------------------------------------------- content elements

  class InboxCard extends HTMLElement {
    get data() {
      const a = (n) => this.getAttribute(n) || '';
      return L.normalizeCard({
        outcome: a('outcome'), title: this.textContent.trim(), category: a('category') || 'Work',
        estimate: a('estimate'), priority: a('priority'), reminder: a('reminder'), due: a('due'),
        project: a('project'), agenda: a('agenda'),
      });
    }
  }

  class InboxEntry extends HTMLElement {
    get data() {
      const orig = this.querySelector('inbox-original');
      return {
        id: this.getAttribute('entry-id') || '',
        age: this.getAttribute('age') || '',
        pageUrl: safeUrl(this.getAttribute('page-url')),
        waiting: this.hasAttribute('waiting'),
        result: this.getAttribute('result') || '',
        title: orig ? orig.textContent.trim() : '',
        source: orig && orig.getAttribute('label')
          ? { label: orig.getAttribute('label'), url: safeUrl(orig.getAttribute('href')) } : null,
        why: (this.querySelector('inbox-why') || {}).textContent?.trim() || '',
        cards: [...this.querySelectorAll('inbox-card')].map((c) => c.data),
      };
    }
  }

  // ---------------------------------------------------------------- app

  class InboxApp extends HTMLElement {
    connectedCallback() {
      if (this._ready) return;
      this._ready = true;
      this.file = this.getAttribute('file') || '';
      this.today = this.getAttribute('date') || new Date().toISOString().slice(0, 10);
      this.entries = [...this.querySelectorAll('inbox-entry')].map((e) => e.data).filter((e) => e.id && e.cards.length);
      this.people = [...this.querySelectorAll('inbox-agenda')].map((a) => a.getAttribute('name')).filter(Boolean);
      this.missing = [...this.querySelectorAll('inbox-missing')]
        .map((m) => `${m.getAttribute('source') || ''} (${m.textContent.trim()})`);
      this.key = `daily-workflow:inbox:${this.file}`;
      this.editing = null; // null | {what: 'title', card: j} | {what: 'note'}
      this.shown = null;
      this.load();
      for (const child of [...this.children]) child.hidden = true;
      this.build();
      this.render();
    }

    // ------------------------------------------------ state

    fresh() {
      return { sig: this.sig(), cur: 0, cards: this.entries.map((e) => e.cards.map(L.normalizeCard)),
        note: this.entries.map(() => ''), last: null };
    }
    sig() { return this.entries.map((e) => e.id).join(','); }
    load() {
      let s = null;
      try { s = JSON.parse(localStorage.getItem(this.key)); } catch { s = null; }
      this.S = s && s.sig === this.sig() ? s : this.fresh();
    }
    save() { try { localStorage.setItem(this.key, JSON.stringify(this.S)); } catch { /* storage unavailable */ } }
    get count() { return this.entries.length; }
    get atSummary() { return this.S.cur >= this.count; }

    setField(j, field, value) {
      const i = this.S.cur;
      this.S.cards[i][j] = L.setField(this.S.cards[i][j], field, value, this.today);
      this.save();
    }
    setStatus(outcome) {
      if (this.atSummary) return;
      const i = this.S.cur;
      this.S.cards[i] = this.S.cards[i].map((c) => L.setField(c, 'outcome', outcome, this.today));
      this.S.last = i;
      this.editing = null;
      this.save();
      this.render();
      this.toast(`Status: ${L.OUTCOMES[outcome]}`, true);
    }
    addCard() {
      if (this.atSummary) return;
      const i = this.S.cur;
      const first = this.S.cards[i][0];
      // Type and reminder from the first card, the rest as a plain next action.
      this.S.cards[i].push(L.normalizeCard({ outcome: 'next', category: first.category, reminder: first.reminder,
        estimate: '0.5 x 🍅', priority: 'P2' }));
      this.editing = { what: 'title', card: this.S.cards[i].length - 1 };
      this.save();
      this.render();
    }
    removeCard(j) {
      const i = this.S.cur;
      if (this.S.cards[i].length < 2) return;
      this.S.cards[i].splice(j, 1);
      this.editing = null;
      this.save();
      this.render();
      this.toast('Card removed');
    }
    resetEntry(i) {
      this.S.cards[i] = this.entries[i].cards.map(L.normalizeCard);
      this.S.note[i] = '';
      this.S.cur = i;
      this.editing = null;
      this.save();
      this.render();
      this.toast('Reset to the AI proposal');
    }
    changed(i) { return L.entryChanged(this.entries[i].cards, this.S.cards[i], this.S.note[i]); }
    reset() {
      if (this.atSummary) return;
      if (this.changed(this.S.cur)) this.resetEntry(this.S.cur);
      else this.toast('Already matches the AI proposal');
    }
    undoLast() { if (this.S.last !== null && this.changed(this.S.last)) this.resetEntry(this.S.last); }
    go(i) {
      this.editing = null;
      this.S.cur = Math.max(0, Math.min(this.count, i));
      this.save();
      this.render();
    }
    finishTitle(keep) {
      const ed = this.editing;
      if (!ed || ed.what !== 'title') return;
      const input = this.querySelector('.tinput');
      const value = input ? input.value.trim() : '';
      this.editing = null;
      const i = this.S.cur;
      const card = this.S.cards[i][ed.card];
      if (keep && value) card.title = value;
      if (!card.title && this.S.cards[i].length > 1) this.S.cards[i].splice(ed.card, 1); // an added card without a title is dropped
      this.save();
      this.render();
    }
    finishNote() {
      if (!this.editing || this.editing.what !== 'note') return;
      const input = this.querySelector('.note-in');
      this.S.note[this.S.cur] = input ? input.value.trim() : '';
      this.editing = null;
      this.save();
      this.render();
    }
    promptText() {
      return L.prompt(this.file, this.entries.map((e, i) => ({ id: e.id, cards: this.S.cards[i], note: this.S.note[i] })));
    }

    // ------------------------------------------------ static parts

    build() {
      this.main = h('main');
      this.toastMsg = h('span');
      this.toastUndo = h('a', { onclick: () => this.undoLast() }, 'Undo');
      this.toastEl = h('div', { class: 'toast' }, this.toastMsg, this.toastUndo);
      const row = (keys, text) => h('tr', {}, h('td', {}, ...keys), h('td', {}, text));
      this.helpEl = h('div', { class: 'overlay', onclick: (e) => { if (e.target === this.helpEl) this.help(false); } },
        h('div', { class: 'box' }, h('div', { class: 'title' }, 'Shortcuts'), h('table', {},
          row([kbd('j'), ' / ', kbd('→')], 'next entry; the entry is accepted as shown'),
          row([kbd('k'), ' / ', kbd('←')], 'previous entry'),
          row([kbd('e')], 'set status Done for every card of the entry'),
          row([kbd('#')], 'set status Trash for every card of the entry'),
          row([kbd('+')], 'add a card to the entry; × removes a card'),
          row([kbd('n')], 'note for AI, shared by every card of the entry'),
          row(['click the title'], 'rename; Enter saves, Esc cancels'),
          row(['click a field'], 'change it; the project only through the note for AI'),
          row([kbd('z')], 'reset the entry to the AI proposal'),
          row([kbd('?'), ' / ', kbd('Esc')], 'this help'))));
      const btn = (keys, label, fn) => h('button', { type: 'button', onclick: fn }, ...keys.flatMap((k) => [kbd(k), ' ']), label);
      const bar = h('div', { class: 'bar' },
        btn(['e'], 'Done', () => this.setStatus('done')),
        btn(['#'], 'Trash', () => this.setStatus('trash')),
        btn(['j', '→'], 'Next', () => this.go(this.S.cur + 1)),
        btn(['k', '←'], 'Previous', () => this.go(this.S.cur - 1)),
        btn(['+'], 'Add card', () => this.addCard()),
        btn(['n'], 'Note', () => this.openNote()),
        btn(['z'], 'Reset', () => this.reset()),
        btn(['?'], '', () => this.help()));
      const header = h('header', {},
        h('span', { class: 'eyebrow' }, 'Inbox'),
        h('h1', {}, this.today),
        h('span', { class: 'muted' }, this.headerNote()),
        h('div', { class: 'tools' }, h('button', { class: 'btn', type: 'button', onclick: () => this.resetAll() }, 'Reset all')));
      this.append(header, this.main, bar, this.toastEl, this.helpEl);
      document.addEventListener('keydown', (e) => this.onKey(e));
      this.addEventListener('focusout', (e) => {
        if (this.editing?.what === 'note' && e.target.classList.contains('note-in')) this.finishNote();
        else if (this.editing?.what === 'title' && e.target.classList.contains('tinput')) this.finishTitle(true);
      });
    }
    headerNote() {
      const parts = [];
      const cap = this.getAttribute('captured');
      if (cap !== null) parts.push(`${cap} captured, ${this.getAttribute('skipped') || 0} duplicates skipped`);
      parts.push(`${this.count} entries`);
      return parts.join(' · ');
    }
    resetAll() {
      if (!confirm('Reset all entries to the AI proposal?')) return;
      this.S = this.fresh();
      this.editing = null;
      this.save();
      this.render();
    }
    openNote() {
      if (this.atSummary) return;
      this.editing = { what: 'note' };
      this.render();
    }

    // ------------------------------------------------ rendering

    render() {
      const fly = this.shown !== this.S.cur;
      this.shown = this.S.cur;
      if (!this.count) {
        this.main.replaceChildren(h('div', { class: 'card' }, h('div', { class: 'title' }, 'Inbox zero'),
          h('p', { class: 'why' }, 'No entries to process.')));
        return;
      }
      const body = this.atSummary ? this.renderSummary() : this.renderEntry();
      if (fly) body.classList.add('fly');
      this.main.replaceChildren(this.renderProgress(), body);
      const input = this.querySelector('.tinput, .note-in');
      if (input) {
        input.focus();
        if (input.classList.contains('tinput')) input.select();
        else input.setSelectionRange(input.value.length, input.value.length);
      }
    }

    renderProgress() {
      const seg = (i, title, extra = {}) => h('span', Object.assign({
        title, onclick: () => this.go(i),
        class: i === this.S.cur ? 'cur' : i < this.S.cur ? 'ok' : '',
      }, extra));
      return h('div', { class: 'progress' },
        this.entries.map((e, i) => seg(i, e.title)),
        seg(this.count, 'Summary', { class: `last ${this.atSummary ? 'cur' : ''}` }));
    }

    select(j, field, current, options) {
      const card = this.S.cards[this.S.cur][j];
      const base = this.entries[this.S.cur].cards[j];
      const mod = L.fieldChanged(base, card, field) ? ' mod' : '';
      return h('select', {
        class: `chip${mod}`, title: 'Click to change',
        onchange: (e) => { this.setField(j, field, e.target.value); this.render(); },
      }, options.map(([v, label]) => h('option', { value: v, selected: v === current }, label)));
    }

    renderFields(j) {
      const c = this.S.cards[this.S.cur][j];
      const f = L.FIELDS[c.outcome];
      const out = [this.select(j, 'outcome', c.outcome, Object.entries(L.OUTCOMES))];
      if (f.includes('category')) out.push(this.select(j, 'category', L.categoryLabel(c.category), Object.keys(L.CATEGORIES).map((k) => [k, k])));
      if (f.includes('estimate')) out.push(this.select(j, 'estimate', c.estimate, [['', 'no estimate'], ...L.ESTIMATES.map((v) => [v, v])]));
      if (f.includes('priority')) out.push(this.select(j, 'priority', c.priority, [['', 'no priority'], ...L.PRIORITIES.map((v) => [v, v])]));
      if (f.includes('reminder')) out.push(this.select(j, 'reminder', c.reminder, L.dateOptions(c.reminder, 'reminder', this.today)));
      if (f.includes('due')) out.push(this.select(j, 'due', c.due, L.dateOptions(c.due, 'due', this.today)));
      if (f.includes('agenda')) {
        const people = c.agenda && !this.people.includes(c.agenda) ? [...this.people, c.agenda] : this.people;
        out.push(this.select(j, 'agenda', c.agenda, [['', 'choose person'], ...people.map((p) => [p, '→ ' + p])]));
      }
      if (f.includes('project') && c.project) {
        out.push(h('span', { class: 'chip static', title: 'Change the project with a note for AI' }, c.project));
      }
      return h('div', { class: 'chips' }, out);
    }

    renderCard(j, n) {
      const i = this.S.cur;
      const c = this.S.cards[i][j];
      const base = this.entries[i].cards[j];
      const tag = !base ? h('span', { class: 'tag' }, 'added by you')
        : c.title !== base.title ? h('span', { class: 'tag' }, 'edited by you') : null;
      const editing = this.editing?.what === 'title' && this.editing.card === j;
      const title = editing
        ? h('input', { class: 'tinput', value: c.title, placeholder: 'Title of the new card' })
        : h('div', { class: 'ptitle', title: 'Click to rename', onclick: () => { this.editing = { what: 'title', card: j }; this.render(); } },
          c.title || '(untitled)', tag);
      return h('div', { class: n > 1 ? 'sub multi' : 'sub' },
        n > 1 ? h('div', { class: 'subhead' }, h('span', { class: 'num' }, `Card ${j + 1}`),
          h('button', { class: 'rm', type: 'button', title: 'Remove this card', onclick: () => this.removeCard(j) }, '×')) : null,
        title,
        this.renderFields(j));
    }

    renderNote(n) {
      const note = this.S.note[this.S.cur];
      if (this.editing?.what === 'note') {
        return [h('textarea', { class: 'note-in', rows: '2',
          placeholder: 'Applies to every card of this entry, e.g. “project Hiring” or “this is about PROJ-1234”' }, note),
        h('div', { class: 'note-hint' }, 'Enter saves · Shift+Enter new line · Esc saves and closes')];
      }
      if (note) {
        return h('div', { class: 'note', title: 'n · click to edit', onclick: () => this.openNote() },
          `Note for AI${n > 1 ? ' (all cards)' : ''}: ${note}`);
      }
      return h('button', { class: 'note-add', type: 'button', onclick: () => this.openNote() },
        n > 1 ? '+ note for AI (all cards above)' : '+ note for AI');
    }

    renderEntry() {
      const i = this.S.cur;
      const e = this.entries[i];
      const cards = this.S.cards[i];
      const n = cards.length;
      const split = e.cards.length > 1;
      const origTitle = e.pageUrl ? h('a', { href: e.pageUrl, target: '_blank', rel: 'noopener' }, e.title) : e.title;
      const source = e.source
        ? (e.source.url ? h('a', { href: e.source.url, target: '_blank', rel: 'noopener' }, `${e.source.label} ↗`) : e.source.label)
        : 'added by hand';
      return h('div', { class: 'card' },
        h('div', { class: 'meta' },
          h('span', {}, `Entry ${i + 1} of ${this.count}`),
          h('span', {}, [e.waiting ? 'someone is waiting' : null, e.age ? `waiting ${e.age}` : null, e.result || null]
            .filter(Boolean).join(' · '))),
        h('div', { class: 'lbl' }, split ? `AI proposal · split into ${e.cards.length} cards` : 'AI proposal'),
        h('div', { class: 'orig' }, 'Original: ', origTitle, ' · ', source),
        cards.map((c, j) => this.renderCard(j, n)),
        h('button', { class: 'add', type: 'button', title: '+ · add another card from this entry', onclick: () => this.addCard() }, '+ Add card'),
        e.why ? h('div', { class: 'why' }, e.why) : null,
        this.renderNote(n));
    }

    renderSummary() {
      const rows = this.entries.map((e, i) => h('tr', { class: 'go', onclick: () => this.go(i) },
        h('td', {}, String(i + 1)),
        h('td', {}, e.title),
        h('td', {},
          this.S.cards[i].map((c) => h('div', { class: L.incomplete(c) ? 'srow warn' : 'srow' },
            L.summary(c, this.today),
            c.outcome !== 'trash' && c.outcome !== 'keep' ? [h('br'), h('span', { class: 'why' }, `→ ${c.title}`)] : null)),
          this.S.note[i] ? h('div', { class: 'why' }, `Note: ${this.S.note[i]}`) : null)));
      const text = this.promptText();
      const incomplete = this.S.cards.flat().filter(L.incomplete).length;
      return h('div', { class: 'card' },
        h('div', { class: 'title' }, 'Summary'),
        h('table', {}, h('tr', {}, h('th', {}, '#'), h('th', {}, 'Inbox entry'), h('th', {}, 'Cards')), rows),
        incomplete ? h('p', { class: 'warn' }, `${incomplete} Agenda card(s) without a person: apply skips them.`) : null,
        this.missing.length ? h('p', { class: 'why' }, `Missing sources: ${this.missing.join('; ')}`) : null,
        h('p', { class: 'why' }, 'Click a row or press ', kbd('k'), ' / ', kbd('←'), ' to go back. Entries you did not open are included with the AI proposal.'),
        h('div', { class: 'lbl' }, 'Prompt to paste into the session'),
        h('pre', { class: 'prompt' }, text),
        h('button', { class: 'btn accent', type: 'button', onclick: () => this.copy(text) }, 'Copy prompt'));
    }

    copy(text) {
      const done = () => this.toast('Copied');
      if (navigator.clipboard?.writeText) navigator.clipboard.writeText(text).then(done, () => this.copyFallback(text, done));
      else this.copyFallback(text, done);
    }
    copyFallback(text, done) {
      const ta = h('textarea', {}, text);
      document.body.append(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
      done();
    }

    toast(message, undo = false) {
      this.toastMsg.textContent = message;
      this.toastUndo.hidden = !undo;
      this.toastEl.classList.add('on');
      clearTimeout(this._toast);
      this._toast = setTimeout(() => this.toastEl.classList.remove('on'), 4000);
    }
    help(on) { this.helpEl.classList.toggle('on', on === undefined ? !this.helpEl.classList.contains('on') : on); }

    // ------------------------------------------------ keyboard

    onKey(e) {
      if (this.editing?.what === 'title') {
        if (e.key === 'Enter') { e.preventDefault(); this.finishTitle(true); }
        else if (e.key === 'Escape') { e.preventDefault(); this.finishTitle(false); }
        return;
      }
      if (this.editing?.what === 'note') {
        if ((e.key === 'Enter' && !e.shiftKey) || e.key === 'Escape') { e.preventDefault(); this.finishNote(); }
        return;
      }
      const tag = e.target?.tagName;
      if (tag === 'SELECT') { if (e.key === 'Escape') e.target.blur(); return; }
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (this.helpEl.classList.contains('on')) {
        if (e.key === 'Escape' || e.key === '?') { e.preventDefault(); this.help(false); }
        return;
      }
      const actions = {
        e: () => this.setStatus('done'), '#': () => this.setStatus('trash'), '+': () => this.addCard(),
        j: () => this.go(this.S.cur + 1), ArrowRight: () => this.go(this.S.cur + 1),
        k: () => this.go(this.S.cur - 1), ArrowLeft: () => this.go(this.S.cur - 1),
        z: () => this.reset(), n: () => this.openNote(), '?': () => this.help(), Escape: () => this.help(true),
      };
      if (actions[e.key]) { e.preventDefault(); actions[e.key](); }
    }
  }

  customElements.define('inbox-card', InboxCard);
  customElements.define('inbox-entry', InboxEntry);
  customElements.define('inbox-app', InboxApp);
})();
