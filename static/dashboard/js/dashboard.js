/* =============================================================================
   CRM Dashboard — API Client & Application Logic
   ============================================================================= */
'use strict';

// ─── Config ────────────────────────────────────────────────────────────────
const API_BASE = 'https://agent-job-production.up.railway.app/api/v1';

// ─── Auth ──────────────────────────────────────────────────────────────────
const Auth = {
  TOKEN_KEY: 'crm_token',
  USER_KEY: 'crm_user',

  save(token, user) {
    localStorage.setItem(this.TOKEN_KEY, token);
    localStorage.setItem(this.USER_KEY, JSON.stringify(user));
  },
  load() {
    return {
      token: localStorage.getItem(this.TOKEN_KEY) || '',
      user: JSON.parse(localStorage.getItem(this.USER_KEY) || 'null'),
    };
  },
  clear() {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
  },
  token() { return localStorage.getItem(this.TOKEN_KEY) || ''; },
  user()  { return JSON.parse(localStorage.getItem(this.USER_KEY) || 'null'); },
  isLoggedIn() { return !!localStorage.getItem(this.TOKEN_KEY); },
};

// ─── API Client ─────────────────────────────────────────────────────────────
async function api({ method = 'GET', path, query = null, body = null, token = null }) {
  const t = token || Auth.token();
  const url = new URL(API_BASE + path, location.origin);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== null && v !== undefined && v !== '') url.searchParams.set(k, v);
    }
  }
  const opts = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(t ? { Authorization: `Bearer ${t}` } : {}),
    },
  };
  if (body !== null) opts.body = JSON.stringify(body);
  const res = await fetch(url.pathname + url.search, opts);
  if (res.status === 401) {
    Auth.clear();
    location.reload();
    return null;
  }
  const json = await res.json().catch(() => ({ success: false, message: 'Invalid response' }));
  if (!json.success && res.status >= 400) {
    throw new Error(json.message || `HTTP ${res.status}`);
  }
  return json;
}

function apiGet(path, query) { return api({ method: 'GET', path, query }); }
function apiPost(path, body) { return api({ method: 'POST', path, body }); }
function apiPut(path, body) { return api({ method: 'PUT', path, body }); }
function apiDel(path)        { return api({ method: 'DELETE', path }); }

// ─── State ─────────────────────────────────────────────────────────────────
const State = {
  currentUser: Auth.user(),
  page: 1,
  pageSize: 20,
  search: '',
  filterStatus: '',
  filterOwner: '',
  filterPriority: '',
  sortBy: 'created_at',
  sortDir: 'desc',
  activeTab: 'customers',
  selectedItem: null,
  detailPanelOpen: false,
  kpis: { customers: 0, opportunities: 0, tickets: 0, openTickets: 0 },
  slaBreaches: [],
};

// ─── Helpers ───────────────────────────────────────────────────────────────
function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
}

function fmtAmt(v) {
  if (!v && v !== 0) return '—';
  return '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function timeAgo(isoStr) {
  try {
    const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
  } catch { return isoStr; }
}

function badgeClass(status) {
  const map = {
    active: 'badge-green', inactive: 'badge-gray', blocked: 'badge-red',
    lead: 'badge-blue', customer: 'badge-green', partner: 'badge-purple', prospect: 'badge-yellow',
    open: 'badge-blue', in_progress: 'badge-yellow', pending: 'badge-yellow',
    resolved: 'badge-green', closed: 'badge-gray',
    high: 'badge-red', medium: 'badge-yellow', low: 'badge-green',
  };
  return map[status] || 'badge-gray';
}

function badge(label, cls) {
  return `<span class="badge ${cls || badgeClass(label)}">${esc(label)}</span>`;
}

function tagList(tags) {
  if (!Array.isArray(tags) || !tags.length) return '—';
  return tags.map(t => `<span class="tag">${esc(t)}</span>`).join('');
}

