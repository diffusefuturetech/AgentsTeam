// Agent management UI

async function loadAgentsList() {
    try {
        const res = await fetch('/api/agents?include_inactive=true');
        const data = await res.json();
        const container = document.getElementById('agents-list');

        if (!data.agents.length) {
            container.innerHTML = '<div class="empty-state">暂无Agent</div>';
            return;
        }

        container.innerHTML = data.agents.map(a => `
            <div class="agent-item">
                <div class="agent-info">
                    <div style="display:flex;align-items:center;gap:8px">
                        <span class="agent-name">${escapeHtml(a.name)}</span>
                        ${a.is_predefined ? '<span class="predefined-badge">预定义</span>' : ''}
                        ${!a.is_active ? '<span style="color:var(--danger);font-size:0.75rem">已停用</span>' : ''}
                    </div>
                    <div class="agent-role-key">${a.role_key} · ${a.provider_name}/${a.model_name}</div>
                    <div class="agent-expertise">${(a.expertise || []).join(', ')}</div>
                </div>
                <div>
                    ${!a.is_predefined ? `<button class="btn btn-danger btn-small" onclick="deleteAgent('${a.id}')">删除</button>` : ''}
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Failed to load agents:', err);
        showToast('加载Agent列表失败');
    }
}

async function createAgent(e) {
    e.preventDefault();

    const data = {
        name: document.getElementById('agent-name').value,
        role_key: document.getElementById('agent-role-key').value,
        expertise: document.getElementById('agent-expertise').value.split(',').map(s => s.trim()).filter(Boolean),
        responsibilities: document.getElementById('agent-responsibilities').value,
        system_prompt: document.getElementById('agent-prompt').value || `You are a ${document.getElementById('agent-name').value}. Your current goal is: {goal}`,
        provider_name: document.getElementById('agent-provider').value,
        model_name: document.getElementById('agent-model').value,
    };

    try {
        const res = await fetch('/api/agents', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        if (!res.ok) {
            const err = await res.json();
            alert(err.detail || 'Failed to create agent');
            return;
        }

        // Reset form
        document.getElementById('agent-form').reset();
        document.getElementById('agent-model').value = 'claude-sonnet-4-6';

        loadAgentsList();
        loadTeamAgents();
    } catch (err) {
        console.error('Failed to create agent:', err);
        showToast('创建Agent失败');
    }
}

async function deleteAgent(agentId) {
    if (!confirm('确定要删除这个Agent吗？')) return;

    try {
        await fetch(`/api/agents/${agentId}`, { method: 'DELETE' });
        loadAgentsList();
        loadTeamAgents();
    } catch (err) {
        console.error('Failed to delete agent:', err);
        showToast('删除Agent失败');
    }
}

// Load on tab switch
document.querySelector('.tab[data-tab="agents"]').addEventListener('click', loadAgentsList);
document.querySelector('.tab[data-tab="goals"]').addEventListener('click', loadGoals);

// Initial load
document.addEventListener('DOMContentLoaded', loadAgentsList);
