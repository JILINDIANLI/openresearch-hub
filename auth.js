(() => {
  let currentUser = null;
  let initialized = false;

  function token() { return null; }
  function initials(user) { return (user?.display_name || user?.username || 'OR').split(/[\s_-]+/).filter(Boolean).map(part => part[0]).join('').slice(0, 2).toUpperCase(); }
  function escapeHtml(value) { return String(value ?? '').replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[char])); }

  async function request(url, options = {}) {
    const headers = new Headers(options.headers || {});
    const response = await fetch(url, { ...options, headers, credentials: 'same-origin' });
    if (response.status === 401 && currentUser) {
      currentUser = null;
      renderAll();
    }
    return response;
  }

  async function refreshUser() {
    try {
      const response = await request('/api/auth/me');
      if (!response.ok) throw new Error('会话暂不可用');
      currentUser = await response.json();
    } catch (_) { currentUser = null; }
    renderAll();
    return currentUser;
  }

  async function login(identifier, password) {
    const response = await fetch('/api/auth/login', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type':'application/json' }, body: JSON.stringify({ identifier, password }) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || '登录失败');
    currentUser = data.user;
    renderAll();
    return data.user;
  }

  async function logout() {
    try { await request('/api/auth/logout', { method: 'POST' }); } catch (_) {}
    currentUser = null;
    renderAll();
    window.location.href = '/';
  }

  function authMarkup(user) {
    if (!user) return `<span class="auth-links"><a href="/login">登录</a><a class="auth-create" href="/register">创建账户</a></span>`;
    const image = user.avatar_url ? `<img src="${escapeHtml(user.avatar_url)}" alt="" />` : initials(user);
    const adminLink = user.role === 'ADMIN' ? `<a href="/admin" class="auth-admin-link"><i data-lucide="shield-check"></i>Admin Center</a>` : '';
    return `<details class="notification-menu"><summary title="通知"><i data-lucide="bell"></i><span class="notification-count" hidden>0</span></summary><div class="notification-popover"><div class="notification-head"><b>通知</b><button data-read-all>全部标为已读</button></div><div data-notification-list>正在加载…</div></div></details><details class="auth-menu"><summary><span class="auth-avatar">${image}</span><span class="auth-name">${escapeHtml(user.display_name || user.username)}</span><i data-lucide="chevron-down"></i></summary><div class="auth-popover">${adminLink}<a href="/users/${encodeURIComponent(user.username)}"><i data-lucide="user-round"></i>个人资料</a><a href="/users/${encodeURIComponent(user.username)}#resources"><i data-lucide="folder-kanban"></i>我的资源</a><a href="/publish"><i data-lucide="plus"></i>发布资源</a><a href="#settings" data-settings><i data-lucide="settings"></i>设置</a><hr/><button type="button" data-logout><i data-lucide="log-out"></i>退出登录</button></div></details>`;
  }

  function injectStyle() {
    if (document.querySelector('#openresearch-auth-style')) return;
    const style = document.createElement('style'); style.id = 'openresearch-auth-style';
    style.textContent = `.auth-links{display:flex;align-items:center;gap:8px}.auth-links a{font-size:12px;font-weight:600;text-decoration:none;color:#53616e;padding:8px 10px;border-radius:8px}.auth-links .auth-create{background:#17202a;color:#fff;border:1px solid #17202a}.auth-menu,.notification-menu{position:relative}.auth-menu summary,.notification-menu summary{display:flex;align-items:center;gap:7px;list-style:none;cursor:pointer}.auth-menu summary::-webkit-details-marker,.notification-menu summary::-webkit-details-marker{display:none}.auth-avatar{width:29px;height:29px;border-radius:50%;overflow:hidden;background:#e9eef4;color:#344155;display:grid;place-items:center;font-size:10px;font-weight:800}.auth-avatar img{width:100%;height:100%;object-fit:cover}.auth-name{max-width:104px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;font-weight:700;color:#344155}.auth-menu summary svg,.notification-menu summary svg{width:16px;color:#596775}.notification-menu summary{position:relative;padding:7px}.notification-count{position:absolute;right:0;top:1px;min-width:15px;height:15px;border-radius:8px;background:#d4384e;color:#fff;font:700 9px system-ui;text-align:center;line-height:15px}.auth-popover,.notification-popover{position:absolute;right:0;top:calc(100% + 11px);width:280px;padding:7px;background:#fff;border:1px solid #dfe6eb;border-radius:10px;box-shadow:0 16px 35px rgba(20,35,50,.14);z-index:100}.auth-popover a,.auth-popover button{width:100%;border:0;background:none;display:flex;align-items:center;gap:9px;padding:10px;border-radius:7px;color:#445260;text-decoration:none;font:600 12px system-ui;text-align:left}.auth-popover a:hover,.auth-popover button:hover{background:#f1f5f8;color:#17202a}.auth-popover svg{width:15px}.auth-popover hr{border:0;border-top:1px solid #edf0f2;margin:6px 2px}.notification-head{display:flex;justify-content:space-between;padding:7px 8px}.notification-head button{border:0;background:none;color:#2563eb;font-size:11px}.notification-item{display:block;padding:10px 8px;border-top:1px solid #edf0f2;color:#43515e;font-size:12px}.notification-item b{display:block;color:#1e2933}.notification-item small{color:#85919b}@media(max-width:760px){.auth-name,.auth-menu summary>svg{display:none}.auth-links a{padding:8px 7px;font-size:11px}}`;
    document.head.appendChild(style);
  }

  function mountNav(target) {
    const node = typeof target === 'string' ? document.querySelector(target) : target;
    if (!node) return;
    node.innerHTML = authMarkup(currentUser);
    node.querySelector('[data-logout]')?.addEventListener('click', logout);
    node.querySelector('[data-settings]')?.addEventListener('click', event => { event.preventDefault(); alert('Settings 将在后续账户设置阶段开放。'); });
    const notificationList = node.querySelector('[data-notification-list]');
    async function loadNotifications() { if (!notificationList) return; const response = await request('/api/notifications'); if (!response.ok) return; const data = await response.json(); const count = node.querySelector('.notification-count'); if (count) { count.hidden = !data.unread_count; count.textContent = data.unread_count > 99 ? '99+' : data.unread_count; } notificationList.innerHTML = data.items.length ? data.items.map(item => `<a class="notification-item" href="${escapeHtml(item.target_url || '#')}"><b>${escapeHtml(item.title)}</b><span>${escapeHtml(item.message)}</span><small>${new Date(item.created_at).toLocaleString()}</small></a>`).join('') : '<div class="notification-item">暂无通知。</div>'; }
    node.querySelector('[data-read-all]')?.addEventListener('click', async () => { await request('/api/notifications/read-all', { method: 'POST' }); loadNotifications(); });
    node.querySelector('.notification-menu')?.addEventListener('toggle', event => { if (event.currentTarget.open) loadNotifications(); });
    loadNotifications();
    window.lucide?.createIcons();
  }

  function renderAll() { document.querySelectorAll('[data-auth-nav]').forEach(mountNav); document.dispatchEvent(new CustomEvent('openresearch:authchange', { detail: { user: currentUser } })); }
  function isAuthenticated() { return Boolean(currentUser); }
  function redirectToLogin(message) { const next = encodeURIComponent(location.pathname + location.search); window.location.href = `/login?next=${next}${message ? `&notice=${encodeURIComponent(message)}` : ''}`; }

  function init() { if (initialized) return Promise.resolve(currentUser); initialized = true; injectStyle(); return refreshUser(); }
  window.OpenResearchAuth = { init, request, login, logout, refreshUser, mountNav, redirectToLogin, isAuthenticated, get currentUser() { return currentUser; } };
  document.addEventListener('DOMContentLoaded', init);
})();
