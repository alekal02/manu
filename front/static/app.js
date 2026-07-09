// Tabs, accordion, search, check-in e menu mobile
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initAccordion();
  initDashboard();
  initCheckinForms();
  initMobileMenu();
  scrollToFoco();
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
  const rows = () => list.querySelectorAll('.dash-asset-row, .checkin-card');

  const applyFilters = () => {
    const term = (input?.value || '').toLowerCase().trim();
    let visible = 0;

    rows().forEach(row => {
      const text = row.dataset.search || '';
      const status = row.dataset.status;
      const local = row.dataset.local;
      const pendente = row.dataset.pendente;

      const matchSearch = !term || text.includes(term);
      let matchFilter = true;
      if (activeFilter === 'operacional') matchFilter = status === 'operacional';
      else if (activeFilter === 'manutencao') matchFilter = status === 'manutencao';
      else if (activeFilter === 'pendente') matchFilter = pendente === 'sim';
      else if (activeFilter === 'base') matchFilter = status === 'manutencao' && local === 'base';
      else if (activeFilter === 'terceiros') matchFilter = status === 'manutencao' && local === 'terceiros';
      else if (activeFilter === 'servico') matchFilter = local === 'servico';
      else if (activeFilter === 'deslocamento') matchFilter = local === 'deslocamento';

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

function syncManutFields(form) {
  const manutencao = form.querySelector('input[name="em_manutencao"][value="sim"]')?.checked;
  const fields = form.querySelector('[data-manut-fields]');
  const osInput = form.querySelector('[data-os-input]');
  const localSelect = form.querySelector('[data-local-select]');

  if (fields) fields.classList.toggle('is-hidden', !manutencao);
  if (osInput) {
    osInput.required = !!manutencao;
    if (!manutencao) osInput.value = '';
  }
  if (localSelect) {
    localSelect.required = !!manutencao;
    if (!manutencao) localSelect.value = '';
  }
}

function initCheckinForms() {
  document.querySelectorAll('[data-checkin-form]').forEach(form => {
    form.querySelectorAll('[data-status-toggle]').forEach(input => {
      input.addEventListener('change', () => syncManutFields(form));
    });
    syncManutFields(form);

    form.addEventListener('submit', (e) => {
      const manutencao = form.querySelector('input[name="em_manutencao"][value="sim"]')?.checked;
      if (!manutencao) return;

      const os = (form.querySelector('[data-os-input]')?.value || '').trim();
      const local = (form.querySelector('[data-local-select]')?.value || '').trim();
      if (!os || !local) {
        e.preventDefault();
        alert('Em manutenção, informe a OS e se está na base ou em terceiros.');
      }
    });
  });
}

function scrollToFoco() {
  const params = new URLSearchParams(window.location.search);
  const foco = params.get('foco');
  if (!foco) return;
  const el = document.getElementById(`ativo-${foco}`);
  if (!el) return;
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  el.classList.add('checkin-highlight');
  setTimeout(() => el.classList.remove('checkin-highlight'), 1800);
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
