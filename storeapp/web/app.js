'use strict';

/* ================================================================
   StoreApp 前端逻辑（原生 JS，无构建依赖）
   数据交换：pywebview js_api —— call(name, ...args) -> Promise
   ================================================================ */

/* ------------------------------------------------ pywebview 桥接 */

const bridge = new Promise((resolve) => {
  if (window.pywebview && window.pywebview.api) {
    resolve(window.pywebview.api);
  } else {
    window.addEventListener('pywebviewready', () => resolve(window.pywebview.api), { once: true });
  }
});

async function call(name, ...args) {
  const api = await bridge;
  return api[name](...args);
}

/* ------------------------------------------------ 常量与状态 */

const UNGROUPED = -1;

const AVATAR_COLORS = [
  '#6366F1', '#0EA5E9', '#10B981', '#F59E0B',
  '#EF4444', '#8B5CF6', '#EC4899', '#14B8A6',
];

const state = {
  groups: [],
  records: [],
  selectedGroupId: null,     // null=全部, -1=未分组, >0=分组 ID
  selectedRecordId: null,
  keyword: '',
  showSecrets: localStorage.getItem('storeapp.showSecrets') === '1',
  secretOverrides: new Map(),   // 单条卡片的眼睛切换
  dbPath: '',
  version: '',
};

/* ------------------------------------------------ 小工具 */

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function groupOf(record) {
  if (!record.group_id) return null;
  return state.groups.find((g) => g.id === record.group_id) || null;
}

function colorFor(key) {
  let h = 0;
  for (let i = 0; i < key.length; i += 1) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}

function matches(record) {
  const k = state.keyword.trim().toLowerCase();
  if (!k) return true;
  const g = groupOf(record);
  const hay = [
    record.name, record.username, record.url, record.note,
    record.tags.join(','), g ? g.name : '未分组',
  ].join('\n').toLowerCase();
  return hay.includes(k);
}

function visibleRecords() {
  const matched = state.records.filter(matches);
  if (state.keyword.trim()) return matched;
  const gid = state.selectedGroupId;
  if (gid === null) return matched;
  if (gid === UNGROUPED) return matched.filter((r) => !r.group_id);
  return matched.filter((r) => r.group_id === gid);
}

function isSecretVisible(record) {
  if (state.secretOverrides.has(record.id)) return state.secretOverrides.get(record.id);
  return state.showSecrets;
}

function applySnapshot(data) {
  state.groups = data.groups || [];
  state.records = data.records || [];
  state.dbPath = data.db_path || '';
  state.version = data.version || '';
  if (state.selectedGroupId !== null && state.selectedGroupId !== UNGROUPED
      && !state.groups.some((g) => g.id === state.selectedGroupId)) {
    state.selectedGroupId = null;
  }
  if (state.selectedRecordId
      && !state.records.some((r) => r.id === state.selectedRecordId)) {
    state.selectedRecordId = null;
  }
  renderAll();
}

/* ------------------------------------------------ Toast */

let toastTimer = null;
function toast(message, isError = false) {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.classList.toggle('error', isError);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2600);
}

/* ------------------------------------------------ 图标 */

const ICON = {
  copy: (s = 14) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="8" width="14" height="14" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`,
  check: (s = 14) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`,
  pencil: (s = 14) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/></svg>`,
  trash: (s = 14) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>`,
  eye: (s = 14) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>`,
  eyeOff: (s = 14) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c6.5 0 10 8 10 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><path d="M6.61 6.61A18.15 18.15 0 0 0 2 12s3.5 8 10 8a9.12 9.12 0 0 0 5.39-1.61"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><path d="m2 2 20 20"/></svg>`,
  key: (s = 64) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="7.5" cy="15.5" r="4.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/></svg>`,
  searchBig: (s = 64) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>`,
  x: (s = 14) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`,
};

/* ------------------------------------------------ 渲染：边栏 */

