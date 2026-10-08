const fallbackProjects = [
  { title: '园区无人机智能巡检', summary: '面向园区设施巡检的自主飞行、缺陷识别与报告生成方案。', category: 'robotics', owner: '周思远', date: '2026.09', code: 'https://github.com/', video: 'https://www.youtube.com/', icon: 'drone' },
  { title: '工业视觉缺陷检测平台', summary: '将多模型检测能力封装为可配置的产线质检服务，缩短上线周期。', category: 'ai', owner: '陈卓', date: '2026.08', code: 'https://github.com/', video: 'https://www.youtube.com/', icon: 'scan-eye' },
  { title: '客户交付项目看板', summary: '从启动到验收统一追踪里程碑、风险与关键交付物。', category: 'delivery', owner: '孟然', date: '2026.08', code: 'https://github.com/', video: 'https://www.youtube.com/', icon: 'kanban-square' },
  { title: '设备远程运维中台', summary: '统一接入设备状态、告警与远程诊断记录，让问题可追溯。', category: 'platform', owner: '罗颖', date: '2026.07', code: 'https://github.com/', video: 'https://www.youtube.com/', icon: 'monitor-cog' },
  { title: '多传感器融合定位', summary: '针对复杂环境的视觉、惯导和里程计融合定位验证。', category: 'ai', owner: '李扬', date: '2026.07', code: 'https://github.com/', video: 'https://www.youtube.com/', icon: 'map-pinned' },
  { title: '巡检任务智能调度', summary: '根据设备优先级、天气与航线约束自动生成巡检计划。', category: 'platform', owner: '黄蓉', date: '2026.06', code: 'https://github.com/', video: 'https://www.youtube.com/', icon: 'route' }
];
let projects = [];
const names = { ai: '人工智能', robotics: '智能硬件', platform: '软件平台', delivery: '行业应用' };
const grid = document.querySelector('#projectGrid');
let activeCategory = 'all';

