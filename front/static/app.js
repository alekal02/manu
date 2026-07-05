// Tabs, accordion, search e menu mobile
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initAccordion();
  initDashboard();
  initMobileMenu();
});

function initTabs() {
  document.querySelectorAll('[data-tabs]').forEach(root => {
    const buttons = root.querySelectorAll('.tab-btn');
    const panels = root.querySelectorAll('.tab-panel');

    buttons.forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.tab;
        buttons.forEach(b => b.classList.toggle('active', b === btn));
        panels.forEach(p => p.classList.toggle('active', p.id === target));
      });
    });
  });
}

function initAccordion() {
  document.querySelectorAll('.accordion-trigger').forEach(trigger => {
    trigger.addEventListener('click', () => {
      const item = trigger.closest('.accordion-item');
      const wasOpen = item.classList.contains('open');
      item.closest('.accordion-list')?.querySelectorAll('.accordion-item.open')
        .forEach(el => el.classList.remove('open'));
      if (!wasOpen) item.classList.add('open');
    });
  });
}

function initDashboard() {
  const input = document.getElementById('busca-ativos');
  const filters = document.getElementById('dash-filters');
  const list = document.getElementById('dash-list');
  if (!list) return;

  let activeFilter = 'todos';

  const applyFilters = () => {
    const term = (input?.value || '').toLowerCase().trim();
    let visible = 0;

    list.querySelectorAll('.dash-asset-row').forEach(row => {
      const text = row.dataset.search || '';
      const status = row.dataset.status;
      const local = row.dataset.local;

      const matchSearch = !term || text.includes(term);
      let matchFilter = true;
      if (activeFilter === 'operacional') matchFilter = status === 'operacional';
      else if (activeFilter === 'manutencao') matchFilter = status === 'manutencao';
      else if (activeFilter === 'base') matchFilter = local === 'base';
      else if (activeFilter === 'servico') matchFilter = local === 'servico';
      else if (activeFilter === 'deslocamento') matchFilter = local === 'deslocamento';
      else if (activeFilter === 'terceiros') matchFilter = local === 'terceiros';

      const show = matchSearch && matchFilter;
      row.classList.toggle('hidden-row', !show);
      if (show) visible++;
    });

    const counter = document.getElementById('dash-count');
    if (counter) counter.textContent = visible;

    const noResults = document.getElementById('dash-no-results');
    if (noResults) noResults.classList.toggle('hidden-row', visible > 0);
  };

  input?.addEventListener('input', applyFilters);

  filters?.querySelectorAll('.filter-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      filters.querySelectorAll('.filter-pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeFilter = btn.dataset.filter;
      applyFilters();
    });
  });
}

function initMobileMenu() {
  const toggle = document.getElementById('menu-toggle');
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  if (!toggle || !sidebar || window.matchMedia('(min-width: 769px)').matches) return;

  const close = () => {
    sidebar.classList.remove('open');
    overlay?.classList.remove('visible');
    document.body.classList.remove('menu-open');
  };

  toggle.addEventListener('click', () => {
    const opening = !sidebar.classList.contains('open');
    sidebar.classList.toggle('open');
    overlay?.classList.toggle('visible');
    document.body.classList.toggle('menu-open', opening);
  });

  overlay?.addEventListener('click', close);
  sidebar.querySelectorAll('.nav-item').forEach(link => link.addEventListener('click', close));
}