// ─── Toast ─────────────────────────────────────────────────────────────────
let _toastTimer = null;
function toast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ─── Detail Panel ───────────────────────────────────────────────────────────
function openDetail(data, type) {
  State.selectedItem = data;
  State.detailPanelOpen = true;
  renderDetailPanel(data, type);
  document.getElementById('detail-panel').classList.add('open');
}

function closeDetail() {
  State.detailPanelOpen = false;
  document.getElementById('detail-panel').classList.remove('open');
}

function renderDetailPanel(data, type) {
  const panel = document.getElementById('detail-panel');
  if (!data) { panel.innerHTML = ''; return; }

  const header = document.getElementById('detail-panel-header');
  const body   = document.getElementById('detail-panel-body');

  if (type === 'customer') {
    header.textContent = 'Customer Detail';
    body.innerHTML = `
      <div class="detail-row"><span class="detail-label">Name</span><span class="detail-value">${esc(data.name || '')}</span></div>
      <div class="detail-row"><span class="detail-label">Email</span><span class="detail-value">${esc(data.email || '—')}</span></div>
      <div class="detail-row"><span class="detail-label">Phone</span><span class="detail-value">${esc(data.phone || '—')}</span></div>
      <div class="detail-row"><span class="detail-label">Company</span><span class="detail-value">${esc(data.company || '—')}</span></div>
      <div class="detail-row"><span class="detail-label">Status</span><span class="detail-value">${badge(data.status)}</span></div>
      <div class="detail-row"><span class="detail-label">Owner ID</span><span class="detail-value mono">${data.owner_id || '—'}</span></div>
      <div class="detail-row"><span class="detail-label">Tags</span><span class="detail-value">${tagList(data.tags)}</span></div>
      <div class="detail-row"><span class="detail-label">Created</span><span class="detail-value">${fmtDate(data.created_at)}</span></div>
      <div class="detail-row"><span class="detail-label">Updated</span><span class="detail-value">${fmtDate(data.updated_at)}</span></div>
    `;
  } else if (type === 'opportunity') {
    header.textContent = 'Opportunity Detail';
    body.innerHTML = `
      <div class="detail-row"><span class="detail-label">Name</span><span class="detail-value">${esc(data.name || '')}</span></div>
      <div class="detail-row"><span class="detail-label">Customer ID</span><span class="detail-value mono">${data.customer_id || '—'}</span></div>
      <div class="detail-row"><span class="detail-label">Pipeline</span><span class="detail-value mono">${data.pipeline_id || '—'}</span></div>
      <div class="detail-row"><span class="detail-label">Stage</span><span class="detail-value">${badge(data.stage)}</span></div>
      <div class="detail-row"><span class="detail-label">Amount</span><span class="detail-value" style="color:var(--green);font-weight:700">${fmtAmt(data.amount)}</span></div>
      <div class="detail-row"><span class="detail-label">Probability</span><span class="detail-value">${data.probability != null ? data.probability + '%' : '—'}</span></div>
      <div class="detail-row"><span class="detail-label">Close Date</span><span class="detail-value">${fmtDate(data.expected_close_date)}</span></div>
      <div class="detail-row"><span class="detail-label">Owner ID</span><span class="detail-value mono">${data.owner_id || '—'}</span></div>
      <div class="detail-row"><span class="detail-label">Created</span><span class="detail-value">${fmtDate(data.created_at)}</span></div>
    `;
  } else if (type === 'ticket') {
    header.textContent = 'Ticket Detail';
    body.innerHTML = `
      <div class="detail-row"><span class="detail-label">Subject</span><span class="detail-value">${esc(data.subject || '')}</span></div>
      <div class="detail-row"><span class="detail-label">Status</span><span class="detail-value">${badge(data.status)}</span></div>
      <div class="detail-row"><span class="detail-label">Priority</span><span class="detail-value">${badge(data.priority)}</span></div>
      <div class="detail-row"><span class="detail-label">Channel</span><span class="detail-value">${esc(data.channel || '—')}</span></div>
      <div class="detail-row"><span class="detail-label">Customer ID</span><span class="detail-value mono">${data.customer_id || '—'}</span></div>
      <div class="detail-row"><span class="detail-label">Assigned To</span><span class="detail-value mono">${data.assigned_to || '—'}</span></div>
      <div class="detail-row"><span class="detail-label">SLA Level</span><span class="detail-value">${esc(data.sla_level || '—')}</span></div>
      <div class="detail-row"><span class="detail-label">Description</span><span class="detail-value">${esc(data.description || '—')}</span></div>
      <div class="detail-row"><span class="detail-label">Created</span><span class="detail-value">${fmtDate(data.created_at)}</span></div>
      <div class="detail-row"><span class="detail-label">Resolved At</span><span class="detail-value">${fmtDate(data.resolved_at)}</span></div>
      <div class="detail-row"><span class="detail-label">Response Deadline</span><span class="detail-value">${fmtDate(data.response_deadline)}</span></div>
    `;
  } else if (type === 'pipeline') {
    header.textContent = 'Pipeline Detail';
    body.innerHTML = `
      <div class="detail-row"><span class="detail-label">Name</span><span class="detail-value">${esc(data.name || '')}</span></div>
      <div class="detail-row"><span class="detail-label">Default</span><span class="detail-value">${data.is_default ? 'Yes' : 'No'}</span></div>
      <div class="detail-row"><span class="detail-label">Stages</span><span class="detail-value">${(data.stages || []).join(' → ')}</span></div>
      <div class="detail-row"><span class="detail-label">Created</span><span class="detail-value">${fmtDate(data.created_at)}</span></div>
    `;
  } else {
    body.innerHTML = '<div style="padding:16px;color:var(--gray)">No detail available</div>';
  }
}