function renderSidebar() {
  const list = document.getElementById('group-list');
  const searching = !!state.keyword.trim();
  const matched = state.records.filter(matches);

  const counts = { all: matched.length, ungrouped: 0, groups: {} };
  matched.forEach((r) => {
    if (r.group_id) counts.groups[r.group_id] = (counts.groups[r.group_id] || 0) + 1;
    else counts.ungrouped += 1;
  });

  const item = (id, label, count, custom) => {
    const active = state.selectedGroupId === id ? ' active' : '';
    const cls = `group-item${custom ? ' custom' : ''}${active}`;
    const actions = custom
      ? `<span class="group-actions">
           <button class="g-mini-btn" data-g-action="rename" data-g-id="${id}" title="重命名">${ICON.pencil(13)}</button>
           <button class="g-mini-btn danger" data-g-action="delete" data-g-id="${id}" title="删除分组">${ICON.trash(13)}</button>
         </span>`
      : '';
    return `<div class="${cls}" data-g-id="${id}" role="button" tabindex="0">
              <span class="g-name">${esc(label)}</span>
              <span class="badge">${count}</span>${actions}
            </div>`;
  };

  let html = item(null, '全部记录', counts.all, false);
  html += item(UNGROUPED, '未分组', counts.ungrouped, false);
  if (state.groups.length) html += '<div class="group-divider"></div>';
  state.groups.forEach((g) => {
    html += item(g.id, g.name, counts.groups[g.id] || 0, true);
  });
  list.innerHTML = html;
}

/* ------------------------------------------------ 渲染：工具栏 / 标题 */

function renderToolbar() {
  const title = document.getElementById('view-title');
  const count = document.getElementById('view-count');
  const list = visibleRecords();

  if (state.keyword.trim()) {
    title.textContent = `搜索“${state.keyword.trim()}”`;
    count.textContent = `找到 ${list.length} 条（全部分组）`;
  } else if (state.selectedGroupId === null) {
    title.textContent = '全部记录';
    count.textContent = `${list.length} 条`;
  } else if (state.selectedGroupId === UNGROUPED) {
    title.textContent = '未分组';
    count.textContent = `${list.length} 条`;
  } else {
    const g = state.groups.find((x) => x.id === state.selectedGroupId);
    title.textContent = g ? g.name : '全部记录';
    count.textContent = `${list.length} 条`;
  }

  const hasSel = !!state.selectedRecordId;
  document.getElementById('edit-btn').disabled = !hasSel;
  document.getElementById('delete-btn').disabled = !hasSel;
}

/* ------------------------------------------------ 渲染：卡片列表 */

function cardHtml(record) {
  const group = groupOf(record);
  const groupName = group ? group.name : '未分组';
  const letter = groupName.trim().charAt(0) || '?';
  const color = colorFor(groupName);
  const visible = isSecretVisible(record);

  let secretHtml;
  if (!record.secret) {
    secretHtml = '<span class="secret-empty">未设置密钥</span>';
  } else if (visible) {
    secretHtml = `<span class="secret-text">${esc(record.secret)}</span>`;
  } else {
    secretHtml = `<span class="secret-dots">${'•'.repeat(Math.min(record.secret.length, 18))}</span>`;
  }

  const tagsHtml = record.tags
    .map((t) => `<span class="tag">${esc(t)}</span>`).join('');

  const selected = state.selectedRecordId === record.id ? ' selected' : '';

  return `<div class="card${selected}" data-rec-id="${record.id}">
    <span class="avatar" style="background:${color}" title="分组：${esc(groupName)}">${esc(letter)}</span>
    <div class="card-main">
      <div class="card-name">${esc(record.name)}</div>
      <div class="card-sub">
        <span class="card-account" title="${esc(record.username || '')}">${esc(record.username || '—')}</span>
        <button class="mini-copy" data-action="copy-user" data-id="${record.id}" title="复制账号">${ICON.copy(13)}</button>
        ${tagsHtml}
      </div>
      <div class="card-secret">
        ${secretHtml}
        ${record.secret ? `<button class="icon-btn reveal-btn" data-action="reveal" data-id="${record.id}" title="${visible ? '隐藏密钥' : '显示密钥'}">${visible ? ICON.eye(14) : ICON.eyeOff(14)}</button>` : ''}
      </div>
    </div>
    <div class="card-actions">
      <button class="act-btn" data-action="copy" data-id="${record.id}">${ICON.copy(14)}<span>复制</span></button>
      <button class="act-btn" data-action="edit" data-id="${record.id}" title="编辑">${ICON.pencil(14)}</button>
      <button class="act-btn danger" data-action="delete" data-id="${record.id}" title="删除">${ICON.trash(14)}</button>
    </div>
  </div>`;
}

