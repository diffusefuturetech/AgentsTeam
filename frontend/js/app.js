// Global state
let currentGoalId = null;

// Toast notification utility
function showToast(message, type = 'error') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(tab.dataset.tab).classList.add('active');
    });
});

// Create goal
async function createGoal(e) {
    e.preventDefault();
    const input = document.getElementById('goal-input');
    const description = input.value.trim();
    if (!description) return;

    try {
        const res = await fetch('/api/goals', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description }),
        });
        const data = await res.json();
        input.value = '';
        currentGoalId = data.id;

        // Switch to observation tab
        document.querySelector('.tab[data-tab="observation"]').click();
        document.getElementById('current-goal').textContent = description;
        document.getElementById('goal-controls').classList.remove('hidden');

        loadGoals();
    } catch (err) {
        console.error('Failed to create goal:', err);
        showToast('创建目标失败');
    }
}

// Goal controls
async function pauseGoal() {
    if (!currentGoalId) return;
    try {
        await fetch(`/api/goals/${currentGoalId}/pause`, { method: 'POST' });
    } catch (err) {
        console.error('Failed to pause goal:', err);
        showToast('暂停目标失败');
    }
}

async function stopGoal() {
    if (!currentGoalId) return;
    if (!confirm('确定要停止当前目标吗？')) return;
    try {
        await fetch(`/api/goals/${currentGoalId}/stop`, { method: 'POST' });
        currentGoalId = null;
        document.getElementById('goal-controls').classList.add('hidden');
    } catch (err) {
        console.error('Failed to stop goal:', err);
        showToast('停止目标失败');
    }
}

async function confirmGoal() {
    if (!currentGoalId) return;
    try {
        await fetch(`/api/goals/${currentGoalId}/confirm`, { method: 'POST' });
        currentGoalId = null;
        document.getElementById('goal-controls').classList.add('hidden');
        document.getElementById('current-goal').textContent = '无活跃目标';
    } catch (err) {
        console.error('Failed to confirm goal:', err);
        showToast('确认目标失败');
    }
}

async function resumeGoal() {
    if (!currentGoalId) return;
    try {
        await fetch(`/api/goals/${currentGoalId}/resume`, { method: 'POST' });
    } catch (err) {
        console.error('Failed to resume goal:', err);
        showToast('恢复目标失败');
    }
}

// Load goals list
async function loadGoals() {
    try {
        const res = await fetch('/api/goals');
        const data = await res.json();
        const container = document.getElementById('goals-list');

        if (!data.goals.length) {
            container.innerHTML = '<div class="empty-state">暂无目标</div>';
            return;
        }

        container.innerHTML = data.goals.map(g => `
            <div class="goal-item">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <span class="goal-status ${g.status}">${g.status}</span>
                    <span style="font-size:0.8rem;color:var(--text-secondary)">${g.created_at ? new Date(g.created_at).toLocaleString() : ''}</span>
                </div>
                <div style="margin-top:8px;font-size:0.9rem">${g.description.substring(0, 200)}</div>
            </div>
        `).join('');

        // Update current goal if active
        const active = data.goals.find(g => g.status === 'active' || g.status === 'pending_confirmation');
        if (active) {
            currentGoalId = active.id;
            document.getElementById('current-goal').textContent = active.description.substring(0, 200);
            document.getElementById('goal-controls').classList.remove('hidden');
            if (active.status === 'pending_confirmation') {
                document.getElementById('confirm-btn').classList.remove('hidden');
            }
        }
    } catch (err) {
        console.error('Failed to load goals:', err);
        showToast('加载目标列表失败');
    }
}

// Load team agents for sidebar
async function loadTeamAgents() {
    try {
        const res = await fetch('/api/agents');
        const data = await res.json();
        const container = document.getElementById('team-agents');
        container.innerHTML = data.agents.map(a => `
            <span class="agent-badge">
                <span class="dot"></span>
                ${a.name}
            </span>
        `).join('');
    } catch (err) {
        console.error('Failed to load team agents:', err);
    }
}

// Poll for goal progress
async function pollGoalProgress() {
    if (!currentGoalId) return;
    try {
        const res = await fetch(`/api/goals/${currentGoalId}`);
        const data = await res.json();

        const container = document.getElementById('task-progress');
        if (data.tasks && data.tasks.length > 0) {
            const p = data.progress;
            container.innerHTML = `
                <div class="progress-item"><span>总任务</span><span>${p.total_tasks}</span></div>
                <div class="progress-item"><span>已完成</span><span style="color:var(--success)">${p.completed}</span></div>
                <div class="progress-item"><span>进行中</span><span style="color:var(--warning)">${p.in_progress}</span></div>
                <div class="progress-item"><span>待处理</span><span>${p.pending}</span></div>
            `;
        }

        if (data.status === 'pending_confirmation') {
            document.getElementById('confirm-btn').classList.remove('hidden');
        }
    } catch (err) {
        console.error('Failed to poll goal progress:', err);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadGoals();
    loadTeamAgents();
    setInterval(pollGoalProgress, 5000);
});