// ─── Login ─────────────────────────────────────────────────────────────────
async function handleLogin(e) {
  e.preventDefault();
  const errEl = document.getElementById('login-error');
  const btn = document.getElementById('login-btn');
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  errEl.textContent = '';
  btn.disabled = true;
  btn.textContent = 'Signing in…';

  try {
    const form = new URLSearchParams({ username, password, grant_type: 'password' });
    const res = await fetch(API_BASE + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form,
    });
    const json = await res.json().catch(() => null);
    if (!res.ok || !json.access_token) {
      errEl.textContent = json?.detail || 'Invalid credentials';
      return;
    }
    // Fetch user profile
    const profileRes = await api({ method: 'GET', path: '/users/me', token: json.access_token });
    if (!profileRes?.data) throw new Error('Failed to fetch user profile');
    Auth.save(json.access_token, profileRes.data);
    showApp();
    await loadDashboardData();
  } catch (err) {
    errEl.textContent = err.message || 'Login failed';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign In';
  }
}

function handleLogout() {
  Auth.clear();
  location.reload();
}

// ─── App Init ────────────────────────────────────────────────────────────────
function showApp() {
  const user = Auth.user();
  if (!user) { document.getElementById('login-screen').style.display = 'flex'; return; }
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app').classList.add('visible');
  document.getElementById('user-name').textContent = esc(user.full_name || user.username || 'User');
  document.getElementById('user-role').textContent = esc(user.role || 'user');
}

async function loadDashboardData() {
  await Promise.allSettled([
    loadKPIs(),
    loadSLABreaches(),
  ]);
}

// ─── KPIs ──────────────────────────────────────────────────────────────────
async function loadKPIs() {
  try {
    const [custRes, oppRes, tickRes] = await Promise.all([
      apiGet('/customers', { page: 1, page_size: 1 }),
      apiGet('/sales/opportunities', { page: 1, page_size: 1 }),
      apiGet('/tickets', { page: 1, page_size: 1 }),
    ]);
    const tickOpenRes = apiGet('/tickets', { status: 'open', page_size: 1 });
    State.kpis.customers     = custRes?.data?.total || 0;
    State.kpis.opportunities = oppRes?.data?.total || 0;
    State.kpis.tickets       = tickRes?.data?.total || 0;
    State.kpis.openTickets   = (await tickOpenRes)?.data?.total || 0;
    renderKPIs();
  } catch { /* silent */ }
}

