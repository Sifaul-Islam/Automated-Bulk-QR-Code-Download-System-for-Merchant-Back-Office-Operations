window.addEventListener('DOMContentLoaded', function() {
    const saved = localStorage.getItem('upay_credentials');
    if (saved) {
        try {
            const creds = JSON.parse(saved);
            const usernameField = document.getElementById('username');
            const passwordField = document.getElementById('password');
            const rememberField = document.getElementById('rememberMe');
            if (usernameField) usernameField.value = creds.username || '';
            if (passwordField) passwordField.value = creds.password || '';
            if (rememberField) rememberField.checked = true;
        } catch (e) {}
    }
});

function iconMarkup(name) {
    const icons = {
        warning: '<svg class="inline-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 2.5 20h19z"/><path d="M12 9v4m0 3h.01"/></svg>',
        check: '<svg class="inline-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16 9"/></svg>',
        spinner: '<svg class="inline-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v5h-5"/></svg>',
        close: '<svg class="inline-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m9 9 6 6m0-6-6 6"/></svg>',
        download: '<svg class="inline-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m0 0 4-4m-4 4-4-4M4 17v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/></svg>',
        view: '<svg class="inline-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12S6 6 12 6s9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.5"/></svg>',
        play: '<svg class="inline-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m8 5 11 7-11 7z"/></svg>'
    };
    return icons[name] || '';
}

async function startJob() {
    const username    = document.getElementById('username').value.trim();
    const password     = document.getElementById('password').value.trim();
    const fileInput     = document.getElementById('fileInput');
    const errorAlert    = document.getElementById('errorAlert');
    const rememberMe    = document.getElementById('rememberMe').checked;

    if (!username || !password) {
        showError('Please enter your username and password');
        return;
    }
    if (!fileInput.files[0]) {
        showError('Please select an Excel file');
        return;
    }

    if (rememberMe) {
        localStorage.setItem('upay_credentials', JSON.stringify({ username, password }));
    } else {
        localStorage.removeItem('upay_credentials');
    }

    errorAlert.style.display = 'none';

    const btn = document.getElementById('startBtn');
    btn.disabled    = true;
    btn.innerHTML = iconMarkup('spinner') + ' Starting...';

    const formData = new FormData();
    formData.append('username',   username);
    formData.append('password',   password);
    formData.append('excel_file', fileInput.files[0]);

    try {
        const response = await fetch('/api/start', {
            method: 'POST',
            body:   formData
        });

        const data = await response.json();

        if (data.job_id) {
            window.location.href = `/progress.html?job_id=${data.job_id}`;
        } else {
            showError(data.error || 'Failed to start job');
            btn.disabled    = false;
            btn.innerHTML = iconMarkup('play') + ' Start Automation';
        }
    } catch (err) {
        showError('Could not connect to server. Make sure server.py is running.');
        btn.disabled    = false;
        btn.innerHTML = iconMarkup('play') + ' Start Automation';
    }
}

function showError(message) {
    const alert = document.getElementById('errorAlert');
    if (alert) {
        alert.textContent   = message;
        alert.insertAdjacentHTML('afterbegin', iconMarkup('warning') + ' ');
        alert.style.display = 'block';
    }
}

async function loadHistory() {
    try {
        const response = await fetch('/api/jobs');
        const jobs     = await response.json();

        const container = document.getElementById('historyContainer');
        if (!container) return;

        if (!jobs || jobs.length === 0) {
            container.innerHTML = `
                <p style="color:#888; font-size:13px; text-align:center; padding:20px;">
                    No jobs yet
                </p>`;
            return;
        }

        let html = `
            <table class="history-table">
                <thead>
                    <tr>
                        <th>File Name</th>
                        <th>Started</th>
                        <th>Status</th>
                        <th>Downloaded</th>
                        <th>Missing</th>
                        <th>Total</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>`;

        jobs.forEach(job => {
            const statusBadge = getStatusBadge(job.status);
            const action      = getAction(job);

            html += `
                <tr>
                    <td><strong>${job.excel_name || '—'}</strong></td>
                    <td>${job.started_at || '—'}</td>
                    <td>${statusBadge}</td>
                    <td style="color:#28a745; font-weight:700;">${job.downloaded_count || 0}</td>
                    <td style="color:#dc3545; font-weight:700;">${job.missing_count || 0}</td>
                    <td>${job.total_count || 0}</td>
                    <td>${action}</td>
                </tr>`;
        });

        html += '</tbody></table>';
        container.innerHTML = html;

    } catch (err) {
        console.error('History load error:', err);
    }
}

function getStatusBadge(status) {
    if (status === 'done')    return `<span class="badge badge-done">${iconMarkup('check')} Done</span>`;
    if (status === 'running') return `<span class="badge badge-running">${iconMarkup('spinner')} Running</span>`;
    if (status === 'failed')  return `<span class="badge badge-failed">${iconMarkup('close')} Failed</span>`;
    return '<span class="badge">—</span>';
}

function getAction(job) {
    if (job.status === 'done') {
        return `<a href="/api/download/${job.job_id}" class="download-link">${iconMarkup('download')} Download ZIP</a>`;
    }
    if (job.status === 'running') {
        return `<a href="/progress.html?job_id=${job.job_id}" class="download-link">${iconMarkup('view')} View Progress</a>`;
    }
    return '—';
}

if (window.location.pathname === '/' || window.location.pathname.includes('index')) {
    setInterval(loadHistory, 5000);
}

function togglePassword() {
    const input = document.getElementById('password');
    const icon  = document.getElementById('eyeIcon');
    if (input.type === 'password') {
        input.type    = 'text';
        icon.innerHTML = `
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"></path>
            <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"></path>
            <line x1="1" y1="1" x2="23" y2="23"></line>
        `;
    } else {
        input.type    = 'password';
        icon.innerHTML = `
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
            <circle cx="12" cy="12" r="3"></circle>
        `;
    }
}
