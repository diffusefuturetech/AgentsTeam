// History Tab - View completed goal sessions

// Load completed goals into the dropdown
async function loadCompletedGoals() {
    try {
        const res = await fetch('/api/goals?status=completed');
        const data = await res.json();
        const select = document.getElementById('history-goal-select');

        // Clear existing options except the placeholder
        select.innerHTML = '<option value="">-- 请选择目标 --</option>';

        if (!data.goals || !data.goals.length) {
            return;
        }

        data.goals.forEach(goal => {
            const option = document.createElement('option');
            option.value = goal.id;
            const date = goal.created_at ? new Date(goal.created_at).toLocaleString() : '';
            const desc = goal.description.substring(0, 80);
            option.textContent = `${desc}${goal.description.length > 80 ? '...' : ''} (${date})`;
            select.appendChild(option);
        });
    } catch (err) {
        console.error('Failed to load completed goals:', err);
    }
}

// Load history for a specific goal
async function loadGoalHistory(goalId) {
    if (!goalId) {
        document.getElementById('history-detail').classList.add('hidden');
        return;
    }

    try {
        // First get goal details to find session_id
        const goalRes = await fetch(`/api/goals/${goalId}`);
        const goalData = await goalRes.json();

        const sessionId = goalData.session_id;
        if (!sessionId) {
            document.getElementById('history-messages').innerHTML =
                '<div class="empty-state">该目标没有关联的会话</div>';
            document.getElementById('history-artifacts').innerHTML =
                '<div class="empty-state">暂无产出物</div>';
            document.getElementById('history-detail').classList.remove('hidden');
            return;
        }

        // Fetch messages and artifacts in parallel
        const [messagesRes, artifactsRes] = await Promise.all([
            fetch(`/api/sessions/${sessionId}/messages?limit=100&offset=0`),
            fetch(`/api/sessions/${sessionId}/artifacts`),
        ]);

        const messagesData = await messagesRes.json();
        const artifactsData = await artifactsRes.json();

        renderMessages(messagesData.messages || []);
        renderArtifacts(artifactsData.artifacts || []);

        document.getElementById('history-detail').classList.remove('hidden');
    } catch (err) {
        console.error('Failed to load goal history:', err);
    }
}

// Render message list
function renderMessages(messages) {
    const container = document.getElementById('history-messages');

    if (!messages.length) {
        container.innerHTML = '<div class="empty-state">暂无消息记录</div>';
        return;
    }

    container.innerHTML = messages.map(msg => {
        const role = msg.role || 'system';
        const time = msg.created_at ? new Date(msg.created_at).toLocaleString() : '';
        const sender = msg.agent_name || role;
        const content = msg.content || '';

        return `
            <div class="history-message role-${role}">
                <div class="msg-header">
                    <span class="msg-role">${sender}</span>
                    <span class="msg-time">${time}</span>
                </div>
                <div class="msg-body">${escapeHtml(content)}</div>
            </div>
        `;
    }).join('');
}

// Render artifact cards
function renderArtifacts(artifacts) {
    const container = document.getElementById('history-artifacts');

    if (!artifacts.length) {
        container.innerHTML = '<div class="empty-state">暂无产出物</div>';
        return;
    }

    container.innerHTML = artifacts.map(art => {
        const type = art.type || '文件';
        const name = art.name || art.filename || '未命名';
        const preview = art.content ? art.content.substring(0, 200) : '';
        const time = art.created_at ? new Date(art.created_at).toLocaleString() : '';

        return `
            <div class="artifact-card">
                <span class="artifact-type">${escapeHtml(type)}</span>
                <div class="artifact-name">${escapeHtml(name)}</div>
                ${preview ? `<div class="artifact-preview">${escapeHtml(preview)}</div>` : ''}
                ${time ? `<div class="artifact-time">${time}</div>` : ''}
            </div>
        `;
    }).join('');
}

// HTML escape helper
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Event listeners
document.getElementById('history-goal-select').addEventListener('change', (e) => {
    loadGoalHistory(e.target.value);
});

// Load completed goals when switching to history tab
document.querySelector('.tab[data-tab="history"]').addEventListener('click', () => {
    loadCompletedGoals();
});