function renderKPIs() {
  document.getElementById('kpi-customers').textContent     = State.kpis.customers.toLocaleString();
  document.getElementById('kpi-opportunities').textContent = State.kpis.opportunities.toLocaleString();
  document.getElementById('kpi-tickets').textContent       = State.kpis.tickets.toLocaleString();
  document.getElementById('kpi-open-tickets').textContent  = State.kpis.openTickets.toLocaleString();
}

async function loadSLABreaches() {
  try {
    const res = await apiGet('/tickets/sla/breaches');
    State.slaBreaches = res?.data || [];
    renderSLABreaches();
  } catch { /* silent */ }
}

function renderSLABreaches() {
  const banner = document.getElementById('sla-banner');
  const count = State.slaBreaches.length;
  if (count > 0) {
    banner.style.display = 'flex';
    document.getElementById('sla-count').textContent = count;
  } else {
    banner.style.display = 'none';
  }
}

// ─── Navigation ────────────────────────────────────────────────────────────
function navigate(tab) {
  State.activeTab = tab;
  State.page = 1;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.tab === tab));
  document.querySelectorAll('.page-view').forEach(el => el.classList.toggle('hidden', el.id !== 'view-' + tab));
  closeDetail();
  loadCurrentTab();
}

function loadCurrentTab() {
  switch (State.activeTab) {
    case 'customers':    return loadCustomers();
    case 'opportunities': return loadOpportunities();
    case 'tickets':      return loadTickets();
    case 'pipelines':    return loadPipelines();
    case 'users':       return loadUsers();
  }
}

// ─── Pagination helpers ─────────────────────────────────────────────────────
function renderPagination(info) {
  const { page, page_size, total, total_pages, has_next, has_prev } = info;
  const start = total === 0 ? 0 : (page - 1) * page_size + 1;
  const end   = Math.min(page * page_size, total);
  document.getElementById('pagi-info').textContent = total === 0 ? 'No results' : `Showing ${start}–${end} of ${total}`;
  document.getElementById('pagi-prev').disabled = !has_prev;
  document.getElementById('pagi-next').disabled = !has_next;
}

function prevPage() { if (State.page > 1) { State.page--; loadCurrentTab(); } }
function nextPage() { State.page++; loadCurrentTab(); }

// ─── Customers ─────────────────────────────────────────────────────────────
let _customerCols = [
  { label: 'Name',    key: 'name' },
  { label: 'Email',  key: 'email' },
  { label: 'Phone',  key: 'phone' },
  { label: 'Status', key: 'status' },
  { label: 'Tags',   key: 'tags' },
  { label: 'Owner',  key: 'owner_id', cls: 'mono' },
  { label: 'Created',key: 'created_at' },
];

