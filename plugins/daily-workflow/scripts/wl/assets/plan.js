/*
 * daily-workflow plan page: components.
 * Plan page format 4
 *
 * Copied into ~/.ai/worklog/plans/assets/ by `worklog render-plan` on every render. Do not edit the copy.
 * Light DOM custom elements (no shadow DOM), styled by plan.css. The renderer writes the content:
 *   <plan-page file>
 *     <header class="rail">eyebrow, headline, the three acts</header>
 *     <main>
 *       <plan-section name [class="deep"] [sortable]><h2>title</h2>
 *         <div class="items"><plan-item key label [url] [done]><div class="cbody">…</div>
 *           [<div class="reqs" data-key><div class="req" data-text>stored note for AI and its result</div></div>]
 *           [<div class="sub">…</div>]</plan-item></div>
 *       </plan-section>
 *       <plan-section name="ai_notes" class="general">the note for the whole plan and its stored notes</plan-section>
 *     </main>
 *   </plan-page>
 * The page is readable without JS. With JS every <plan-item> gets a checkbox and a "+ note" button (a note for AI:
 * free text about what to do with the item), every section a "2/3" counter, the last section a field for a note
 * about the whole plan, and the bottom bar copies the "apply" prompt. In a sortable section the items get a grip:
 * drag it (native drag and drop) or press the arrow keys on it to reorder the list. Ticks, notes and the order live
 * in localStorage until that prompt is pasted into the session; then the plan JSON marks the items done (the done
 * attribute), stores the notes (.req) and has the lists in the new order, so they leave localStorage on the next
 * load.
 * Load with <script defer src="..."> so all markup is parsed before upgrade.
 */
