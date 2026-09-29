(() => {
  const select = document.getElementById('date');
  if (!select) return;

  const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
  const chevron = '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const check = '<svg class="date-select-check" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="m2.5 7.5 3 3 6-7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const label = select.getAttribute('aria-label') || 'Date';

  const wrapper = document.createElement('div');
  wrapper.className = 'date-select';
  select.before(wrapper);
  select.classList.add('date-select-native');
  select.tabIndex = -1;
  select.setAttribute('aria-hidden', 'true');

  const trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'date-select-trigger';
  trigger.setAttribute('aria-haspopup', 'listbox');
  trigger.setAttribute('aria-expanded', 'false');
  trigger.setAttribute('aria-controls', 'date-select-list');

  const list = document.createElement('div');
  list.id = 'date-select-list';
  list.className = 'date-select-list';
  list.setAttribute('role', 'listbox');
  list.setAttribute('aria-label', label);
  list.tabIndex = -1;
  list.hidden = true;

  wrapper.append(select, trigger, list);

  let options = [];
  let activeIndex = -1;

  function asUtcDate(text) {
    return new Date(`${text}T00:00:00Z`);
  }

  function selectedText() {
    return select.selectedOptions[0]?.textContent.trim() ?? '';
  }

  function syncTrigger() {
    const text = selectedText();
    trigger.innerHTML = `<span>${text || '—'}</span>${chevron}`;
    trigger.setAttribute('aria-label', `${label}: ${text || 'none'}`);
  }

  function optionMarkup(option, index) {
    const text = option.textContent.trim();
    const weekday = ISO_DATE.test(text)
      ? asUtcDate(text).toLocaleDateString('en-US', { weekday: 'short', timeZone: 'UTC' })
      : '';
    return `<div role="option" id="date-select-option-${index}" class="date-select-option" data-value="${option.value}" aria-selected="${option.selected}">${check}<span>${text}</span><span class="date-select-weekday">${weekday}</span></div>`;
  }

  function buildList() {
    const newestFirst = [...select.options].map((option, index) => ({ option, index })).reverse();
    let currentMonth = null;
    let html = '';
    for (const { option, index } of newestFirst) {
      const text = option.textContent.trim();
      if (ISO_DATE.test(text)) {
        const month = asUtcDate(text).toLocaleDateString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' });
        if (month !== currentMonth) {
          if (currentMonth !== null) html += '</div>';
          html += `<div role="group" aria-label="${month}"><div class="date-select-month" aria-hidden="true">${month}</div>`;
          currentMonth = month;
        }
      }
      html += optionMarkup(option, index);
    }
    if (currentMonth !== null) html += '</div>';
    list.innerHTML = html;
    options = [...list.querySelectorAll('[role="option"]')];
  }

  function setActive(index, { scroll = true } = {}) {
    if (!options.length) return;
    activeIndex = Math.max(0, Math.min(options.length - 1, index));
    options.forEach((option, i) => option.classList.toggle('is-active', i === activeIndex));
    const active = options[activeIndex];
    list.setAttribute('aria-activedescendant', active.id);
    if (scroll) active.scrollIntoView({ block: 'nearest' });
  }

  function open() {
    buildList();
    list.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
    const selectedIndex = options.findIndex(option => option.getAttribute('aria-selected') === 'true');
    setActive(selectedIndex === -1 ? 0 : selectedIndex);
    list.focus({ preventScroll: true });
  }

  function close({ restoreFocus = false } = {}) {
    if (list.hidden) return;
    list.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
    list.removeAttribute('aria-activedescendant');
    if (restoreFocus) trigger.focus();
  }

  function choose(option) {
    const value = option.dataset.value;
    close({ restoreFocus: true });
    if (select.value === value) return;
    select.value = value;
    select.dispatchEvent(new Event('change', { bubbles: true }));
  }

  trigger.addEventListener('click', () => (list.hidden ? open() : close()));

  trigger.addEventListener('keydown', event => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      open();
    }
  });

  list.addEventListener('keydown', event => {
    const page = 8;
    const moves = {
      ArrowDown: activeIndex + 1,
      ArrowUp: activeIndex - 1,
      PageDown: activeIndex + page,
      PageUp: activeIndex - page,
      Home: 0,
      End: options.length - 1,
    };
    if (event.key in moves) {
      event.preventDefault();
      setActive(moves[event.key]);
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (options[activeIndex]) choose(options[activeIndex]);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      close({ restoreFocus: true });
    } else if (event.key === 'Tab') {
      close();
    }
  });

  list.addEventListener('pointermove', event => {
    const option = event.target.closest('[role="option"]');
    if (option) setActive(options.indexOf(option), { scroll: false });
  });

  list.addEventListener('click', event => {
    const option = event.target.closest('[role="option"]');
    if (option) choose(option);
  });

  document.addEventListener('pointerdown', event => {
    if (!wrapper.contains(event.target)) close();
  });

  wrapper.addEventListener('focusout', event => {
    if (event.relatedTarget && !wrapper.contains(event.relatedTarget)) close();
  });

  select.addEventListener('change', syncTrigger);
  syncTrigger();
})();