function renderProjects() {
  const search = document.querySelector('#projectSearch').value.trim().toLowerCase();
  const visible = projects.filter((p) => p.isPublic !== false && (activeCategory === 'all' || p.category === activeCategory) && (`${p.title} ${p.summary} ${names[p.category]}`).toLowerCase().includes(search));
  grid.innerHTML = visible.map((p) => `<article class="project-card" data-index="${projects.indexOf(p)}"><div class="card-banner tone-${p.category}"><i data-lucide="${p.icon}"></i><span>${names[p.category]}</span></div><div class="card-body"><h3>${p.title}</h3><p>${p.summary}</p><div class="card-meta"><span><i data-lucide="user-round"></i>${p.owner}</span><span>${p.date}</span></div></div></article>`).join('') || '<p style="color:#7b858d;font-size:13px">没有找到匹配项目。</p>';
  document.querySelector('#resultCount').textContent = `${visible.length} 个项目`;
  document.querySelector('#projectCount').textContent = projects.filter((p) => p.isPublic !== false).length;
  lucide.createIcons();
}
async function loadProjects() {
  try {
    const response = await fetch('http://127.0.0.1:8000/api/projects?public_only=false');
    if (!response.ok) throw new Error('API unavailable');
    projects = await response.json();
    projects = projects.map((project) => ({ ...project, isPublic: project.is_public, code: project.code_url, video: project.video_url, codeFile: project.code_file, videoFile: project.video_file, date: project.updated_at?.slice(0, 7).replace('-', '.') || '刚刚', icon: project.category === 'ai' ? 'scan-eye' : project.category === 'robotics' ? 'drone' : project.category === 'platform' ? 'monitor-cog' : 'kanban-square' }));
  } catch (error) {
    projects = fallbackProjects;
    console.warn('后端暂不可用，使用演示数据', error);
  }
  renderProjects();
}
function showView(view) {
  document.querySelector('#publicView').classList.toggle('hidden', view !== 'public');
  document.querySelector('#internalView').classList.toggle('hidden', view !== 'internal');
  document.querySelectorAll('[data-view]').forEach((button) => button.classList.toggle('active', button.dataset.view === view));
  if (view === 'internal') renderMyProjects();
}
function renderMyProjects() {
  document.querySelector('#myProjects').innerHTML = projects.slice(-3).reverse().map((p) => `<div class="my-project"><span class="project-symbol tone-${p.category}"><i data-lucide="${p.icon}"></i></span><span class="my-project-main"><b>${p.title}</b><small>${names[p.category]} · ${p.date}</small></span><span class="status">${p.isPublic === false ? '内部草稿' : '已发布'}</span></div>`).join('');
  lucide.createIcons();
}
function openDetail(project) {
  document.querySelector('#detailBanner').className = `detail-banner tone-${project.category}`;
  document.querySelector('#detailCategory').textContent = names[project.category];
  document.querySelector('#detailTitle').textContent = project.title;
  document.querySelector('#detailSummary').textContent = project.summary;
  document.querySelector('#detailOwner').textContent = project.owner;
  document.querySelector('#detailDate').textContent = project.date;
  [['#detailCode', project.code, project.codeFile, '#detailCodeNote'], ['#detailVideo', project.video, project.videoFile, '#detailVideoNote']].forEach(([selector, href, fileName, noteSelector]) => { const item = document.querySelector(selector); const available = href || fileName; item.href = href || '#'; item.style.opacity = available ? '1' : '.45'; item.style.pointerEvents = href ? 'auto' : 'none'; document.querySelector(noteSelector).textContent = fileName ? `已上传：${fileName}` : (href ? '查看链接中的项目资料' : '暂未提供'); });
  document.querySelector('#detailDialog').showModal();
  lucide.createIcons();
}
document.querySelector('#categories').addEventListener('click', (event) => { const button = event.target.closest('button'); if (!button) return; activeCategory = button.dataset.category; document.querySelectorAll('#categories button').forEach((b) => b.classList.toggle('active', b === button)); renderProjects(); });
document.querySelector('#projectSearch').addEventListener('input', renderProjects);
grid.addEventListener('click', (event) => { const card = event.target.closest('.project-card'); if (card) openDetail(projects[card.dataset.index]); });
document.querySelectorAll('[data-view]').forEach((button) => button.addEventListener('click', () => showView(button.dataset.view)));
const dialog = document.querySelector('#projectDialog');
document.querySelectorAll('#shareProject,#newProject').forEach((button) => button.addEventListener('click', () => dialog.showModal()));
document.querySelector('#closeDialog').addEventListener('click', () => dialog.close());
document.querySelector('#cancelDialog').addEventListener('click', () => dialog.close());
document.querySelector('#closeDetail').addEventListener('click', () => document.querySelector('#detailDialog').close());
[['#codeFileInput', '#codeFileName'], ['#videoFileInput', '#videoFileName']].forEach(([inputSelector, labelSelector]) => document.querySelector(inputSelector).addEventListener('change', (event) => { document.querySelector(labelSelector).textContent = event.target.files[0]?.name || '未选择文件'; }));
document.querySelector('#projectForm').addEventListener('submit', (event) => {
  event.preventDefault(); const get = (id) => document.querySelector(id).value.trim();
  const isPublic = document.querySelector('#publishInput').checked;
  const body = new FormData();
  body.append('title', get('#titleInput')); body.append('summary', get('#summaryInput')); body.append('category', get('#categoryInput')); body.append('owner', get('#ownerInput')); body.append('code_url', get('#codeInput')); body.append('video_url', get('#videoInput')); body.append('is_public', String(isPublic));
  const codeFile = document.querySelector('#codeFileInput').files[0]; const videoFile = document.querySelector('#videoFileInput').files[0];
  if (codeFile) body.append('code_file', codeFile); if (videoFile) body.append('video_file', videoFile);
  fetch('http://127.0.0.1:8000/api/projects', { method: 'POST', body }).then((response) => { if (!response.ok) throw new Error('项目保存失败'); return response.json(); }).then(() => { dialog.close(); event.target.reset(); document.querySelector('#codeFileName').textContent = '未选择文件'; document.querySelector('#videoFileName').textContent = '未选择文件'; return loadProjects(); }).then(() => showView(isPublic ? 'public' : 'internal')).catch((error) => { console.error(error); alert('项目保存失败，请确认后端服务已启动。'); });
});
loadProjects();