function renderList() {
  const listEl = document.getElementById('record-list');
  const emptyEl = document.getElementById('empty');
  const records = visibleRecords();

  if (!records.length) {
    listEl.innerHTML = '';
    emptyEl.hidden = false;
    if (state.keyword.trim()) {
      emptyEl.innerHTML = `${ICON.searchBig(56)}
        <h3>没有找到匹配的记录</h3>
        <p>换个关键词，或按 Esc 清除搜索</p>`;
    } else {
      emptyEl.innerHTML = `${ICON.key(64)}
        <h3>${state.selectedGroupId === null ? '还没有记录' : '这个分组还没有记录'}</h3>
        <p>点击「新增记录」保存你的第一个 API Key</p>
        <button class="btn btn-primary" data-action="new-empty">＋ 新增记录</button>`;
    }
    return;
  }

  emptyEl.hidden = true;
  listEl.innerHTML = records.map(cardHtml).join('');
}

function renderAll() {
  renderSidebar();
  renderToolbar();
  renderList();
  syncSettingsUi();
}

/* ------------------------------------------------ 通用弹窗 */

function modal(html, { onMount, dismissible = true } = {}) {
  return new Promise((resolve) => {
    const root = document.getElementById('modal-root');
    const overlay = document.createElement('div');
    overlay.className = 'overlay';
    overlay.innerHTML = `<div class="modal" role="dialog">${html}</div>`;
    root.appendChild(overlay);

    let done = false;
    function close(value) {
      if (done) return;
      done = true;
      document.removeEventListener('keydown', onKey, true);
      overlay.remove();
      resolve(value);
    }
    function onKey(e) {
      if (e.key === 'Escape') { e.stopPropagation(); e.preventDefault(); close(null); }
    }
    document.addEventListener('keydown', onKey, true);
    if (dismissible) {
      overlay.addEventListener('mousedown', (e) => { if (e.target === overlay) close(null); });
    }
    onMount && onMount(overlay.querySelector('.modal'), close);
  });
}

