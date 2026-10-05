(() => {
  'use strict';
  document.documentElement.classList.add("js");
  const input = document.querySelector('input[data-search]');
  const filters = [...document.querySelectorAll('[data-filter]')];
  const cards = [...document.querySelectorAll('[data-issue]')];
  const count = document.querySelector('[data-count]');
  const empty = document.querySelector('[data-empty]');
  if (!input) return;
  let column = 'all';
  function update() {
    const query = input.value.trim().toLocaleLowerCase();
    let visible = 0;
    cards.forEach(card => {
      const show = (column === 'all' || card.dataset.column === column) && card.dataset.search.includes(query);
      card.hidden = !show;
      if (show) visible++;
    });
    if (count) count.textContent = `${visible} 篇周报`;
    if (empty) empty.hidden = visible !== 0;
  }
  filters.forEach(button => button.addEventListener('click', () => {
    column = button.dataset.filter;
    filters.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    update();
  }));
  input.addEventListener('input', update);
  input.addEventListener('keydown', event => { if (event.key === 'Escape') { input.value = ''; update(); } });
  document.querySelector('[data-reset]')?.addEventListener('click', () => { input.value = ''; column = 'all'; filters.forEach(b => b.setAttribute('aria-pressed',String(b.dataset.filter === 'all'))); update(); input.focus(); });
  update();
})();
