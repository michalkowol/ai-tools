/*
 * daily-workflow plan page: checkboxes.
 * Plan page format 1
 *
 * Copied into ~/.ai/worklog/plans/assets/ by `worklog render-plan` on every render. Do not edit the copy.
 * Every item rendered with data-key gets a working checkbox. Ticks live in localStorage until the "Copy done"
 * prompt is pasted into the session; then the plan JSON marks them done (data-done) and they stay ticked.
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

  function start() {
    const file = document.body.dataset.file || location.pathname;
    const key = PlanLogic.storageKey(file);
    const nodes = Array.from(document.querySelectorAll('.chk[data-key]'));
    const items = nodes.map((el) => ({ el, key: el.dataset.key, label: el.dataset.label || '', done: el.hasAttribute('data-done') }));
    let ticks = PlanLogic.prune(items, load(key));
    save(key, ticks);

    const bar = document.createElement('div');
    bar.className = 'bar';
    const count = document.createElement('span');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Copy done';
    const ok = document.createElement('span');
    ok.className = 'ok';
    bar.append(count, button, ok);
    document.body.appendChild(bar);

    function update() {
      items.forEach((i) => {
        const on = i.done || !!ticks[i.key];
        i.el.classList.toggle('done', on);
        const box = i.el.querySelector(':scope > .cbx');
        box.checked = on;
        box.disabled = i.done;
        box.title = i.done ? 'Marked done in the plan' : '';
      });
      const n = PlanLogic.pending(items, ticks).length;
      count.textContent = n + ' done';
      bar.classList.toggle('on', n > 0);
      ok.textContent = '';
    }

    items.forEach((i) => {
      i.el.querySelector(':scope > .cbx').addEventListener('change', (ev) => {
        if (ev.target.checked) ticks[i.key] = true; else delete ticks[i.key];
        save(key, ticks);
        update();
      });
    });
    button.addEventListener('click', () => {
      copy(PlanLogic.prompt(file, PlanLogic.pending(items, ticks))).then(() => {
        ok.textContent = 'Copied, paste it into the session';
      });
    });
    update();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