(function () {
  'use strict';

  // Key of the note for the whole plan; item keys always contain "|".
  const GENERAL = 'plan';

  const PlanLogic = {
    GENERAL,
    storageKey(file) {
      return 'daily-workflow:plan:' + file;
    },
    notesKey(file) {
      return 'daily-workflow:plan-notes:' + file;
    },
    orderKey(file) {
      return 'daily-workflow:plan-order:' + file;
    },
    // Ticks that are not in the JSON yet, in page order.
    pending(items, ticks) {
      return items.filter((i) => !i.done && ticks[i.key]);
    },
    // The note typed for a key, unless the plan already stores the same text for it.
    pendingNote(key, sent, notes) {
      const text = String(notes[key] || '').trim();
      return text && !(sent || []).includes(text) ? text : '';
    },
    // One line per item with a new tick or a new note, in page order, then the note for the whole plan, then one
    // line per list whose order differs from the plan.
    lines(items, ticks, notes, generalSent, orders) {
      const out = [];
      items.forEach((i) => {
        const done = !i.done && !!ticks[i.key];
        const note = PlanLogic.pendingNote(i.key, i.sent, notes);
        if (!done && !note) return;
        const line = { key: i.key, label: i.label };
        if (done) line.done = true;
        if (note) line.note = note;
        out.push(line);
      });
      const general = PlanLogic.pendingNote(GENERAL, generalSent, notes);
      if (general) out.push({ key: GENERAL, label: 'Whole plan', note: general });
      return out.concat(orders || []);
    },
    prompt(file, lines) {
      return ['/daily-workflow:morning apply ' + file].concat(lines.map((l) => JSON.stringify(l))).join('\n');
    },
    summary(lines) {
      const done = lines.filter((l) => l.done).length;
      const notes = lines.filter((l) => l.note).length;
      const lists = lines.filter((l) => l.order).length;
      return [done ? done + ' done' : '', notes ? notes + (notes === 1 ? ' note' : ' notes') : '',
        lists ? lists + (lists === 1 ? ' list reordered' : ' lists reordered') : '']
        .filter(Boolean).join(' · ');
    },
    // Keys the JSON already marks done do not need to stay in localStorage.
    prune(items, ticks) {
      const out = {};
      const done = new Set(items.filter((i) => i.done).map((i) => i.key));
      Object.keys(ticks).forEach((k) => { if (ticks[k] && !done.has(k)) out[k] = true; });
      return out;
    },
    // Notes the plan already stores do not need to stay in localStorage; notes of unknown keys are kept.
    pruneNotes(items, notes, generalSent) {
      const sent = new Map(items.map((i) => [i.key, i.sent || []]));
      sent.set(GENERAL, generalSent || []);
      const out = {};
      Object.keys(notes).forEach((k) => {
        const text = PlanLogic.pendingNote(k, sent.get(k), notes);
        if (text) out[k] = text;
      });
      return out;
    },
    // The order the user arranged, applied to the keys the plan renders: the arranged keys that still exist come
    // first, the rest (items added since) keep the plan's order after them.
    mergeOrder(rendered, arranged) {
      const present = new Set(rendered);
      const first = (arranged || []).filter((k, i, all) => present.has(k) && all.indexOf(k) === i);
      const used = new Set(first);
      return first.concat(rendered.filter((k) => !used.has(k)));
    },
    sameOrder(a, b) {
      return a.length === b.length && a.every((k, i) => k === b[i]);
    },
    // Lists whose arranged order differs from the plan, as prompt lines; lists: [{name, keys}] as rendered.
    pendingOrders(lists, orders) {
      const out = [];
      lists.forEach((l) => {
        const keys = PlanLogic.mergeOrder(l.keys, orders[l.name]);
        if (!PlanLogic.sameOrder(keys, l.keys)) out.push({ order: l.name, keys });
      });
      return out;
    },
    // An order the plan already has does not need to stay in localStorage; orders of unknown lists are dropped.
    pruneOrders(lists, orders) {
      const out = {};
      PlanLogic.pendingOrders(lists, orders).forEach((o) => { out[o.order] = o.keys; });
      return out;
    },
  };
  globalThis.PlanLogic = PlanLogic;
  if (typeof document === 'undefined') return;

  function load(key) {
    try { return JSON.parse(localStorage.getItem(key) || '{}') || {}; } catch (err) { return {}; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (err) { /* storage unavailable: lasts until reload */ }
  }
  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
    return Promise.resolve();
  }
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  };
  // Texts of the notes the plan already stores in one .reqs box.
  const sentTexts = (box) => (box ? [...box.querySelectorAll(':scope > .req')].map((r) => r.dataset.text || '') : []);
  const itemsOf = (box) => [...box.children].filter((c) => c.localName === 'plan-item');
  const keysOf = (box) => itemsOf(box).map((c) => c.getAttribute('key') || '');
  const noteInput = (placeholder) => {
    const input = el('textarea', 'nin');
    input.rows = 2;
    input.placeholder = placeholder;
    input.setAttribute('aria-label', 'Note for AI');
    return input;
  };

  // The handle of an item in a sortable list. A span, not a button: Firefox does not start a drag from a button.
  const grip = () => {
    const g = el('span', 'grip', '⋮⋮');
    g.draggable = true;
    g.tabIndex = 0;
    g.setAttribute('role', 'button');
    g.setAttribute('aria-label', 'Reorder: drag, or press the up and down arrow keys');
    g.title = 'Drag to reorder · ↑ ↓ on the keyboard';
    return g;
  };

  class PlanItem extends HTMLElement {
    connectedCallback() {
      if (this.box) return;
      this.box = el('input', 'cbx');
      this.box.type = 'checkbox';
      this.box.setAttribute('aria-label', 'Done');
      this.prepend(this.box);

      const reqs = this.querySelector(':scope > .reqs');
      this.sent = sentTexts(reqs);
      this.nbtn = el('button', 'nbtn', '+ note');
      this.nbtn.type = 'button';
      this.nbtn.title = 'Note for AI: what to do with this item';
      this.mine = el('div', 'mine');
      const body = this.querySelector(':scope > .cbody');
      (body || this.box).after(this.nbtn);
      (reqs || this.nbtn).after(this.mine);
    }
    get data() {
      return { key: this.getAttribute('key') || '', label: this.getAttribute('label') || '',
        done: this.hasAttribute('done'), sent: this.sent };
    }
    get noteInput() {
      return this.mine.querySelector('.nin');
    }
    show(on) {
      const done = this.hasAttribute('done');
      this.classList.toggle('ticked', done || on);
      this.box.checked = done || on;
      this.box.disabled = done;
      this.box.title = done ? 'Marked done in the plan' : '';
    }
    // The note typed on the page and not sent yet: click to edit.
    showNote(text) {
      this.classList.toggle('noted', !!text);
      this.nbtn.textContent = text ? 'edit note' : '+ note';
      if (!text) { this.mine.replaceChildren(); return; }
      const view = el('div', 'mytext');
      view.title = 'Click to edit';
      view.append(el('span', 'req-l', 'Note for AI'), ' ' + text + ' ', el('span', 'res new', 'not sent yet'));
      this.mine.replaceChildren(view);
    }
    editNote(text) {
      this.classList.add('noted');
      const input = noteInput('e.g. “set the reminder to 1 Dec” or “move to Waiting for”');
      input.value = text;
      this.mine.replaceChildren(input, el('div', 'nhint', 'Enter saves · Shift+Enter new line · Esc saves and closes · empty removes the note'));
      input.focus();
    }
  }

  class PlanSection extends HTMLElement {
    count() {
      const items = [...this.querySelectorAll('plan-item')];
      if (!items.length) return;
      if (!this.counter) {
        this.counter = el('span', 'cnt');
        const h2 = this.querySelector('h2');
        if (h2) h2.append(this.counter);
      }
      const ticked = items.filter((i) => i.classList.contains('ticked')).length;
      this.counter.textContent = ticked + '/' + items.length;
      this.counter.classList.toggle('all', ticked === items.length);
    }
  }

  class PlanPage extends HTMLElement {
    connectedCallback() {
      if (this.ready) return;
      this.ready = true;
      const file = this.getAttribute('file') || location.pathname;
      this.file = file;
      this.storage = PlanLogic.storageKey(file);
      this.notesStorage = PlanLogic.notesKey(file);
      this.nodes = [...this.querySelectorAll('plan-item')];
      this.sections = [...this.querySelectorAll('plan-section')];
      this.editing = null;

      const general = this.querySelector('plan-section[name="ai_notes"]');
      this.generalSent = sentTexts(general && general.querySelector(':scope > .reqs[data-key="' + GENERAL + '"]'));
      this.ticks = PlanLogic.prune(this.items(), load(this.storage));
      this.notes = PlanLogic.pruneNotes(this.items(), load(this.notesStorage), this.generalSent);
      save(this.storage, this.ticks);
      save(this.notesStorage, this.notes);

      // Sortable lists: the order arranged in the browser is applied on top of the plan's order.
      this.orderStorage = PlanLogic.orderKey(file);
      this.lists = [...this.querySelectorAll('plan-section[sortable]')]
        .map((s) => ({ name: s.getAttribute('name') || '', box: s.querySelector(':scope > .items') }))
        .filter((l) => l.box)
        .map((l) => Object.assign(l, { keys: keysOf(l.box) }));
      this.orders = PlanLogic.pruneOrders(this.lists, load(this.orderStorage));
      save(this.orderStorage, this.orders);
      this.drag = null;
      this.lists.forEach((l) => {
        this.arrange(l, PlanLogic.mergeOrder(l.keys, this.orders[l.name]));
        const items = itemsOf(l.box);
        if (items.length > 1) items.forEach((item) => item.prepend(grip()));
      });
      this.nodes = [...this.querySelectorAll('plan-item')];

      if (general) {
        this.ginput = noteInput('e.g. “move everything unfinished to tomorrow” or “add a card: call the accountant”');
        this.ginput.value = this.notes[GENERAL] || '';
        (general.querySelector(':scope > .hint') || general.querySelector('h2')).after(this.ginput);
        this.ginput.addEventListener('input', () => {
          this.setNote(GENERAL, this.ginput.value);
          this.updateBar();
        });
      }

      this.bar = el('div', 'bar');
      this.counter = el('span');
      const button = el('button', 'btn accent', 'Copy prompt');
      button.type = 'button';
      this.ok = el('span', 'ok');
      this.bar.append(this.counter, button, this.ok);
      document.body.append(this.bar);

      this.addEventListener('change', (ev) => {
        const item = ev.target.closest('plan-item');
        if (!item || ev.target !== item.box) return;
        const key = item.data.key;
        if (ev.target.checked) this.ticks[key] = true; else delete this.ticks[key];
        save(this.storage, this.ticks);
        this.update();
      });
      this.addEventListener('click', (ev) => {
        const hit = ev.target.closest('.nbtn, .mytext');
        const item = hit && hit.closest('plan-item');
        if (item) this.openNote(item);
      });
      this.addEventListener('keydown', (ev) => {
        if (ev.target.classList && ev.target.classList.contains('grip')) { this.moveByKey(ev); return; }
        if (!this.editing || ev.target !== this.editing.noteInput) return;
        if ((ev.key === 'Enter' && !ev.shiftKey) || ev.key === 'Escape') { ev.preventDefault(); this.closeNote(); }
      });
      this.addEventListener('dragstart', (ev) => {
        const item = ev.target.classList && ev.target.classList.contains('grip') && ev.target.closest('plan-item');
        const list = item && this.listOf(item);
        if (!list) return;
        this.drag = { item, list, before: keysOf(list.box), dropped: false };
        ev.dataTransfer.effectAllowed = 'move';
        ev.dataTransfer.setData('text/plain', item.getAttribute('label') || '');
        ev.dataTransfer.setDragImage(item, 12, 12);
        // After the browser took the drag image; not at all when the drag is already over.
        requestAnimationFrame(() => { if (this.drag && this.drag.item === item) item.classList.add('dragging'); });
      });
      // While dragging, the item follows the pointer inside its own list; releasing anywhere keeps the new place,
      // Esc puts the list back.
      document.addEventListener('dragover', (ev) => {
        const d = this.drag;
        if (!d) return;
        ev.preventDefault();
        ev.dataTransfer.dropEffect = 'move';
        const over = ev.target.closest && ev.target.closest('plan-item');
        if (!over || over === d.item || over.parentElement !== d.list.box) return;
        const box = over.getBoundingClientRect();
        over[ev.clientY > box.top + box.height / 2 ? 'after' : 'before'](d.item);
      });
      document.addEventListener('drop', (ev) => {
        if (!this.drag) return;
        ev.preventDefault();
        this.drag.dropped = true;
      });
      this.addEventListener('dragend', () => {
        const d = this.drag;
        if (!d) return;
        this.drag = null;
        d.item.classList.remove('dragging');
        if (!d.dropped) this.arrange(d.list, d.before);
        this.commit(d.list);
      });
      this.addEventListener('focusout', (ev) => {
        if (this.editing && ev.target === this.editing.noteInput) this.closeNote();
      });
      button.addEventListener('click', () => {
        this.closeNote();
        copy(PlanLogic.prompt(this.file, this.lines())).then(() => {
          this.ok.textContent = 'Copied, paste it into the session';
        });
      });
      this.update();
    }
    items() {
      return this.nodes.map((n) => n.data);
    }
    lines() {
      return PlanLogic.lines(this.items(), this.ticks, this.notes, this.generalSent,
        PlanLogic.pendingOrders(this.lists, this.orders));
    }
    listOf(item) {
      return this.lists.find((l) => l.box === item.parentElement);
    }
    // Puts the items of a list into the given key order.
    arrange(list, keys) {
      const byKey = new Map();
      itemsOf(list.box).forEach((item) => {
        const key = item.getAttribute('key') || '';
        byKey.set(key, (byKey.get(key) || []).concat(item));
      });
      keys.forEach((key) => { (byKey.get(key) || []).forEach((item) => list.box.append(item)); byKey.delete(key); });
    }
    // The list was rearranged: remember its order, unless it is the plan's order again.
    commit(list) {
      const keys = keysOf(list.box);
      if (PlanLogic.sameOrder(keys, list.keys)) delete this.orders[list.name]; else this.orders[list.name] = keys;
      save(this.orderStorage, this.orders);
      this.nodes = [...this.querySelectorAll('plan-item')];
      this.updateBar();
    }
    moveByKey(ev) {
      if (ev.key !== 'ArrowUp' && ev.key !== 'ArrowDown') return;
      ev.preventDefault();
      const item = ev.target.closest('plan-item');
      const list = item && this.listOf(item);
      const up = ev.key === 'ArrowUp';
      const other = item && (up ? item.previousElementSibling : item.nextElementSibling);
      if (!list || !other) return;
      other[up ? 'before' : 'after'](item);
      ev.target.focus();
      this.commit(list);
    }
    setNote(key, text) {
      if (String(text || '').trim()) this.notes[key] = String(text).trim(); else delete this.notes[key];
      save(this.notesStorage, this.notes);
    }
    openNote(item) {
      if (this.editing === item) return;
      this.closeNote();
      this.editing = item;
      item.editNote(this.notes[item.data.key] || '');
    }
    closeNote() {
      const item = this.editing;
      if (!item) return;
      this.editing = null;
      const input = item.noteInput;
      this.setNote(item.data.key, input ? input.value : '');
      this.update();
    }
    update() {
      this.nodes.forEach((n) => {
        n.show(!!this.ticks[n.data.key]);
        if (n !== this.editing) n.showNote(PlanLogic.pendingNote(n.data.key, n.sent, this.notes));
      });
      this.sections.forEach((s) => s.count());
      this.updateBar();
    }
    updateBar() {
      const lines = this.lines();
      this.counter.textContent = PlanLogic.summary(lines);
      this.bar.classList.toggle('on', lines.length > 0);
      this.ok.textContent = '';
    }
  }

  // Items and sections first, so the page finds them upgraded.
  customElements.define('plan-item', PlanItem);
  customElements.define('plan-section', PlanSection);
  customElements.define('plan-page', PlanPage);
})();