/* 记录表单 */
function modalRecord(record) {
  const defaultGroup = record
    ? (record.group_id || null)
    : (state.selectedGroupId > 0 ? state.selectedGroupId : null);

  const groupOptions = [{ id: null, name: '未分组' }, ...state.groups]
    .map((g) => `<option value="${g.id == null ? '' : g.id}" ${ (defaultGroup == null ? g.id == null : g.id === defaultGroup) ? 'selected' : ''}>${esc(g.name)}</option>`)
    .join('');

  const isEdit = !!record;
  const html = `
    <div class="modal-title">${isEdit ? '编辑记录' : '新增记录'}</div>
    <div class="modal-desc">${isEdit ? '修改这条记录的内容。' : '保存一条新的密钥或密码。'}</div>
    <form id="rec-form">
      <div class="field-row">
        <div class="field">
          <label>名称 *</label>
          <input class="input" name="name" value="${esc(record ? record.name : '')}" placeholder="如 OpenAI" required>
        </div>
        <div class="field">
          <label>分组</label>
          <select class="select" name="group_id">${groupOptions}</select>
        </div>
      </div>
      <div class="field">
        <label>账号 / 用户名</label>
        <input class="input" name="username" value="${esc(record ? record.username : '')}" placeholder="可选">
      </div>
      <div class="field">
        <label>密钥 / 密码</label>
        <div class="input-wrap">
          <input class="input" name="secret" type="password" value="${esc(record ? record.secret : '')}" placeholder="sk-…" style="font-family:ui-monospace,Menlo,Consolas,monospace">
          <button type="button" class="input-eye" data-eye title="显示/隐藏">${ICON.eye(15)}</button>
        </div>
      </div>
      <div class="field">
        <label>标签</label>
        <input class="input" name="tags" value="${esc(record ? record.tags.join(', ') : '')}" placeholder="openai, 付费（逗号分隔）">
      </div>
      <div class="field">
        <label>网址</label>
        <input class="input" name="url" value="${esc(record ? record.url : '')}" placeholder="可选">
      </div>
      <div class="field">
        <label>备注</label>
        <textarea class="textarea" name="note" placeholder="可选">${esc(record ? record.note : '')}</textarea>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-ghost" data-cancel>取消</button>
        <button type="submit" class="btn btn-primary">保存</button>
      </div>
    </form>`;

  return modal(html, {
    onMount(el, close) {
      const form = el.querySelector('#rec-form');
      const nameInput = form.elements.name;
      nameInput.focus();
      nameInput.select();

      el.querySelector('[data-cancel]').onclick = () => close(null);
      const eye = el.querySelector('[data-eye]');
      eye.onclick = () => {
        const inp = form.elements.secret;
        const showing = inp.type === 'text';
        inp.type = showing ? 'password' : 'text';
        eye.innerHTML = showing ? ICON.eye(15) : ICON.eyeOff(15);
      };

      form.onsubmit = (e) => {
        e.preventDefault();
        const name = nameInput.value.trim();
        if (!name) { nameInput.focus(); return; }
        const gid = form.elements.group_id.value;
        const tags = form.elements.tags.value
          .split(/[,，;；、]/).map((t) => t.trim()).filter(Boolean);
        const unique = [...new Set(tags)];
        close({
          name,
          group_id: gid ? Number(gid) : null,
          username: form.elements.username.value.trim(),
          secret: form.elements.secret.value,
          tags: unique.join(','),
          url: form.elements.url.value.trim(),
          note: form.elements.note.value.replace(/\s+$/, ''),
        });
      };
    },
  });
}

/* 分组名输入 */
function modalGroupName(title, initial = '') {
  const html = `
    <div class="modal-title">${esc(title)}</div>
    <form id="g-form">
      <div class="field">
        <label>分组名称</label>
        <input class="input" name="name" value="${esc(initial)}" placeholder="如 大模型 API" required>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-ghost" data-cancel>取消</button>
        <button type="submit" class="btn btn-primary">确定</button>
      </div>
    </form>`;
  return modal(html, {
    onMount(el, close) {
      const form = el.querySelector('#g-form');
      const input = form.elements.name;
      input.focus();
      input.select();
      el.querySelector('[data-cancel]').onclick = () => close(null);
      form.onsubmit = (e) => {
        e.preventDefault();
        const v = input.value.trim();
        if (v) close(v);
      };
    },
  });
}

/* 确认框 */
function modalConfirm(title, descHtml, dangerLabel = '确定') {
  const html = `
    <div class="modal-title">${esc(title)}</div>
    <div class="modal-desc">${descHtml}</div>
    <div class="modal-footer">
      <button class="btn btn-ghost" data-cancel>取消</button>
      <button class="btn ${dangerLabel === '取消' ? 'btn-primary' : 'btn-danger'}" data-ok>${esc(dangerLabel)}</button>
    </div>`;
  return modal(html, {
    onMount(el, close) {
      el.querySelector('[data-cancel]').onclick = () => close(false);
      el.querySelector('[data-ok]').onclick = () => close(true);
      el.querySelector('[data-ok]').focus();
    },
  });
}

