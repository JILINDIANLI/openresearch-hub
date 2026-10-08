(() => {
  const TYPES = [
    ['model', '模型', 'box'], ['dataset', '数据集', 'database'], ['algorithm', '算法', 'braces'],
    ['project', '项目', 'folder-git-2'], ['paper', '论文', 'file-text'], ['demo', '演示', 'play'], ['tutorial', '教程', 'book-open']
  ];
  const iconFor = type => ({model:'box',dataset:'database',algorithm:'braces',project:'folder-git-2',paper:'file-text',demo:'play',tutorial:'book-open'}[type] || 'sparkles');
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const compact = value => Number(value || 0).toLocaleString();
  const params = () => new URLSearchParams(location.search);
  const queryInput = document.querySelector('#queryInput');
  const list = document.querySelector('#resultsList');
  const status = document.querySelector('#status');
  const facets = { research_field: '#fieldFilters', tag: '#tagFilters', framework: '#frameworkFilters', license: '#licenseFilters', year: '#yearFilters' };
  let debounce;
  let lastFacets = {};

  function selected(name) { return params().getAll(name); }
  function setParams(mutator, {replace = false} = {}) { const next = params(); mutator(next); const url = `${location.pathname}${next.toString() ? `?${next}` : ''}`; history[replace ? 'replaceState' : 'pushState']({}, '', url); load(); }
  function removeValue(name, value) { setParams(next => { const rest = next.getAll(name).filter(item => item !== value); next.delete(name); rest.forEach(item => next.append(name, item)); next.delete('page'); }); }
  function toggleValue(name, value, checked) { setParams(next => { const values = next.getAll(name).filter(item => item !== value); if (checked) values.push(value); next.delete(name); values.forEach(item => next.append(name, item)); next.delete('page'); }); }
  function primaryQuery() { return (params().get('q') || '').trim(); }
  function searchUrlFor(name, value) { const next = new URLSearchParams(); next.set(name, value); return `/search?${next}`; }

  function renderChecks(container, name, values, counts = {}) {
    const current = new Set(selected(name).map(value => name === 'type' ? value.toLowerCase() : value));
    document.querySelector(container).innerHTML = values.length ? values.map(([value, label]) => `<label class="check-item"><input type="checkbox" data-filter="${esc(name)}" value="${esc(value)}" ${current.has(String(value)) ? 'checked' : ''}><span>${esc(label)}</span>${counts[String(value).toUpperCase()] !== undefined ? `<small>${counts[String(value).toUpperCase()]}</small>` : ''}</label>`).join('') : '<span class="check-item"><span>暂无选项</span></span>';
  }
  function renderFacets(data) {
    lastFacets = data.facets || {};
    renderChecks('#typeFilters', 'type', TYPES.map(([value, label]) => [value, label]), data.counts || {});
    Object.entries(facets).forEach(([name, container]) => {
      const values = (lastFacets[`${name}s`] || (name === 'research_field' ? lastFacets.research_fields : []) || []).map(value => [String(value), String(value)]);
      renderChecks(container, name, values);
    });
    document.querySelectorAll('[data-filter]').forEach(input => input.addEventListener('change', () => toggleValue(input.dataset.filter, input.value, input.checked)));
  }
  function activeChips() {
    const labels = {type:'类型',tag:'标签',research_field:'研究领域',framework:'框架',license:'许可证',year:'年份'};
    const box = document.querySelector('#activeFilters');
    const all = Object.keys(labels).flatMap(name => selected(name).map(value => [name, value]));
    box.innerHTML = all.map(([name,value]) => `<span class="chip">${esc(labels[name])}: ${esc(value)}<button type="button" data-remove="${esc(name)}" data-value="${esc(value)}" aria-label="移除筛选"><i data-lucide="x"></i></button></span>`).join('');
    box.querySelectorAll('[data-remove]').forEach(button => button.addEventListener('click', () => removeValue(button.dataset.remove, button.dataset.value)));
  }
  function skeletons() { list.innerHTML = Array.from({length:4}, () => '<article class="resource-card skeleton"><div class="sk-line sk-title"></div><div class="sk-line sk-copy"></div><div class="sk-line sk-copy short"></div><div class="sk-line" style="width:43%;margin-top:19px"></div></article>').join(''); }
  function card(item) {
    const author = item.author || {}; const name = author.display_name || author.username || '开放研究中心贡献者';
    const avatar = author.avatar_url ? `<img src="${esc(author.avatar_url)}" alt="">` : esc(name.split(/\s+/).map(part => part[0]).join('').slice(0,2).toUpperCase());
    const updated = item.updated_at || item.updated_time;
    return `<article class="resource-card"><div class="card-top"><span class="type"><i data-lucide="${iconFor(item.resource_type)}"></i>${esc(item.type || item.resource_type)}</span><time class="updated">更新于 ${updated ? new Date(updated).toLocaleDateString('zh-CN') : '—'}</time></div><h2><a href="/resources/${item.id}">${esc(item.title)}</a></h2><p class="description">${esc(item.description)}</p><div class="meta-row"><a class="author" href="${author.username ? `/users/${encodeURIComponent(author.username)}` : '#'}"><span class="avatar">${avatar}</span>${esc(name)}</a>${item.has_showcase ? `<a class="tag showcase-tag" href="/resources/${item.id}/showcase"><i data-lucide="sparkles"></i>科研展示</a>` : ''}${item.research_field ? `<a class="tag" href="${searchUrlFor('research_field', item.research_field)}">${esc(item.research_field)}</a>` : ''}${(item.tags || []).slice(0,5).map(tag => `<a class="tag" href="${searchUrlFor('tag', tag.name)}">${esc(tag.name)}</a>`).join('')}</div><div class="metrics"><span><i data-lucide="star"></i>${compact(item.stars_count ?? item.stars)}</span><span><i data-lucide="download"></i>${compact(item.downloads_count ?? item.downloads)}</span><span><i data-lucide="eye"></i>${compact(item.views_count ?? item.views)}</span></div></article>`;
  }
  function noResults() { list.innerHTML = '<section class="empty"><i data-lucide="search-x"></i><h2>未找到资源。</h2><p>请尝试更换关键词、移除筛选条件，或搜索其他研究领域。</p><ul><li>使用更短的关键词</li><li>尝试相关标签或框架</li><li>清除一个或多个筛选条件</li></ul></section>'; }
  function pagination(data) {
    const target = document.querySelector('#pagination');
    if (data.total_pages <= 1) { target.innerHTML = ''; return; }
    const pages = [...new Set([1, data.page - 1, data.page, data.page + 1, data.total_pages].filter(page => page >= 1 && page <= data.total_pages))];
    target.innerHTML = `<button data-page="${data.page - 1}" ${data.page === 1 ? 'disabled' : ''} aria-label="Previous page"><i data-lucide="chevron-left"></i></button>${pages.map(page => `<button data-page="${page}" class="${page === data.page ? 'active' : ''}">${page}</button>`).join('')}<button data-page="${data.page + 1}" ${data.page === data.total_pages ? 'disabled' : ''} aria-label="Next page"><i data-lucide="chevron-right"></i></button>`;
    target.querySelectorAll('[data-page]').forEach(button => button.addEventListener('click', () => setParams(next => next.set('page', button.dataset.page))));
  }
  function buildApiParams() {
    const source = params(); const result = new URLSearchParams();
    ['q','type','tag','research_field','framework','license','author','year','sort','page','page_size'].forEach(name => source.getAll(name).forEach(value => result.append(name, value)));
    if (!result.get('page')) result.set('page', '1');
    if (!result.get('page_size')) result.set('page_size', '20');
    return result;
  }
  async function load() {
    const q = primaryQuery(); queryInput.value = q; document.querySelector('#sortSelect').value = params().get('sort') || (q ? 'relevance' : 'newest');
    document.querySelector('#title').textContent = q ? `“${q}”的搜索结果` : '浏览研究资源';
    document.querySelector('#summary').textContent = q ? '来自开放研究中心公开资源的搜索结果。' : '浏览并筛选公开研究资源目录。';
    activeChips(); skeletons(); status.textContent = '正在搜索公开资源…'; document.querySelector('#pagination').innerHTML = '';
    try {
      const response = await OpenResearchAuth.request(`/api/search?${buildApiParams()}`);
      if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || '搜索服务暂不可用。');
      const data = await response.json(); renderFacets(data); activeChips();
      status.innerHTML = `找到 <strong>${data.total.toLocaleString()}</strong> 个资源${q ? `，关键词为“${esc(q)}”` : ''}`;
      if (data.items.length) list.innerHTML = data.items.map(card).join(''); else noResults();
      pagination(data); window.lucide?.createIcons();
    } catch (error) {
      status.textContent = '';
      list.innerHTML = `<section class="error"><i data-lucide="cloud-off"></i><h2>无法加载搜索结果。</h2><p>${esc(error.message)}</p><button class="retry" type="button" id="retry">重试</button></section>`;
      document.querySelector('#retry')?.addEventListener('click', load); window.lucide?.createIcons();
    }
  }
  async function showSuggestions(value) {
    const menu = document.querySelector('#suggestions');
    const q = value.trim();
    if (!q) { menu.hidden = true; return; }
    try {
      const response = await fetch(`/api/search/suggestions?q=${encodeURIComponent(q)}`); const data = response.ok ? await response.json() : [];
      if (!data.length) { menu.hidden = true; return; }
      menu.innerHTML = `<div class="suggestion-label">搜索建议</div>${data.map(item => `<button class="suggestion" type="button" data-kind="${item.kind}" data-id="${item.resource_id || ''}" data-label="${esc(item.label)}"><span class="icon"><i data-lucide="${item.kind === 'resource' ? iconFor(item.resource_type) : item.kind === 'tag' ? 'tag' : 'layers-3'}"></i></span><b>${esc(item.label)}</b><small>${item.kind === 'resource' ? ({model:'模型',dataset:'数据集',algorithm:'算法',project:'项目',paper:'论文',demo:'演示',tutorial:'教程'}[item.resource_type] || '资源') : item.kind === 'tag' ? '标签' : '研究领域'}</small></button>`).join('')}`;
      menu.hidden = false; menu.querySelectorAll('.suggestion').forEach(button => button.addEventListener('click', () => { if (button.dataset.kind === 'resource') location.href = `/resources/${button.dataset.id}`; else { const key = button.dataset.kind === 'tag' ? 'tag' : 'research_field'; location.href = `/search?${new URLSearchParams([[key, button.dataset.label]])}`; } })); window.lucide?.createIcons();
    } catch (_) { menu.hidden = true; }
  }
  document.querySelector('#globalSearch').addEventListener('submit', event => { event.preventDefault(); setParams(next => { const q = queryInput.value.trim(); q ? next.set('q', q) : next.delete('q'); next.delete('page'); }); document.querySelector('#suggestions').hidden = true; });
  queryInput.addEventListener('input', () => { clearTimeout(debounce); debounce = setTimeout(() => showSuggestions(queryInput.value), 180); });
  queryInput.addEventListener('blur', () => setTimeout(() => { document.querySelector('#suggestions').hidden = true; }, 120));
  document.querySelector('#sortSelect').addEventListener('change', event => setParams(next => { next.set('sort', event.target.value); next.delete('page'); }));
  document.querySelector('#clearFilters').addEventListener('click', () => setParams(next => { ['type','tag','research_field','framework','license','year','author','sort','page'].forEach(key => next.delete(key)); }));
  window.addEventListener('popstate', load);
  document.addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); queryInput.focus(); queryInput.select(); } });
  OpenResearchAuth.init().finally(load);
  window.lucide?.createIcons();
})();
