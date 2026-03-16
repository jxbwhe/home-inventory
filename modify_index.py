import re

def main():
    with open('app/static/index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update Header
    header_replacement = """    <div class="app-header">
        <h1><i class="bi bi-house-heart"></i> 家庭消耗品管理</h1>
        <div class="subtitle">跟踪消耗 · 及时补货</div>
        <div class="mt-2 text-center">
            <select id="header-family-select" class="form-select form-select-sm" style="background-color: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; display: inline-block; width: auto; min-width: 120px;" onchange="onFamilyChange()">
                <option value="0" style="color: black;">全部家庭</option>
            </select>
        </div>
    </div>"""
    content = re.sub(r'<div class="app-header">.*?</div>', header_replacement, content, flags=re.DOTALL)

    # 2. Add Settings Navigation Button
    nav_replacement = """        <button class="nav-btn" onclick="showSection('add-item-section', this)" id="nav-add">
            <i class="bi bi-plus-circle-fill"></i>
            <span>添加</span>
        </button>
        <button class="nav-btn" onclick="showSection('settings-section', this)" id="nav-settings">
            <i class="bi bi-gear-fill"></i>
            <span>设置</span>
        </button>"""
    content = content.replace('        <button class="nav-btn" onclick="showSection(\'add-item-section\', this)" id="nav-add">\n            <i class="bi bi-plus-circle-fill"></i>\n            <span>添加</span>\n        </button>', nav_replacement)

    # 3. Add Settings Section
    settings_section = """    <!-- Settings Section -->
    <div id="settings-section" class="section">
        <div class="section-title">
            <h5>系统设置</h5>
        </div>
        
        <!-- Families Management -->
        <div class="form-card mb-3">
            <h6 class="mb-3"><i class="bi bi-people"></i> 家庭管理</h6>
            <div id="settings-family-list" class="mb-3"></div>
            <form id="add-family-form" class="d-flex gap-2">
                <input type="text" class="form-control form-control-sm" id="new-family-name" required placeholder="新增家庭名称(如：公司/新家)">
                <button type="submit" class="btn btn-sm btn-primary-gradient"><i class="bi bi-plus"></i></button>
            </form>
        </div>

        <!-- Notify Channels Management -->
        <div class="form-card mb-3">
            <h6 class="mb-3"><i class="bi bi-bell"></i> 通知渠道管理</h6>
            <div id="settings-channel-list" class="mb-3"></div>
            <form id="add-channel-form" class="row g-2">
                <div class="col-12">
                    <input type="text" class="form-control form-control-sm" id="channel-name" required placeholder="渠道名称(如：PushPlus)">
                </div>
                <div class="col-10">
                    <input type="text" class="form-control form-control-sm" id="channel-token" required placeholder="Token">
                </div>
                <div class="col-2">
                    <button type="submit" class="btn btn-sm btn-primary-gradient w-100"><i class="bi bi-plus"></i></button>
                </div>
            </form>
        </div>

        <!-- API Token Management -->
        <div class="form-card mb-3">
            <h6 class="mb-3"><i class="bi bi-key"></i> 开放 API Token</h6>
            <div id="settings-token-list" class="mb-3"></div>
            <form id="add-token-form" class="d-flex gap-2 mb-3">
                <input type="text" class="form-control form-control-sm" id="token-name" required placeholder="Token 用途说明">
                <button type="submit" class="btn btn-sm btn-primary-gradient"><i class="bi bi-plus"></i> 创建</button>
            </form>
            <div class="text-center">
                <a href="/api_docs.html" class="btn btn-sm btn-outline-primary"><i class="bi bi-file-earmark-code"></i> 查看 API 文档</a>
            </div>
        </div>
    </div>

    <!-- Bottom Navigation -->"""
    content = content.replace('    <!-- Bottom Navigation -->', settings_section)

    # 4. Modify Add Item Form
    add_item_desc = """                <div class="mb-3">
                    <label class="form-label">描述</label>
                    <textarea class="form-control" name="description" rows="2" placeholder="可选，如品牌、规格等"></textarea>
                </div>"""
    add_item_desc_with_family = add_item_desc + """\n                <div class="mb-3">
                    <label class="form-label">所属家庭</label>
                    <select class="form-select" name="family_id" id="add-family-select">
                        <option value="">未分组</option>
                    </select>
                </div>"""
    content = content.replace(add_item_desc, add_item_desc_with_family)

    # 5. Modify Edit Form
    edit_desc = """                        <div class="mb-3">
                            <label class="form-label">描述</label>
                            <textarea class="form-control" id="edit-description" rows="2"></textarea>
                        </div>"""
    edit_desc_with_family = edit_desc + """\n                        <div class="mb-3">
                            <label class="form-label">所属家庭</label>
                            <select class="form-select" id="edit-family-select">
                                <option value="">未分组</option>
                            </select>
                        </div>"""
    content = content.replace(edit_desc, edit_desc_with_family)

    # 6. Usage History Modal
    history_modal_end = """    <!-- Image Preview Modal -->"""
    usage_history_modal = """    <!-- Usage History Modal -->
    <div class="modal fade" id="usageHistoryModal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="bi bi-card-list"></i> 使用记录</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body p-0" id="usage-history-list">
                    <!-- Populated by JS -->
                </div>
            </div>
        </div>
    </div>

    <!-- Image Preview Modal -->"""
    content = content.replace(history_modal_end, usage_history_modal)

    # 7. Add Usage History Button to renderItems
    item_actions = """                        <button class="btn btn-outline-info btn-sm" onclick="openHistoryModal(${item.id})" title="购买记录">
                            <i class="bi bi-clock-history"></i>
                        </button>"""
    item_actions_new = item_actions + """\n                        <button class="btn btn-outline-secondary btn-sm" onclick="openUsageHistoryModal(${item.id})" title="使用记录">
                            <i class="bi bi-card-list"></i>
                        </button>"""
    content = content.replace(item_actions, item_actions_new)

    # 8. JS updates
    
    js_global_vars = """        const API_URL = '/api';
        let allItems = [];
        let currentFamilyId = 0;"""
    content = content.replace("        const API_URL = '/api';\n        let allItems = [];", js_global_vars)

    # Injecting big JS update payload before `// ---- Navigation ----` block
    
    js_additions = """
        // JS features extension
        async function loadFamilies() {
            try {
                const res = await fetch(`${API_URL}/families`);
                const families = await res.json();
                
                // Header Select
                const hSelect = document.getElementById('header-family-select');
                if (hSelect) {
                    hSelect.innerHTML = '<option value="0" style="color: black;">全部家庭</option>';
                    families.forEach(f => {
                        hSelect.innerHTML += `<option value="${f.id}" style="color: black;" ${currentFamilyId === f.id ? 'selected':''}>${f.name}</option>`;
                    });
                }
                
                // Add/Edit Selects
                const aSelect = document.getElementById('add-family-select');
                const eSelect = document.getElementById('edit-family-select');
                if (aSelect) {
                    aSelect.innerHTML = '<option value="">未分组</option>';
                    families.forEach(f => aSelect.innerHTML += `<option value="${f.id}">${f.name}</option>`);
                }
                if (eSelect) {
                    eSelect.innerHTML = '<option value="">未分组</option>';
                    families.forEach(f => eSelect.innerHTML += `<option value="${f.id}">${f.name}</option>`);
                }
                
                // Settings List
                const sList = document.getElementById('settings-family-list');
                if (sList) {
                    sList.innerHTML = '';
                    families.forEach(f => {
                        sList.innerHTML += `
                            <div class="d-flex justify-content-between align-items-center border-bottom py-2">
                                <div>
                                    <span class="fw-bold">${f.name}</span>
                                    <small class="text-muted ms-2">${f.item_count} 物品</small>
                                </div>
                                <button class="btn btn-sm text-danger" onclick="deleteFamily(${f.id})"><i class="bi bi-trash"></i></button>
                            </div>
                        `;
                    });
                }
            } catch (e) {
                console.error('Load families error:', e);
            }
        }
        
        function onFamilyChange() {
            currentFamilyId = parseInt(document.getElementById('header-family-select').value);
            loadDashboard();
            loadItems();
        }
        
        // Family forms
        if (document.getElementById('add-family-form')) {
            document.getElementById('add-family-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData();
                formData.append('name', document.getElementById('new-family-name').value);
                try {
                    const res = await fetch(`${API_URL}/families`, { method: 'POST', body: formData });
                    if (res.ok) {
                        document.getElementById('add-family-form').reset();
                        showToast('✅ 家庭添加成功');
                        await loadFamilies();
                    }
                } catch (err) {}
            });
        }
        
        async function deleteFamily(id) {
            if(!confirm('确定删除此家庭？该家庭关联会丢失。')) return;
            try {
                const res = await fetch(`${API_URL}/families/${id}`, { method: 'DELETE' });
                if(res.ok) { showToast('✅ 家庭已删除'); if(currentFamilyId === id) { currentFamilyId = 0; onFamilyChange(); } else { loadFamilies(); } }
            } catch(e){}
        }

        // Channels
        async function loadChannels() {
            try {
                const res = await fetch(`${API_URL}/notify-channels`);
                const channels = await res.json();
                const sList = document.getElementById('settings-channel-list');
                if (!sList) return;
                sList.innerHTML = '';
                channels.forEach(c => {
                    const status = c.enabled ? '<span class="badge bg-success">已启用</span>' : '<span class="badge bg-secondary">已禁用</span>';
                    sList.innerHTML += `
                        <div class="border-bottom py-2 mb-2">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <div><span class="fw-bold">${c.name}</span> (${c.channel_type}) ${status}</div>
                                <div>
                                    <button class="btn btn-sm text-info" onclick="testChannel(${c.id})"><i class="bi bi-send"></i></button>
                                    <button class="btn btn-sm ${c.enabled?'text-warning':'text-success'}" onclick="toggleChannel(${c.id}, ${!c.enabled})"><i class="bi ${c.enabled?'bi-pause-circle':'bi-play-circle'}"></i></button>
                                    <button class="btn btn-sm text-danger" onclick="deleteChannel(${c.id})"><i class="bi bi-trash"></i></button>
                                </div>
                            </div>
                            <small class="text-muted">Token: ${c.config.token || '-'}</small>
                        </div>
                    `;
                });
            } catch(e){}
        }
        
        if (document.getElementById('add-channel-form')) {
            document.getElementById('add-channel-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData();
                formData.append('name', document.getElementById('channel-name').value);
                formData.append('channel_type', 'pushplus');
                formData.append('config', JSON.stringify({token: document.getElementById('channel-token').value}));
                try {
                    const res = await fetch(`${API_URL}/notify-channels`, { method: 'POST', body: formData });
                    if(res.ok) {
                        document.getElementById('add-channel-form').reset();
                        showToast('✅ 渠道添加成功');
                        loadChannels();
                    }
                } catch(e){}
            });
        }

        async function toggleChannel(id, enabled) {
            const formData = new FormData(); formData.append('enabled', enabled);
            try {
                const res = await fetch(`${API_URL}/notify-channels/${id}`, { method: 'PUT', body: formData });
                if(res.ok) { showToast('✅ 状态已更新'); loadChannels(); }
            } catch(e){}
        }
        async function testChannel(id) {
            try {
                const res = await fetch(`${API_URL}/notify-channels/${id}/test`, { method: 'POST' });
                if(res.ok) showToast('✅ 测试消息已推送');
                else showToast('❌ 测试发送失败');
            } catch(e){}
        }
        async function deleteChannel(id) {
            if(!confirm('确定删除?')) return;
            try {
                const res = await fetch(`${API_URL}/notify-channels/${id}`, { method: 'DELETE' });
                if(res.ok) { showToast('✅ 渠道已删除'); loadChannels(); }
            } catch(e){}
        }

        // Tokens
        async function loadTokens() {
            try {
                const res = await fetch(`${API_URL}/tokens`);
                const tokens = await res.json();
                const sList = document.getElementById('settings-token-list');
                if (!sList) return;
                sList.innerHTML = '';
                tokens.forEach(t => {
                    sList.innerHTML += `
                        <div class="d-flex justify-content-between align-items-center border-bottom py-2">
                            <div>
                                <span class="fw-bold">${t.name}</span><br>
                                <small class="text-muted font-monospace">${t.token_preview}</small>
                            </div>
                            <button class="btn btn-sm text-danger" onclick="deleteToken(${t.id})"><i class="bi bi-trash"></i></button>
                        </div>
                    `;
                });
            } catch(e){}
        }
        
        if (document.getElementById('add-token-form')) {
            document.getElementById('add-token-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData();
                formData.append('name', document.getElementById('token-name').value);
                try {
                    const res = await fetch(`${API_URL}/tokens`, { method: 'POST', body: formData });
                    if(res.ok) {
                        const data = await res.json();
                        document.getElementById('add-token-form').reset();
                        alert(`请妥善保存此Token，仅显示一次：\\n\\n${data.token}`);
                        loadTokens();
                    }
                } catch(e){}
            });
        }
        
        async function deleteToken(id) {
            if(!confirm('确定删除此Token? 关联API将失效。')) return;
            try {
                const res = await fetch(`${API_URL}/tokens/${id}`, { method: 'DELETE' });
                if(res.ok) { showToast('✅ Token已删除'); loadTokens(); }
            } catch(e){}
        }

        // Usage history
        let usageHistoryModal = null;
        document.addEventListener('DOMContentLoaded', () => {
            usageHistoryModal = new bootstrap.Modal(document.getElementById('usageHistoryModal'));
        });
        
        async function openUsageHistoryModal(itemId) {
            const list = document.getElementById('usage-history-list');
            list.innerHTML = '<div style="padding:30px; text-align:center; color:var(--text-muted);"><i class="bi bi-hourglass-split"></i> 加载中...</div>';
            if (usageHistoryModal) usageHistoryModal.show();
            try {
                const res = await fetch(`${API_URL}/items/${itemId}/usages`);
                const usages = await res.json();
                if (usages.length === 0) {
                    list.innerHTML = '<div style="padding:30px; text-align:center; color:var(--text-muted);"><i class="bi bi-inbox" style="font-size:2rem; display:block; margin-bottom:8px;"></i>暂无使用记录</div>';
                    return;
                }
                list.innerHTML = usages.map(u => `
                    <div class="purchase-item text-center d-flex flex-column align-items-start px-4">
                        <div class="fw-bold fs-6">消耗量：${u.quantity}</div>
                        <div class="text-muted mt-1 w-100 text-start" style="font-size: 0.8rem;"><i class="bi bi-clock"></i> ${u.date}</div>
                    </div>
                `).join('');
            } catch(e) {
                list.innerHTML = '<div style="padding:30px; text-align:center; color:var(--danger);">加载失败</div>';
            }
        }
"""
    content = content.replace("        // ---- Navigation ----", js_additions + "\n        // ---- Navigation ----")

    # Hook loadDashboard/loadItems
    content = content.replace("const res = await fetch(`${API_URL}/dashboard`);", "const res = await fetch(`${API_URL}/dashboard` + (currentFamilyId > 0 ? `?family_id=${currentFamilyId}` : ''));")
    content = content.replace("const res = await fetch(`${API_URL}/items`);", "const res = await fetch(`${API_URL}/items` + (currentFamilyId > 0 ? `?family_id=${currentFamilyId}` : ''));")

    # Add `family_id` to add item request form data
    content = content.replace("document.getElementById('edit-unit').value = item.unit;", "document.getElementById('edit-unit').value = item.unit;\n                document.getElementById('edit-family-select').value = item.family_id || '';")
    content = content.replace("formData.append('min_quantity', document.getElementById('edit-min-quantity').value);", "formData.append('min_quantity', document.getElementById('edit-min-quantity').value);\n            formData.append('family_id', document.getElementById('edit-family-select').value);")

    # Modify mappings
    mapping_str = """                const mapping = {
                    'dashboard-section': 'nav-dashboard',
                    'items-section': 'nav-items',
                    'add-item-section': 'nav-add',
                };"""
    mapping_str_new = """            if(sectionId === 'settings-section') { loadFamilies(); loadChannels(); loadTokens(); }
                const mapping = {
                    'dashboard-section': 'nav-dashboard',
                    'items-section': 'nav-items',
                    'add-item-section': 'nav-add',
                    'settings-section': 'nav-settings',
                };"""
    content = content.replace(mapping_str, mapping_str_new)

    # Init
    init_str = """        // ---- Init ----
        loadDashboard();"""
    init_str_new = """        // ---- Init ----
        loadFamilies().then(() => { loadDashboard(); loadItems(); });
        loadChannels();
        loadTokens();"""
    content = content.replace(init_str, init_str_new)

    with open('app/static/index.html', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    main()