/* 备份密码输入 */
function modalPassword({ title, desc, confirm }) {
  const html = `
    <div class="modal-title">${esc(title)}</div>
    <div class="modal-desc">${desc}</div>
    <form id="p-form">
      <div class="field">
        <label>密码</label>
        <div class="input-wrap">
          <input class="input" name="pwd" type="password" placeholder="至少 6 位" autocomplete="new-password">
          <button type="button" class="input-eye" data-eye>${ICON.eye(15)}</button>
        </div>
      </div>
      ${confirm ? `
      <div class="field">
        <label>确认密码</label>
        <input class="input" name="pwd2" type="password" placeholder="再输入一次" autocomplete="new-password">
      </div>` : ''}
      <div class="modal-footer">
        <button type="button" class="btn btn-ghost" data-cancel>取消</button>
        <button type="submit" class="btn btn-primary">确定</button>
      </div>
    </form>`;
  return modal(html, {
    onMount(el, close) {
      const form = el.querySelector('#p-form');
      form.elements.pwd.focus();
      el.querySelector('[data-cancel]').onclick = () => close(null);
      const eye = el.querySelector('[data-eye]');
      eye.onclick = () => {
        const showing = form.elements.pwd.type === 'text';
        form.elements.pwd.type = showing ? 'password' : 'text';
        eye.innerHTML = showing ? ICON.eye(15) : ICON.eyeOff(15);
      };
      form.onsubmit = (e) => {
        e.preventDefault();
        const pwd = form.elements.pwd.value;
        if (pwd.length < 6) { toast('备份密码至少需要 6 位', true); form.elements.pwd.focus(); return; }
        if (confirm && pwd !== form.elements.pwd2.value) {
          toast('两次输入的密码不一致', true);
          form.elements.pwd2.value = '';
          form.elements.pwd2.focus();
          return;
        }
        close(pwd);
      };
    },
  });
}

/* 导入方式选择 */
function modalImportChoice(info) {
  const html = `
    <div class="modal-title">导入备份</div>
    <div class="modal-desc">
      备份包含 <strong>${info.groups}</strong> 个分组、<strong>${info.records}</strong> 条记录，
      导出时间 ${esc(info.exported_at)}。<br>请选择导入方式：
    </div>
    <div class="choice-list">
      <button class="choice" data-mode="merge">
        <div class="c-title">合并导入</div>
        <div class="c-desc">保留现有数据，仅补充备份中没有的记录（自动去重）</div>
      </button>
      <button class="choice danger" data-mode="replace">
        <div class="c-title">覆盖全部</div>
        <div class="c-desc">删除当前所有分组与记录，完全替换为备份内容（危险）</div>
      </button>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" data-cancel>取消</button>
    </div>`;
  return modal(html, {
    onMount(el, close) {
      el.querySelector('[data-cancel]').onclick = () => close(null);
      el.querySelectorAll('[data-mode]').forEach((b) => {
        b.onclick = () => close(b.dataset.mode);
      });
    },
  });
}

/* ------------------------------------------------ 记录操作 */

async function actionNew() {
  const fields = await modalRecord(null);
  if (!fields) return;
  const res = await call('create_record', fields);
  if (!res.ok) return toast(res.error, true);
  applySnapshot(res.data);
}

async function actionEdit(id) {
  const record = state.records.find((r) => r.id === id);
  if (!record) return;
  const fields = await modalRecord(record);
  if (!fields) return;
  const res = await call('update_record', id, fields);
  if (!res.ok) return toast(res.error, true);
  applySnapshot(res.data);
}

async function actionDelete(id) {
  const record = state.records.find((r) => r.id === id);
  if (!record) return;
  const ok = await modalConfirm(
    '删除记录',
    `确定删除 <strong>${esc(record.name)}</strong>？该操作不可撤销。`
  );
  if (!ok) return;
  const res = await call('delete_record', id);
  if (!res.ok) return toast(res.error, true);
  applySnapshot(res.data);
  toast('已删除');
}

async function actionCopy(id, kind, btn) {
  const res = await call('copy', id, kind);
  if (!res.ok) return toast(res.error, true);
  if (kind === 'username') { toast('已复制账号'); return; }
  if (btn) {
    btn.classList.add('copied');
    btn.innerHTML = `${ICON.check(14)}<span>已复制</span>`;
    setTimeout(() => {
      if (btn.isConnected) {
        btn.classList.remove('copied');
        btn.innerHTML = `${ICON.copy(14)}<span>复制</span>`;
      }
    }, 1600);
  }
}

