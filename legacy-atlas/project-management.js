let editingProjectId = null;

const projectStatuses = {
  draft: '草稿',
  pending_review: '待审核',
  published: '已发布',
  archived: '已归档',
};

function apiRequest(path, options) {
  return fetch(path, options).then(async (response) => {
    if (!response.ok) throw new Error(await response.text());
    return response.status === 204 ? null : response.json();
  });
}

function decorateProject(project) {
  return {
    ...project,
    status: project.status || (project.is_public ? 'published' : 'draft'),
    isPublic: project.is_public ?? project.status === 'published',
    code: project.code_url,
    video: project.video_url,
    codeFile: project.code_file,
    videoFile: project.video_file,
    date: project.updated_at?.slice(0, 10) || '刚刚',
    icon: project.category === 'ai' ? 'scan-eye' : project.category === 'robotics' ? 'drone' : project.category === 'platform' ? 'monitor-cog' : 'kanban-square',
  };
}

renderProjects = function renderManagedProjects() {
  const search = document.querySelector('#projectSearch').value.trim().toLowerCase();
  const visible = projects.filter((project) => project.status === 'published' && (activeCategory === 'all' || project.category === activeCategory) && (`${project.title} ${project.summary} ${names[project.category]} ${project.tags || ''}`).toLowerCase().includes(search));
  grid.innerHTML = visible.map((project) => `<article class="project-card" data-index="${projects.indexOf(project)}"><div class="card-banner tone-${project.category}"><i data-lucide="${project.icon}"></i><span>${names[project.category]}</span></div><div class="card-body"><h3>${project.title}</h3><p>${project.summary}</p><div class="card-meta"><span><i data-lucide="user-round"></i>${project.owner}</span><span>${project.version || 'v1.0'}</span></div></div></article>`).join('') || '<p class="empty-state">没有找到匹配项目。</p>';
  document.querySelector('#resultCount').textContent = `${visible.length} 个项目`;
  document.querySelector('#projectCount').textContent = visible.length;
  lucide.createIcons();
};

renderMyProjects = function renderManagedProjects() {
  const list = document.querySelector('#myProjects');
  list.innerHTML = projects.slice().reverse().map((project) => `<div class="my-project"><span class="project-symbol tone-${project.category}"><i data-lucide="${project.icon}"></i></span><span class="my-project-main"><b>${project.title}</b><small>${names[project.category]} · ${project.version || 'v1.0'} · ${project.date}</small></span><span class="status status-${project.status}">${projectStatuses[project.status]}</span><span class="project-actions"><button data-action="edit" data-id="${project.id}" title="编辑"><i data-lucide="pencil"></i></button>${project.status === 'draft' ? `<button data-action="submit" data-id="${project.id}" title="提交审核"><i data-lucide="send"></i></button>` : ''}${project.status === 'pending_review' ? `<button data-action="publish" data-id="${project.id}" title="发布项目"><i data-lucide="badge-check"></i></button>` : ''}${project.status === 'published' ? `<button data-action="archive" data-id="${project.id}" title="归档"><i data-lucide="archive"></i></button>` : ''}<button data-action="delete" data-id="${project.id}" title="删除"><i data-lucide="trash-2"></i></button></span></div>`).join('') || '<p class="empty-state">还没有项目，先分享第一个成果吧。</p>';
  lucide.createIcons();
};

loadProjects = async function loadManagedProjects() {
  try {
    const response = await apiRequest('/api/projects?public_only=false');
    projects = response.map(decorateProject);
  } catch (error) {
    projects = fallbackProjects.map(decorateProject);
    console.warn('后端暂不可用，使用演示数据', error);
  }
  renderProjects();
  renderMyProjects();
};

const originalOpenDetail = openDetail;
openDetail = function openManagedDetail(project) {
  originalOpenDetail(project);
  document.querySelector('#detailSummary').textContent = project.description || project.summary;
  document.querySelector('.release-pill').innerHTML = `<i data-lucide="git-branch"></i> ${project.version || 'v1.0'} · ${projectStatuses[project.status] || '已验证'}`;
  lucide.createIcons();
};

function resetProjectForm() {
  document.querySelector('#projectForm').reset();
  document.querySelector('#versionInput').value = 'v1.0';
  document.querySelector('#codeFileName').textContent = '未选择文件';
  document.querySelector('#videoFileName').textContent = '未选择文件';
  document.querySelector('#formTitle').textContent = '分享一个项目';
  document.querySelector('#formSubtitle').textContent = '填写核心信息，项目页就有了可靠的第一版。';
  document.querySelector('#saveProject').textContent = '保存项目';
  document.querySelector('#publishLine').style.display = '';
  editingProjectId = null;
}

function editProject(project) {
  resetProjectForm();
  editingProjectId = project.id;
  document.querySelector('#formTitle').textContent = '编辑项目';
  document.querySelector('#formSubtitle').textContent = '更新项目说明、资源和版本信息。';
  document.querySelector('#saveProject').textContent = '保存修改';
  document.querySelector('#publishLine').style.display = 'none';
  document.querySelector('#titleInput').value = project.title;
  document.querySelector('#summaryInput').value = project.summary;
  document.querySelector('#descriptionInput').value = project.description || '';
  document.querySelector('#categoryInput').value = project.category;
  document.querySelector('#ownerInput').value = project.owner;
  document.querySelector('#versionInput').value = project.version || 'v1.0';
  document.querySelector('#tagsInput').value = project.tags || '';
  document.querySelector('#codeInput').value = project.code || '';
  document.querySelector('#videoInput').value = project.video || '';
  dialog.showModal();
}

document.querySelectorAll('#shareProject,#newProject').forEach((button) => button.addEventListener('click', resetProjectForm));
document.querySelector('#myProjects').addEventListener('click', async (event) => {
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const project = projects.find((item) => item.id === button.dataset.id);
  if (!project) return;
  if (button.dataset.action === 'edit') return editProject(project);
  if (button.dataset.action === 'delete') {
    if (!confirm(`确认删除“${project.title}”吗？`)) return;
    await apiRequest(`/api/projects/${project.id}`, { method: 'DELETE' });
  } else {
    const status = { submit: 'pending_review', publish: 'published', archive: 'archived' }[button.dataset.action];
    const body = new FormData();
    body.append('status', status);
    await apiRequest(`/api/projects/${project.id}/status`, { method: 'POST', body });
  }
  await loadProjects();
});

document.querySelector('#projectForm').addEventListener('submit', async (event) => {
  if (!editingProjectId) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  const value = (selector) => document.querySelector(selector).value.trim();
  const body = new FormData();
  [['title', '#titleInput'], ['summary', '#summaryInput'], ['description', '#descriptionInput'], ['category', '#categoryInput'], ['owner', '#ownerInput'], ['version', '#versionInput'], ['tags', '#tagsInput'], ['code_url', '#codeInput'], ['video_url', '#videoInput']].forEach(([key, selector]) => body.append(key, value(selector)));
  try {
    await apiRequest(`/api/projects/${editingProjectId}`, { method: 'PUT', body });
    dialog.close();
    await loadProjects();
  } catch (error) {
    console.error(error);
    alert('项目保存失败，请确认后端服务正在运行。');
  }
}, true);

loadProjects();
