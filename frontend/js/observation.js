// WebSocket observation
let ws = null;
let reconnectTimer = null;
const agentNames = {};  // role_id -> name cache

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/observe`);

    ws.onopen = () => {
        console.log('WebSocket connected');
        const status = document.getElementById('connection-status');
        status.textContent = '已连接';
        status.className = 'status-connected';
        status.style.padding = '';
        status.style.fontWeight = '';
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'ping') return;
        addMessageToFeed(msg);
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        const status = document.getElementById('connection-status');
        status.textContent = '连接已断开 - 正在重连...';
        status.className = 'status-disconnected';
        status.style.padding = '6px 16px';
        status.style.fontWeight = '600';
        showToast('与服务器的连接已断开，正在尝试重连...', 'warning');
        reconnectTimer = setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        ws.close();
    };
}

function addMessageToFeed(msg) {
    const container = document.getElementById('messages');

    // Remove empty state
    const emptyState = container.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    const type = msg.type;
    const data = msg.data;

    // Determine bubble style
    if (type === 'system_event') {
        bubble.classList.add('system');
    } else if (type === 'task_delegation') {
        bubble.classList.add('delegation');
    } else if (type === 'user_response') {
        bubble.classList.add('user');
    } else {
        bubble.classList.add('agent');
    }

    // Build sender label
    let senderLabel = '系统';
    if (type === 'user_response') {
        senderLabel = '用户';
    } else if (data.sender_role_id) {
        senderLabel = agentNames[data.sender_role_id] || data.sender_role_id.substring(0, 8);
    }

    // Type label
    const typeLabels = {
        'task_delegation': '📋 任务分配',
        'task_response': '✅ 任务完成',
        'status_update': '💬 状态更新',
        'clarification_request': '❓ 需要确认',
        'clarification_response': '💡 确认回复',
        'group_discussion': '👥 团队讨论',
        'system_event': '⚙️ 系统',
        'user_response': '👤 用户回复',
    };

    const timestamp = data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : '';

    bubble.innerHTML = `
        <div class="sender">${typeLabels[type] || type} · ${senderLabel}</div>
        <div class="message-content">${escapeHtml(data.content || '')}</div>
        <div class="timestamp">${timestamp}</div>
    `;

    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Cache agent names
async function cacheAgentNames() {
    try {
        const res = await fetch('/api/agents');
        const data = await res.json();
        // We need to map role IDs to names. Since API returns agents,
        // we store by id for lookup.
        data.agents.forEach(a => {
            agentNames[a.id] = a.name;
        });
    } catch (err) {
        console.error('Failed to cache agent names:', err);
    }
}

// Initialize WebSocket
document.addEventListener('DOMContentLoaded', () => {
    cacheAgentNames();
    connectWebSocket();
});