async function loadCustomers(searchable = false) {
  const tbody = document.getElementById('customers-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="8"><span class="spinner"></span></td></tr>';
  document.getElementById('customers-count').textContent = '…';

  try {
    const keyword = searchable ? document.getElementById('customer-search').value.trim() : '';
    const res = keyword
      ? await apiGet('/customers/search', { keyword })
      : await apiGet('/customers', { page: State.page, page_size: State.pageSize, status: State.filterStatus, owner_id: State.filterOwner || null });
    const data = res?.data;
    if (!data) { tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Failed to load</td></tr>'; return; }

    document.getElementById('customers-count').textContent = data.total || 0;
    if (!data.items || data.items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty-state"><div class="empty-icon">📋</div>No customers found</td></tr>';
    } else {
      tbody.innerHTML = data.items.map(c => `
        <tr data-id="${c.id}" onclick="openCustomerDetail(${c.id})">
          <td><strong>${esc(c.name || '')}</strong></td>
          <td>${esc(c.email || '—')}</td>
          <td class="mono">${esc(c.phone || '—')}</td>
          <td>${badge(c.status)}</td>
          <td>${tagList(c.tags)}</td>
          <td class="mono">${c.owner_id || '—'}</td>
          <td>${fmtDate(c.created_at)}</td>
        </tr>`).join('');
    }
    if (!keyword) renderPagination(data);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty-state">Error: ${esc(err.message)}</td></tr>`;
  }
}

async function openCustomerDetail(id) {
  try {
    const res = await apiGet(`/customers/${id}`);
    if (res?.data) openDetail(res.data, 'customer');
  } catch { toast('Failed to load customer', 'error'); }
}

async function createCustomer() {
  const name = document.getElementById('cust-name').value.trim();
  const email = document.getElementById('cust-email').value.trim();
  const phone = document.getElementById('cust-phone').value.trim();
  const company = document.getElementById('cust-company').value.trim();
  const status = document.getElementById('cust-status').value;
  if (!name) { toast('Name is required', 'error'); return; }
  try {
    const res = await apiPost('/customers', { name, email, phone, company, status });
    if (res?.success) {
      toast('Customer created', 'success');
      closeModal();
      loadCustomers();
    } else {
      toast(res?.message || 'Create failed', 'error');
    }
  } catch (err) { toast(err.message, 'error'); }
}

async function changeCustomerStatus(id) {
  const status = prompt('New status (active|inactive|blocked):');
  if (!status) return;
  try {
    const res = await apiPut(`/customers/${id}/status`, { status });
    if (res?.success) { toast('Status updated', 'success'); loadCustomers(); closeDetail(); }
    else toast(res?.message || 'Update failed', 'error');
  } catch (err) { toast(err.message, 'error'); }
}

// ─── Opportunities ────────────────────────────────────────────────────────
async function loadOpportunities() {
  const tbody = document.getElementById('opps-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="9"><span class="spinner"></span></td></tr>';
  document.getElementById('opps-count').textContent = '…';

  try {
    const res = await apiGet('/sales/opportunities', {
      page: State.page, page_size: State.pageSize,
      pipeline_id: State.filterPipeline || null,
      stage: State.filterStage || null,
    });
    const data = res?.data;
    if (!data) { tbody.innerHTML = '<tr><td colspan="9" class="empty-state">Failed to load</td></tr>'; return; }

    document.getElementById('opps-count').textContent = data.total || 0;
    if (!data.items || data.items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="empty-state"><div class="empty-icon">📈</div>No opportunities found</td></tr>';
    } else {
      tbody.innerHTML = data.items.map(o => `
        <tr data-id="${o.id}" onclick="openOppDetail(${o.id})">
          <td><strong>${esc(o.name || '')}</strong></td>
          <td class="mono">${o.customer_id || '—'}</td>
          <td class="mono">${o.pipeline_id || '—'}</td>
          <td>${badge(o.stage)}</td>
          <td class="num" style="color:var(--green);font-weight:700">${fmtAmt(o.amount)}</td>
          <td class="num">${o.probability != null ? o.probability + '%' : '—'}</td>
          <td>${fmtDate(o.expected_close_date)}</td>
          <td class="mono">${o.owner_id || '—'}</td>
          <td>${fmtDate(o.created_at)}</td>
        </tr>`).join('');
    }
    renderPagination(data);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9" class="empty-state">Error: ${esc(err.message)}</td></tr>`;
  }
}

async function openOppDetail(id) {
  try {
    const res = await apiGet(`/sales/opportunities/${id}`);
    if (res?.data) openDetail(res.data, 'opportunity');
  } catch { toast('Failed to load opportunity', 'error'); }
}

async function changeOppStage(id) {
  const stage = prompt('New stage:');
  if (!stage) return;
  try {
    const res = await apiPut(`/sales/opportunities/${id}/stage`, { stage });
    if (res?.success) { toast('Stage updated', 'success'); loadOpportunities(); closeDetail(); }
    else toast(res?.message || 'Update failed', 'error');
  } catch (err) { toast(err.message, 'error'); }
}

// ─── Tickets ──────────────────────────────────────────────────────────────
async function loadTickets() {
  const tbody = document.getElementById('tickets-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="8"><span class="spinner"></span></td></tr>';
  document.getElementById('tickets-count').textContent = '…';

  try {
    const res = await apiGet('/tickets', {
      page: State.page, page_size: State.pageSize,
      status: State.filterStatus || null,
      priority: State.filterPriority || null,
    });
    const data = res?.data;
    if (!data) { tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Failed to load</td></tr>'; return; }

    document.getElementById('tickets-count').textContent = data.total || 0;
    if (!data.items || data.items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty-state"><div class="empty-icon">🎫</div>No tickets found</td></tr>';
    } else {
      tbody.innerHTML = data.items.map(t => `
        <tr data-id="${t.id}" onclick="openTicketDetail(${t.id})">
          <td class="mono">${t.id}</td>
          <td><strong>${esc(t.subject || '')}</strong></td>
          <td>${badge(t.status)}</td>
          <td>${badge(t.priority)}</td>
          <td>${esc(t.channel || '—')}</td>
          <td class="mono">${t.customer_id || '—'}</td>
          <td class="mono">${t.assigned_to || '—'}</td>
          <td>${fmtDate(t.created_at)}</td>
        </tr>`).join('');
    }
    renderPagination(data);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty-state">Error: ${esc(err.message)}</td></tr>`;
  }
}

async function openTicketDetail(id) {
  try {
    const res = await apiGet(`/tickets/${id}`);
    if (res?.data) openDetail(res.data, 'ticket');
  } catch { toast('Failed to load ticket', 'error'); }
}

async function assignTicket(id) {
  const assigneeId = prompt('Assignee user ID:');
  if (!assigneeId) return;
  try {
    const res = await apiPut(`/tickets/${id}/assign`, { assignee_id: parseInt(assigneeId) });
    if (res?.success) { toast('Ticket assigned', 'success'); loadTickets(); closeDetail(); }
    else toast(res?.message || 'Assign failed', 'error');
  } catch (err) { toast(err.message, 'error'); }
}

// ─── Pipelines ─────────────────────────────────────────────────────────────
async function loadPipelines() {
  const container = document.getElementById('pipelines-container');
  container.innerHTML = '<div style="padding:20px;color:var(--gray)"><span class="spinner"></span></div>';

  try {
    const res = await apiGet('/sales/pipelines');
    const data = res?.data;
    if (!data || !data.items || data.items.length === 0) {
      container.innerHTML = '<div class="empty-state"><div class="empty-icon">📊</div>No pipelines</div>';
      return;
    }
    container.innerHTML = '';
    for (const p of data.items) {
      const statsRes = await apiGet(`/sales/pipelines/${p.id}/stats`).catch(() => null);
      const funnelRes = await apiGet(`/sales/pipelines/${p.id}/funnel`).catch(() => null);
      const oppRes = await apiGet('/sales/opportunities', { pipeline_id: p.id, page_size: 100 });
      const stages = p.stages || [];
      const opportunities = oppRes?.data?.items || [];

      // Build funnel counts
      const funnelStages = funnelRes?.data?.stages || {};

      // Group opps by stage
      const stageGroups = {};
      stages.forEach(s => { stageGroups[s] = []; });
      opportunities.forEach(o => { if (stageGroups[o.stage]) stageGroups[o.stage].push(o); });

      const stats = statsRes?.data || {};
      const col = document.createElement('div');
      col.className = 'kanban-col';
      col.innerHTML = `
        <div class="kanban-col-header">
          <span>${esc(p.name)} ${p.is_default ? '⭐' : ''}</span>
          <span class="kanban-col-count">${opportunities.length}</span>
        </div>
        ${stages.map(s => `
          <div style="margin-bottom:14px">
            <div class="kanban-col-header" style="padding:4px 0 8px;font-size:11px">
              <span>${esc(s)}</span>
              <span class="kanban-col-count">${stageGroups[s].length}</span>
            </div>
            ${stageGroups[s].map(o => `
              <div class="kanban-card" onclick="openOppDetail(${o.id})">
                <div class="kanban-card-name">${esc(o.name || '')}</div>
                <div class="kanban-card-meta">${fmtAmt(o.amount)} · ${o.probability != null ? o.probability + '%' : '?'}</div>
              </div>
            `).join('')}
            ${stageGroups[s].length === 0 ? '<div style="font-size:11px;color:var(--gray);padding:4px 0">No opportunities</div>' : ''}
          </div>
        `).join('')}
      `;
      container.appendChild(col);
    }
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Error: ${esc(err.message)}</div>`;
  }
}

// ─── Users ─────────────────────────────────────────────────────────────────
async function loadUsers() {
  const tbody = document.getElementById('users-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="6"><span class="spinner"></span></td></tr>';
  document.getElementById('users-count').textContent = '…';

  try {
    const res = await apiGet('/users', { page: State.page, page_size: State.pageSize });
    const data = res?.data;
    if (!data) { tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Failed to load</td></tr>'; return; }

    document.getElementById('users-count').textContent = data.total || 0;
    if (!data.items || data.items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state"><div class="empty-icon">👤</div>No users found</td></tr>';
    } else {
      tbody.innerHTML = data.items.map(u => `
        <tr>
          <td class="mono">${u.id}</td>
          <td><strong>${esc(u.full_name || u.username || '')}</strong></td>
          <td>${esc(u.email || '—')}</td>
          <td>${badge(u.role)}</td>
          <td>${badge(u.status)}</td>
          <td>${fmtDate(u.created_at)}</td>
        </tr>`).join('');
    }
    renderPagination(data);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Error: ${esc(err.message)}</td></tr>`;
  }
}

// ─── Modal ────────────────────────────────────────────────────────────────────
function openModal(title, content, footer) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = content;
  document.getElementById('modal-footer').innerHTML = footer;
  document.getElementById('modal-overlay').classList.add('open');
}
function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
}
function confirmModal(title, body, onConfirm) {
  openModal(title, body, `
    <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
    <button class="btn btn-danger" id="modal-confirm-btn">Confirm</button>
  `);
  document.getElementById('modal-confirm-btn').onclick = () => { onConfirm(); closeModal(); };
}

// ─── Create Ticket ──────────────────────────────────────────────────────────
function showCreateTicketModal() {
  openModal('Create Ticket', `
    <div class="field"><label>Subject *</label><input id="tick-subject" placeholder="Brief description of the issue"></div>
    <div class="field"><label>Description *</label><textarea id="tick-desc" placeholder="Detailed description"></textarea></div>
    <div class="field-row">
      <div class="field">
        <label>Customer ID *</label>
        <input id="tick-cust" type="number" placeholder="1">
      </div>
      <div class="field">
        <label>Channel *</label>
        <select id="tick-channel">
          <option value="email">Email</option>
          <option value="phone">Phone</option>
          <option value="chat">Chat</option>
          <option value="portal">Portal</option>
        </select>
      </div>
    </div>
    <div class="field-row">
      <div class="field">
        <label>Priority</label>
        <select id="tick-priority">
          <option value="low">Low</option>
          <option value="medium" selected>Medium</option>
          <option value="high">High</option>
        </select>
      </div>
      <div class="field">
        <label>SLA Level</label>
        <select id="tick-sla">
          <option value="standard" selected>Standard</option>
          <option value="premium">Premium</option>
          <option value="enterprise">Enterprise</option>
        </select>
      </div>
    </div>
  `, `<button class="btn btn-ghost" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="submitCreateTicket()">Create Ticket</button>`);
}

async function submitCreateTicket() {
  const subject = document.getElementById('tick-subject').value.trim();
  const description = document.getElementById('tick-desc').value.trim();
  const customer_id = parseInt(document.getElementById('tick-cust').value);
  const channel = document.getElementById('tick-channel').value;
  const priority = document.getElementById('tick-priority').value;
  const sla_level = document.getElementById('tick-sla').value;
  if (!subject || !description || !customer_id) { toast('Subject, description, and customer ID are required', 'error'); return; }
  try {
    const res = await apiPost('/tickets', { subject, description, customer_id, channel, priority, sla_level });
    if (res?.success) { toast('Ticket created', 'success'); closeModal(); loadTickets(); }
    else toast(res?.message || 'Create failed', 'error');
  } catch (err) { toast(err.message, 'error'); }
}

// ─── Create Customer ───────────────────────────────────────────────────────
function showCreateCustomerModal() {
  openModal('Create Customer', `
    <div class="field"><label>Name *</label><input id="cust-name" placeholder="Company or contact name"></div>
    <div class="field-row">
      <div class="field">
        <label>Email</label>
        <input id="cust-email" type="email" placeholder="contact@example.com">
      </div>
      <div class="field">
        <label>Phone</label>
        <input id="cust-phone" placeholder="+86-138-0000-0000">
      </div>
    </div>
    <div class="field-row">
      <div class="field">
        <label>Company</label>
        <input id="cust-company" placeholder="Company name">
      </div>
      <div class="field">
        <label>Status</label>
        <select id="cust-status">
          <option value="lead" selected>Lead</option>
          <option value="customer">Customer</option>
          <option value="partner">Partner</option>
          <option value="prospect">Prospect</option>
        </select>
      </div>
    </div>
  `, `<button class="btn btn-ghost" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createCustomer()">Create Customer</button>`);
}

// ─── Create Opportunity ────────────────────────────────────────────────────
function showCreateOppModal() {
  openModal('Create Opportunity', `
    <div class="field"><label>Name *</label><input id="opp-name" placeholder="Opportunity name"></div>
    <div class="field-row">
      <div class="field">
        <label>Customer ID *</label>
        <input id="opp-cust" type="number" placeholder="1">
      </div>
      <div class="field">
        <label>Pipeline ID *</label>
        <input id="opp-pipeline" type="number" placeholder="1">
      </div>
    </div>
    <div class="field-row">
      <div class="field">
        <label>Stage *</label>
        <input id="opp-stage" placeholder="lead">
      </div>
      <div class="field">
        <label>Amount *</label>
        <input id="opp-amount" type="number" placeholder="50000">
      </div>
    </div>
    <div class="field-row">
      <div class="field">
        <label>Owner ID *</label>
        <input id="opp-owner" type="number" placeholder="1">
      </div>
      <div class="field">
        <label>Close Date</label>
        <input id="opp-close" type="date" placeholder="2026-06-30">
      </div>
    </div>
  `, `<button class="btn btn-ghost" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="submitCreateOpp()">Create Opportunity</button>`);
}

async function submitCreateOpp() {
  const name = document.getElementById('opp-name').value.trim();
  const customer_id = parseInt(document.getElementById('opp-cust').value);
  const pipeline_id = parseInt(document.getElementById('opp-pipeline').value);
  const stage = document.getElementById('opp-stage').value.trim();
  const amount = parseFloat(document.getElementById('opp-amount').value);
  const owner_id = parseInt(document.getElementById('opp-owner').value);
  const close_date = document.getElementById('opp-close').value || undefined;
  if (!name || !customer_id || !pipeline_id || !stage || isNaN(amount) || !owner_id) {
    toast('All required fields must be filled', 'error'); return;
  }
  try {
    const res = await apiPost('/sales/opportunities', { name, customer_id, pipeline_id, stage, amount, owner_id, close_date });
    if (res?.success) { toast('Opportunity created', 'success'); closeModal(); loadOpportunities(); }
    else toast(res?.message || 'Create failed', 'error');
  } catch (err) { toast(err.message, 'error'); }
}

// ─── Filter helpers ────────────────────────────────────────────────────────
function applyCustomerFilters() {
  State.filterStatus = document.getElementById('filter-status').value;
  State.filterOwner = document.getElementById('filter-owner').value;
  State.page = 1;
  loadCustomers();
}

// ─── Init ──────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Login form
  document.getElementById('login-form').addEventListener('submit', handleLogin);

  // Show app if already logged in
  showApp();

  // Sidebar navigation
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => navigate(el.dataset.tab));
  });

  // Close detail panel
  document.getElementById('detail-panel-close').addEventListener('click', closeDetail);

  // Modal close on overlay click
  document.getElementById('modal-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
  });

  // Global keyboard
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeModal(); closeDetail(); }
  });
});
