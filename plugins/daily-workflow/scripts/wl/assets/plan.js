/*
 * daily-workflow plan page: components.
 * Plan page format 2
 *
 * Copied into ~/.ai/worklog/plans/assets/ by `worklog render-plan` on every render. Do not edit the copy.
 * Light DOM custom elements (no shadow DOM), styled by plan.css. The renderer writes the content:
 *   <plan-page file>
 *     <header class="rail">eyebrow, headline, the three acts</header>
 *     <main>
 *       <plan-section name [class="deep"]><h2>title</h2>
 *         <div class="items"><plan-item key label [url] [done]><div class="cbody">…</div>[<div class="sub">…</div>]</plan-item></div>
 *       </plan-section>
 *     </main>
 *   </plan-page>
 * The page is readable without JS. With JS every <plan-item> gets a checkbox, every section a "2/3" counter, and
 * the bottom bar copies the "done" prompt. Ticks live in localStorage until that prompt is pasted into the session;
 * then the plan JSON marks the items done (the done attribute) and they stay ticked.
 * Load with <script defer src="..."> so all markup is parsed before upgrade.
 */
(function () {
  'use strict';

  const PlanLogic = {
    storageKey(file) {
      return 'daily-workflow:plan:' + file;
    },
    // Ticks that are not in the JSON yet, in page order.
    pending(items, ticks) {
      return items.filter((i) => !i.done && ticks[i.key]);
    },
    prompt(file, items) {
      return ['/daily-workflow:briefing done ' + file]
        .concat(items.map((i) => JSON.stringify({ key: i.key, label: i.label })))
        .join('\n');
    },
    // Keys the JSON already marks done do not need to stay in localStorage.
    prune(items, ticks) {
      const out = {};
      const done = new Set(items.filter((i) => i.done).map((i) => i.key));
      Object.keys(ticks).forEach((k) => { if (ticks[k] && !done.has(k)) out[k] = true; });
      return out;
    },
  };
  globalThis.PlanLogic = PlanLogic;
  if (typeof document === 'undefined') return;

  function load(key) {
    try { return JSON.parse(localStorage.getItem(key) || '{}') || {}; } catch (err) { return {}; }
  }
  function save(key, ticks) {
    try { localStorage.setItem(key, JSON.stringify(ticks)); } catch (err) { /* storage unavailable: ticks last until reload */ }
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

  class PlanItem extends HTMLElement {
    connectedCallback() {
      if (this.box) return;
      this.box = el('input', 'cbx');
      this.box.type = 'checkbox';
      this.box.setAttribute('aria-label', 'Done');
      this.prepend(this.box);
    }
    get data() {
      return { key: this.getAttribute('key') || '', label: this.getAttribute('label') || '', done: this.hasAttribute('done') };
    }
    show(on) {
      const done = this.hasAttribute('done');
      this.classList.toggle('ticked', done || on);
      this.box.checked = done || on;
      this.box.disabled = done;
      this.box.title = done ? 'Marked done in the plan' : '';
    }
  }

  class PlanSection extends HTMLElement {
    count() {
      if (!this.counter) {
        this.counter = el('span', 'cnt');
        const h2 = this.querySelector('h2');
        if (h2) h2.append(this.counter);
      }
      const items = [...this.querySelectorAll('plan-item')];
      const ticked = items.filter((i) => i.classList.contains('ticked')).length;
      this.counter.textContent = ticked + '/' + items.length;
      this.counter.classList.toggle('all', items.length > 0 && ticked === items.length);
    }
  }

  class PlanPage extends HTMLElement {
    connectedCallback() {
      if (this.ready) return;
      this.ready = true;
      const file = this.getAttribute('file') || location.pathname;
      this.storage = PlanLogic.storageKey(file);
      this.file = file;
      this.nodes = [...this.querySelectorAll('plan-item')];
      this.sections = [...this.querySelectorAll('plan-section')];
      this.ticks = PlanLogic.prune(this.items(), load(this.storage));
      save(this.storage, this.ticks);

      this.bar = el('div', 'bar');
      this.counter = el('span');
      const button = el('button', 'btn accent', 'Copy done');
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
      button.addEventListener('click', () => {
        copy(PlanLogic.prompt(this.file, PlanLogic.pending(this.items(), this.ticks))).then(() => {
          this.ok.textContent = 'Copied, paste it into the session';
        });
      });
      this.update();
    }
    items() {
      return this.nodes.map((n) => n.data);
    }
    update() {
      this.nodes.forEach((n) => n.show(!!this.ticks[n.data.key]));
      this.sections.forEach((s) => s.count());
      const n = PlanLogic.pending(this.items(), this.ticks).length;
      this.counter.textContent = n + ' done';
      this.bar.classList.toggle('on', n > 0);
      this.ok.textContent = '';
    }
  }

  // Items and sections first, so the page finds them upgraded.
  customElements.define('plan-item', PlanItem);
  customElements.define('plan-section', PlanSection);
  customElements.define('plan-page', PlanPage);
})();