function toggleReveal(id) {
  const record = state.records.find((r) => r.id === id);
  if (!record) return;
  const current = isSecretVisible(record);
  state.secretOverrides.set(id, !current);
  renderList();
}

/* ------------------------------------------------ 分组操作 */

async function actionNewGroup() {
  const name = await modalGroupName('新增分组');
  if (!name) return;
  const res = await call('create_group', name);
  if (!res.ok) return toast(res.error, true);
  applySnapshot(res.data);
}

async function actionRenameGroup(id) {
  const group = state.groups.find((g) => g.id === id);
  if (!group) return;
  const name = await modalGroupName('重命名分组', group.name);
  if (!name || name === group.name) return;
  const res = await call('rename_group', id, name);
  if (!res.ok) return toast(res.error, true);
  applySnapshot(res.data);
}

async function actionDeleteGroup(id) {
  const group = state.groups.find((g) => g.id === id);
  if (!group) return;
  const count = state.records.filter((r) => r.group_id === id).length;
  const desc = count
    ? `分组 <strong>${esc(group.name)}</strong> 中有 ${count} 条记录，删除后它们将变为「未分组」。`
    : `确定删除分组 <strong>${esc(group.name)}</strong>？`;
  const ok = await modalConfirm('删除分组', desc);
  if (!ok) return;
  const res = await call('delete_group', id);
  if (!res.ok) return toast(res.error, true);
  if (state.selectedGroupId === id) state.selectedGroupId = null;
  applySnapshot(res.data);
}

/* ------------------------------------------------ 备份操作 */

function timestamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

async function actionExport() {
  const pathRes = await call('save_path_dialog', `StoreApp-backup-${timestamp()}.sab`);
  if (pathRes.cancelled) return;
  if (!pathRes.ok) return toast(pathRes.error, true);

  const pwd = await modalPassword({
    title: '设置备份密码',
    desc: '该密码用于加密备份文件，<strong>不会被保存在任何地方</strong>；<span class="danger-text">遗忘后将无法恢复此备份。</span>',
    confirm: true,
  });
  if (pwd == null) return;

  const res = await call('export_backup', pathRes.path, pwd);
  if (!res.ok) return toast(res.error, true);
  toast(`已导出 ${res.groups} 个分组、${res.records} 条记录`);
}

async function actionImport() {
  const pathRes = await call('open_path_dialog');
  if (pathRes.cancelled) return;
  if (!pathRes.ok) return toast(pathRes.error, true);

  const pwd = await modalPassword({
    title: '输入备份密码',
    desc: '输入导出该备份时设置的密码。',
    confirm: false,
  });
  if (pwd == null) return;

  const preview = await call('import_preview', pathRes.path, pwd);
  if (!preview.ok) return toast(preview.error, true);

  const mode = await modalImportChoice(preview);
  if (!mode) return;

  const res = await call('import_backup', pathRes.path, pwd, mode);
  if (!res.ok) return toast(res.error, true);
  applySnapshot(res.data);
  const s = res.stats;
  toast(`导入完成：新增 ${s.records_added} 条，跳过重复 ${s.records_skipped} 条，新建分组 ${s.groups_created} 个`);
}

/* ------------------------------------------------ 设置菜单 */

function syncSettingsUi() {
  document.getElementById('show-secrets-switch').classList.toggle('on', state.showSecrets);
  document.getElementById('dd-version').textContent = `StoreApp v${state.version || '…'}`;
  const pathEl = document.getElementById('dd-path');
  pathEl.textContent = state.dbPath;
  pathEl.title = state.dbPath;
}

function closeSettingsMenu() {
  document.getElementById('settings-menu').hidden = true;
}

/* ------------------------------------------------ 事件绑定 */

function bindEvents() {
  /* 搜索 */
  const search = document.getElementById('search');
  if (!/Mac|iPhone|iPad/.test(navigator.platform || '')) {
    document.getElementById('search-kbd').textContent = 'Ctrl K';
  }
  search.addEventListener('input', () => {
    state.keyword = search.value;
    state.selectedRecordId = null;
    renderAll();
  });
  search.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      search.value = '';
      state.keyword = '';
      renderAll();
      search.blur();
    }
  });

  /* 边栏 */
  document.getElementById('group-list').addEventListener('click', (e) => {
    const actionBtn = e.target.closest('[data-g-action]');
    if (actionBtn) {
      e.stopPropagation();
      const gid = Number(actionBtn.dataset.gId);
      if (actionBtn.dataset.gAction === 'rename') actionRenameGroup(gid);
      else actionDeleteGroup(gid);
      return;
    }
    const item = e.target.closest('.group-item');
    if (!item) return;
    state.selectedGroupId = item.dataset.gId === 'null' ? null : Number(item.dataset.gId);
    state.selectedRecordId = null;
    renderAll();
  });
  document.getElementById('add-group-btn').onclick = actionNewGroup;

  /* 卡片列表（事件委托） */
  document.getElementById('record-list').addEventListener('click', (e) => {
    const actionBtn = e.target.closest('[data-action]');
    if (actionBtn) {
      e.stopPropagation();
      const id = Number(actionBtn.dataset.id);
      const action = actionBtn.dataset.action;
      if (action === 'copy') actionCopy(id, 'secret', actionBtn);
      else if (action === 'copy-user') actionCopy(id, 'username');
      else if (action === 'edit') actionEdit(id);
      else if (action === 'delete') actionDelete(id);
      else if (action === 'reveal') toggleReveal(id);
      return;
    }
    const card = e.target.closest('.card');
    if (!card) return;
    state.selectedRecordId = Number(card.dataset.recId);
    renderAll();
  });

  /* 空状态里的新增按钮 */
  document.getElementById('empty').addEventListener('click', (e) => {
    if (e.target.closest('[data-action="new-empty"]')) actionNew();
  });

  /* 工具栏 */
  document.getElementById('new-btn').onclick = actionNew;
  document.getElementById('edit-btn').onclick = () => {
    if (state.selectedRecordId) actionEdit(state.selectedRecordId);
  };
  document.getElementById('delete-btn').onclick = () => {
    if (state.selectedRecordId) actionDelete(state.selectedRecordId);
  };

  /* 设置下拉 */
  const gear = document.getElementById('gear-btn');
  const menu = document.getElementById('settings-menu');
  gear.onclick = (e) => {
    e.stopPropagation();
    menu.hidden = !menu.hidden;
  };
  document.addEventListener('click', (e) => {
    if (!menu.hidden && !menu.contains(e.target)) closeSettingsMenu();
  });

  document.getElementById('show-secrets-item').onclick = () => {
    state.showSecrets = !state.showSecrets;
    state.secretOverrides.clear();
    localStorage.setItem('storeapp.showSecrets', state.showSecrets ? '1' : '0');
    syncSettingsUi();
    renderList();
  };
  document.getElementById('export-item').onclick = () => { closeSettingsMenu(); actionExport(); };
  document.getElementById('import-item').onclick = () => { closeSettingsMenu(); actionImport(); };

  /* 快捷键 */
  document.addEventListener('keydown', (e) => {
    const inField = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'k' || e.key.toLowerCase() === 'f')) {
      e.preventDefault();
      search.focus();
      search.select();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'n') {
      e.preventDefault();
      actionNew();
      return;
    }
    if (e.key === 'Delete' && !inField && state.selectedRecordId
        && !document.querySelector('.overlay')) {
      actionDelete(state.selectedRecordId);
    }
  });
}

/* ------------------------------------------------ 启动 */

async function init() {
  bindEvents();
  const res = await call('bootstrap');
  if (!res.ok) {
    document.getElementById('empty').hidden = false;
    document.getElementById('empty').innerHTML =
      `${ICON.key(56)}<h3>无法加载数据</h3><p>${esc(res.error || '本地服务未就绪')}</p>`;
    return;
  }
  applySnapshot(res.data);
}

init();
