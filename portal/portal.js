const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? "http://localhost:8000/merchant_ops"
    : window.location.origin + "/merchant_ops";let authToken       = null;
let currentType     = "Child";
let selectedWallets = [];
let allMerchants    = [];
let currentPage     = 1;
const PAGE_SIZE     = 30;
let otherPageType   = "Child";
let otherPageStatus = "Pending";
let otherAllData    = [];
let otherCurrentPage = 1;

// =============================================
// LOGIN
// =============================================
async function doLogin() {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value.trim();
    const errorDiv = document.getElementById('loginError');

    if (!username || !password) {
        errorDiv.textContent   = 'Please enter username and password';
        errorDiv.style.display = 'block';
        return;
    }

    try {
        const res  = await fetch(`${API_BASE}/auth/web/v1/login/`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ username, password, portal: "merchant_back_ops" })
        });
        const data = await res.json();


        let titlename = "";
        if (username === "sifaul") titlename = "Sifaul Islam";

        if (data.token) {
            authToken = data.token;
            document.getElementById('loginPage').style.display    = 'none';
            document.getElementById('dashboardPage').style.display = 'block';
            document.getElementById('headerName').textContent      = titlename || username;
            errorDiv.style.display = 'none';
            showPage('dashboard');
        } else {
            errorDiv.textContent   = 'Invalid username or password';
            errorDiv.style.display = 'block';
        }
    } catch (err) {
        errorDiv.textContent   = 'Cannot connect to server. Make sure portal_api.py is running.';
        errorDiv.style.display = 'block';
    }
}

document.addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;

    const lp = document.getElementById('loginPage');

    // LOGIN PAGE
    if (lp && lp.style.display !== 'none') {
        const username = document.getElementById('loginUsername');
        const password = document.getElementById('loginPassword');

        // Enter on username → password
        if (document.activeElement === username) {
            e.preventDefault();
            password.focus();
            return;
        }

        // Enter on password → login
        if (document.activeElement === password) {
            e.preventDefault();
            doLogin();
            return;
        }

        // Enter anywhere else on login page → username
        e.preventDefault();
        username.focus();
        return;
    }

    // WALLET SEARCH
    const ws = document.getElementById('walletSearch');

    if (document.activeElement === ws) {
        e.preventDefault();
        searchMerchants();
        return;
    }

    // OTHER WALLET SEARCH
    const ow = document.getElementById('otherWalletSearch');

    if (document.activeElement === ow) {
        e.preventDefault();
        searchOtherPage();
        return;
    }
});

// =============================================
// PASSWORD TOGGLE
// =============================================
function togglePortalPassword() {
    const input = document.getElementById('loginPassword');
    const icon  = document.getElementById('portalEyeIcon');
    if (input.type === 'password') {
        input.type     = 'text';
        icon.innerHTML = `
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"></path>
            <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"></path>
            <line x1="1" y1="1" x2="23" y2="23"></line>`;
    } else {
        input.type     = 'password';
        icon.innerHTML = `
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
            <circle cx="12" cy="12" r="3"></circle>`;
    }
}
function togglePassword() {
    const input = document.getElementById('loginPassword');
    const icon = document.querySelector('.password-toggle .eye-icon');

    if (!input || !icon) return;

    if (input.type === 'password') {
        input.type = 'text';

        icon.innerHTML = `
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"/>
            <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"/>
            <line x1="1" y1="1" x2="23" y2="23"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"/>
        `;
    } else {
        input.type = 'password';

        icon.innerHTML = `
            <path d="M2.5 12C4.2 8.5 7.6 6 12 6C16.4 6 19.8 8.5 21.5 12C19.8 15.5 16.4 18 12 18C7.6 18 4.2 15.5 2.5 12Z"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"/>
            <circle cx="12" cy="12" r="2.5"
                stroke="currentColor"
                stroke-width="1.8"/>
        `;
    }
}
// =============================================
// PAGE NAVIGATION
// =============================================
function showPage(page, event) {
    if (event) event.stopPropagation();
    document.getElementById('pageDashboard').style.display    = 'none';
    document.getElementById('pageMerchantList').style.display = 'none';
    document.getElementById('pageOther').style.display        = 'none';

    if (page === 'dashboard') {
        document.getElementById('pageDashboard').style.display = 'block';
    } else if (page === 'merchantList') {
        document.getElementById('pageMerchantList').style.display = 'block';
    } else {
        document.getElementById('pageOther').style.display = 'block';
    }
}

function setActiveNavItem(target) {
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active-nav'));
    document.querySelectorAll('.nav-submenu li').forEach(el => el.classList.remove('active-sub'));

    if (!target) return;

    target.classList.add('active-sub');
    const parent = target.closest('.nav-item.has-sub');
    if (parent) {
        parent.classList.add('active-nav');
        const sub = parent.querySelector('.nav-submenu');
        if (sub) {
            sub.style.display = 'block';
            parent.classList.add('open');
        }
    }
}

function showMerchantList(type, event) {
    if (event) event.stopPropagation();
    currentType     = type;
    selectedWallets = [];
    allMerchants    = [];

    if (event && event.currentTarget) {
        setActiveNavItem(event.currentTarget);
    }

    const config = {
        Parent: { title: "ParentMerchant List",            banner: "PARENT MERCHANT LIST",           bc1: "ParentMerchant",  bc2: "ParentMerchant List",  createBtn: "ParentMerchant Create" },
        Child:  { title: "Child Merchant List",             banner: "CHILD MERCHANT LIST",            bc1: "Child Merchant",  bc2: "Child Merchant List",  createBtn: "ChildMerchant Create"  },
        PRA:    { title: "Micro Merchant Approved List",    banner: "MICRO MERCHANT APPROVED LIST",   bc1: "Micro Merchant",  bc2: "Approved List",        createBtn: "Micro Merchant Create" }
    };

    const c = config[type] || config.Child;
    document.getElementById('listTitle').textContent   = c.title;
    document.getElementById('listBanner').textContent  = c.banner;
    document.getElementById('breadcrumb1').textContent = c.bc1;
    document.getElementById('breadcrumb2').textContent = c.bc2;
    document.getElementById('createBtn').textContent   = c.createBtn;

    showPage('merchantList', event);
    updateCount();
    loadDefaultMerchants();
}


async function loadDefaultMerchants() {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '<tr><td colspan="8" class="table-empty">Loading...</td></tr>';

    try {
        let endpoint = "child_merchant";
        if (currentType === "Parent") endpoint = "parent_merchant";
        if (currentType === "PRA")    endpoint = "micro_merchant";

        const offset = (currentPage - 1) * PAGE_SIZE;
        const res = await fetch(`${API_BASE}/merchant/web/v1/${endpoint}/list/?wallet_number=&limit=${PAGE_SIZE}&offset=${offset}`,
            { headers: { "authorization": `MERCHANT ${authToken}`, "accept": "application/json" } }
        );
        const data = await res.json();
        const payload = data?.data || {};
        const results = payload.results || [];
        const total = Number(payload.count || 0);
        allMerchants = results;

        if (results.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="table-empty">No active merchants found</td></tr>';
            document.getElementById('pageInfo').textContent = '0-0 of 0';
            updatePaginationBtns(currentPage, Math.max(1, Math.ceil(total / PAGE_SIZE)), 'mainPag');
            return;
        }

        renderTable(results, total);
        document.getElementById('pageInfo').textContent = `${(currentPage - 1) * PAGE_SIZE + 1}-${Math.min(currentPage * PAGE_SIZE, total)} of ${total}`;

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="8" class="table-empty" style="color:#dc3545;">Error loading data</td></tr>';
    }
}
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const main    = document.getElementById('mainContent');
    if (sidebar.style.width === '0px') {
        sidebar.style.width   = '230px';
        main.style.marginLeft = '230px';
    } else {
        sidebar.style.width   = '0px';
        main.style.marginLeft = '0px';
    }
}

function toggleNav(item) {
    const sub = item.querySelector('.nav-submenu');
    if (!sub) return;
    const open = sub.style.display === 'block';
    sub.style.display = open ? 'none' : 'block';
    item.classList.toggle('open', !open);
}

function updateDashboard() {
    const month = document.getElementById('dashMonth').value;
    const year  = document.getElementById('dashYear').value;

    if (!month || !year) return;

    // Generate random but realistic looking data based on month/year
    const seed     = parseInt(month) + parseInt(year);
    const sales    = (seed * 12345 + 456789) % 900000 + 100000;
    const voidAmt  = (seed * 3456 + 12345) % 90000 + 10000;
    const refund   = (seed * 1234 + 5678) % 15000 + 5000;
    const saleCnt  = (seed * 23 + 456) % 2000 + 500;
    const voidCnt  = (seed * 7 + 23) % 100 + 20;
    const refCnt   = (seed * 3 + 12) % 50 + 10;

    // Update cards
    document.querySelector('.dash-card.purple-card .dash-stat:first-child .dash-num').textContent =
        '৳ ' + sales.toLocaleString();
    document.querySelector('.dash-card.purple-card .dash-stat:last-child .dash-num').textContent =
        saleCnt.toLocaleString();
    document.querySelector('.dash-card.green-card .dash-stat:first-child .dash-num').textContent =
        '৳ ' + voidAmt.toLocaleString();
    document.querySelector('.dash-card.green-card .dash-stat:last-child .dash-num').textContent =
        voidCnt.toLocaleString();
    document.querySelector('.dash-card.yellow-card .dash-stat:first-child .dash-num').textContent =
        '৳ ' + refund.toLocaleString();
    document.querySelector('.dash-card.yellow-card .dash-stat:last-child .dash-num').textContent =
        refCnt.toLocaleString();
}

function activateSidebarItem(target) {
    const item = target && target.closest ? target.closest('.nav-item') : null;

    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active-nav'));
    document.querySelectorAll('.nav-submenu li').forEach(el => el.classList.remove('active-sub'));

    if (item) {
        item.classList.add('active-nav');
    }

    if (target && target.classList && target.classList.contains('nav-submenu')) {
        return;
    }

    const submenuItem = target && target.closest ? target.closest('.nav-submenu li') : null;
    if (submenuItem) {
        submenuItem.classList.add('active-sub');
        const parent = submenuItem.closest('.nav-item.has-sub');
        if (parent) {
            parent.classList.add('active-nav');
            const sub = parent.querySelector('.nav-submenu');
            if (sub) {
                sub.style.display = 'block';
                parent.classList.add('open');
            }
        }
    }
}

document.addEventListener('click', function (event) {
    const clickedSubItem = event.target.closest('.nav-submenu li');
    if (clickedSubItem) {
        activateSidebarItem(clickedSubItem);
        return;
    }

    const clickedMainItem = event.target.closest('.nav-item');
    if (clickedMainItem) {
        activateSidebarItem(clickedMainItem);
    }
});

// =============================================
// ACTIVE LIST SEARCH
// =============================================
async function searchMerchants() {
    const wallet = document.getElementById('walletSearch').value.trim();
    const tbody  = document.getElementById('tableBody');
    currentPage = 1;

    const dba     = document.getElementById('dbaSearch').value.trim();
    const kam     = document.getElementById('kamSearch').value.trim();
    const status  = document.getElementById('statusSearch').value.trim();
    const persona = document.getElementById('personaSearch').value.trim();

    // Allow search if any filter is filled
    if (!wallet && !dba && !kam && !status && !persona) {
        loadDefaultMerchants();
        return;
    }

    tbody.innerHTML = '<tr><td colspan="8" class="table-empty">Searching...</td></tr>';

    try {
        let endpoint = "child_merchant";
        if (currentType === "Parent") endpoint = "parent_merchant";
        if (currentType === "PRA")    endpoint = "micro_merchant";

        

        const offset = (currentPage - 1) * PAGE_SIZE;
        const url = (() => {
                const dba     = encodeURIComponent(document.getElementById('dbaSearch').value.trim());
                const kam     = encodeURIComponent(document.getElementById('kamSearch').value.trim());
                const status  = document.getElementById('statusSearch').value || 'Active';
                const persona = encodeURIComponent(document.getElementById('personaSearch').value.trim());
                return `${API_BASE}/merchant/web/v1/${endpoint}/list/?wallet_number=${encodeURIComponent(wallet)}&dba=${dba}&kam=${kam}&status=${status}&persona=${persona}&limit=${PAGE_SIZE}&offset=${offset}`;
            })();
        console.log('Search URL:', url);
        const res     = await fetch(url, {
            headers: { "authorization": `MERCHANT ${authToken}`, "accept": "application/json" }
        });
        const data    = await res.json();
        const payload = data?.data || {};
        const results = payload.results || [];
        const total = Number(payload.count || 0);
        allMerchants  = results;

        if (results.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="table-empty">No results found for: ${wallet}</td></tr>`;
            document.getElementById('pageInfo').textContent = '0-0 of 0';
            updatePaginationBtns(1, 1, 'mainPag');
            return;
        }

        renderTable(results, total);
        document.getElementById('pageInfo').textContent = `${offset + 1}-${Math.min(offset + results.length, total)} of ${total}`;

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="8" class="table-empty" style="color:#dc3545;">Error connecting to API</td></tr>';
    }
}

function renderTable(merchants, totalCount = merchants.length) {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';

    if (!merchants || merchants.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12" class="table-empty">No data found</td></tr>';
        return;
    }

    merchants.forEach(m => {
        const selected = selectedWallets.includes(m.wallet_number);
        const tr       = document.createElement('tr');
        tr.className   = selected ? 'row-selected' : '';
        tr.innerHTML   = `
            <td><input type="checkbox" class="table-checkbox"
                ${selected ? 'checked' : ''}
                ${!selected && selectedWallets.length >= 30 ? 'disabled' : ''}
                onchange="toggleSelect('${m.wallet_number}', this)"></td>
            <td>${m.dba || '—'}</td>
            <td>${m.dba || '—'}</td>
            <td>${m.wallet_number || '—'}</td>
            <td>${m.merchant_id || '—'}</td>
            <td>${m.email || '—'}</td>
            <td>${m.merchant_type || 'Corporate'}</td>
            <td>${m.persona || 'Regular'}</td>
            <td>${m.division || 'Not Elsewhere Classified'}</td>
            <td>${m.kam || '—'}</td>
            <td>
                <button class="tbl-btn-view">View</button>
                <button class="tbl-btn-kam">Re-Assign KAM</button>
            </td>
            <td>
                <label class="toggle-switch">
                    <input type="checkbox" checked>
                    <span class="toggle-slider"></span>
                </label>
            </td>
        `;
        tbody.appendChild(tr);
    });

    const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
    document.getElementById('pageInfo').textContent = `${(currentPage - 1) * PAGE_SIZE + 1}-${Math.min(currentPage * PAGE_SIZE, totalCount)} of ${totalCount}`;
    updatePaginationBtns(currentPage, totalPages, 'mainPag');
}

function updatePaginationBtns(page, totalPages, id) {
    const btns = document.getElementById(id);
    if (!btns) return;
    btns.innerHTML = `
        <button class="page-btn" onclick="goPage(1, '${id}')" ${page === 1 ? 'disabled' : ''}>|‹</button>
        <button class="page-btn" onclick="goPage(${page - 1}, '${id}')" ${page === 1 ? 'disabled' : ''}>‹</button>
        <span style="padding:0 10px; font-size:13px; color:#555;">${page} / ${totalPages}</span>
        <button class="page-btn" onclick="goPage(${page + 1}, '${id}')" ${page === totalPages ? 'disabled' : ''}>›</button>
        <button class="page-btn" onclick="goPage(${totalPages}, '${id}')" ${page === totalPages ? 'disabled' : ''}>›|</button>
    `;
}

function goPage(page, id) {
    if (id === 'mainPag') {
        const totalPages = Math.max(1, Math.ceil((document.getElementById('pageInfo').textContent.match(/of\s+(\d+)/)?.[1] || allMerchants.length) / PAGE_SIZE));
        if (page < 1 || page > totalPages) return;
        currentPage = page;
        loadDefaultMerchants();
    } else if (id === 'otherPag') {
        const totalPages = Math.max(1, Math.ceil(otherAllData.length / PAGE_SIZE));
        if (page < 1 || page > totalPages) return;
        otherCurrentPage = page;
        renderOtherTable(otherAllData);
    } else if (id === 'qrLogPag') {
        renderQRLogs(page);
    } else if (id === 'transPag') {
        renderTransPage(page);
    }
}

function resetSearch() {
    ['walletSearch','dbaSearch','kamSearch','statusSearch','personaSearch'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    currentPage  = 1;
    allMerchants = [];
    updateCount();
    loadDefaultMerchants();
}

// =============================================
// SELECTION
// =============================================
function toggleSelect(wallet, cb) {
    if (cb.checked) {
        if (selectedWallets.length >= 30) {
            cb.checked = false;
            alert('Maximum 30 merchants can be selected at once.');
            return;
        }
        if (!selectedWallets.includes(wallet)) selectedWallets.push(wallet);
    } else {
        selectedWallets = selectedWallets.filter(w => w !== wallet);
    }
    updateCount();
    renderTable(allMerchants);
}

function toggleSelectAll(master) {
    const cbs = document.querySelectorAll('#tableBody input[type="checkbox"]');
    if (master.checked) {
        cbs.forEach((cb, i) => {
            if (selectedWallets.length < 30 && !cb.disabled) {
                cb.checked = true;
                const w = allMerchants[i]?.wallet_number;
                if (w && !selectedWallets.includes(w)) selectedWallets.push(w);
            }
        });
    } else {
        cbs.forEach(cb => cb.checked = false);
        selectedWallets = [];
    }
    updateCount();
    renderTable(allMerchants);
}

function updateCount() {
    const el = document.getElementById('selectedCount');
    if (el) el.textContent = `${selectedWallets.length} selected (max 30)`;
}

// =============================================
// DOWNLOAD MODAL
// =============================================
function openDownloadModal() {
    if (selectedWallets.length === 0) {
        alert('Please select at least one merchant first.');
        return;
    }
    document.getElementById('downloadModal').style.display = 'flex';
    document.getElementById('dlStatus').style.display      = 'none';
}

function closeDownloadModal() {
    document.getElementById('downloadModal').style.display = 'none';
}

async function downloadQR() {
    const qrType = document.getElementById('qrType').value;
    if (!qrType) { alert('Please select QR Code Type'); return; }

    document.getElementById('dlStatus').style.display = 'block';
    document.querySelector('#downloadModal .btn-submit').disabled = true;

    try {
        let merchant_type = "child";
        if (currentType === "Parent") merchant_type = "parent";
        if (currentType === "PRA")    merchant_type = "micro_merchant";

        let payload = { merchant_wallets: selectedWallets, regulation_type: qrType, pdf_type: "" };
        if (currentType !== "PRA") payload.merchant_type = merchant_type;

        const res = await fetch(`${API_BASE}/qr_code/web/v1/bulk/qr-code/download/`, {
            method:  'POST',
            headers: { "authorization": `MERCHANT ${authToken}`, "Content-Type": "application/json" },
            body:    JSON.stringify(payload)
        });

        if (res.ok) {
            const blob = await res.blob();
            const url  = URL.createObjectURL(blob);
            const a    = document.createElement('a');
            a.href     = url;
            a.download = `QR_${currentType}_${Date.now()}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            closeDownloadModal();
            selectedWallets = [];
            updateCount();
            renderTable(allMerchants);
        } else {
            const d = await res.json();
            alert(`Download failed: ${d.message || 'Unknown error'}`);
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }

    document.getElementById('dlStatus').style.display = 'none';
    document.querySelector('#downloadModal .btn-submit').disabled = false;
}

// =============================================
// GENERATE MODAL
// =============================================
function openGenerateModal() {
    if (selectedWallets.length === 0) {
        alert('Please select at least one merchant first.');
        return;
    }
    document.getElementById('generateModal').style.display = 'flex';
}

function closeGenerateModal() {
    document.getElementById('generateModal').style.display = 'none';
}

async function submitGenerate() {
    const qrType = document.getElementById('generateQrType').value;
    let merchant_type = "child";
    if (currentType === "Parent") merchant_type = "parent";
    if (currentType === "PRA")    merchant_type = "micro_merchant";

    let payload = { merchant_wallets: selectedWallets, regulation_type: qrType };
    if (currentType !== "PRA") payload.merchant_type = merchant_type;

    try {
        await fetch(`${API_BASE}/qr_code/web/v1/bulk/qr-code/generate/`, {
            method:  'POST',
            headers: { "authorization": `MERCHANT ${authToken}`, "Content-Type": "application/json" },
            body:    JSON.stringify(payload)
        });
        alert('QR Code generation started successfully!');
        closeGenerateModal();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// =============================================
// PENDING / REJECTED PAGES
// =============================================
async function showOtherPage(type, status, title, bc, event) {
    if (event) event.stopPropagation();

    if (event && event.currentTarget) {
        setActiveNavItem(event.currentTarget);
    }

    otherPageType   = type;
    otherPageStatus = status;

    document.getElementById('otherTitle').textContent      = title;
    document.getElementById('otherBreadcrumb').textContent = bc;
    document.getElementById('transactionSection').style.display = 'none';
    document.getElementById('qrLogSection').style.display       = 'none';
    document.getElementById('otherFilterCard').style.display    = 'block';
    document.getElementById('otherTableCard').style.display     = 'block';
    document.getElementById('otherWalletSearch').value          = '';

    showPage('other');
    await loadOtherPage('');
}
async function loadOtherPage(wallet) {
    const tbody = document.getElementById('otherTableBody');
    tbody.innerHTML = '<tr><td colspan="7" class="table-empty">Loading...</td></tr>';

    try {
        let endpoint = "child_merchant";
        if (otherPageType === "Parent") endpoint = "parent_merchant";
        if (otherPageType === "PRA")    endpoint = "micro_merchant";

        const url = `${API_BASE}/merchant/web/v1/${endpoint}/list/?wallet_number=${wallet}&status=${otherPageStatus}&limit=30&offset=0`;
        const res = await fetch(url, {
            headers: { "authorization": `MERCHANT ${authToken}`, "accept": "application/json" }
        });
        const data    = await res.json();
        otherAllData  = data?.data?.results || [];
        otherCurrentPage = 1;
        renderOtherTable(otherAllData);

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="7" class="table-empty" style="color:#dc3545;">Error loading data</td></tr>';
    }
}

function renderOtherTable(data) {
    const tbody   = document.getElementById('otherTableBody');
    const start   = (otherCurrentPage - 1) * PAGE_SIZE;
    const end     = start + PAGE_SIZE;
    const pageData = data.slice(start, end);
    const total   = data.length;

    tbody.innerHTML = '';

    if (pageData.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="table-empty">No ${otherPageStatus} merchants found</td></tr>`;
        document.getElementById('otherPageInfo').textContent = '0-0 of 0';
        return;
    }

    pageData.forEach(m => {
        const color = m.status === 'Pending' ? '#e6a817' : '#dc3545';
        const tr    = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${m.dba || '—'}</strong></td>
            <td>${m.wallet_number || '—'}</td>
            <td>${m.merchant_id || '—'}</td>
            <td>${m.kam || '—'}</td>
            <td>${m.division || '—'}</td>
            <td>${m.merchant_type || '—'}</td>
            <td><span style="color:${color}; font-weight:600; font-size:12px;">${m.status || '—'}</span></td>
        `;
        tbody.appendChild(tr);
    });

    const from = start + 1;
    const to   = Math.min(end, total);
    document.getElementById('otherPageInfo').textContent = `${from}-${to} of ${total}`;
    updatePaginationBtns(otherCurrentPage, Math.ceil(total / PAGE_SIZE), 'otherPag');
}

async function searchOtherPage() {
    const wallet = document.getElementById('otherWalletSearch').value.trim();
    await loadOtherPage(wallet);
}

function resetOtherPage() {
    document.getElementById('otherWalletSearch').value = '';
    loadOtherPage('');
}

// =============================================
// TRANSACTION HISTORY
// =============================================
async function showTransactionHistory(type,event) {

    if (event && event.currentTarget) {
        setActiveNavItem(event.currentTarget);
    }
    if (event) event.stopPropagation();
    document.getElementById('otherTitle').textContent           = 'Transaction History';
    document.getElementById('otherBreadcrumb').textContent      = 'Transaction History';
    document.getElementById('otherFilterCard').style.display    = 'none';
    document.getElementById('otherTableCard').style.display     = 'none';
    document.getElementById('transactionSection').style.display = 'block';
    document.getElementById('qrLogSection').style.display       = 'none';
    showPage('other');
    generateTransactions();
    renderTransPage(1);
}

function generateTransactions() {
    const types     = ['Payment', 'Refund', 'Transfer', 'Collection'];
    const merchants = [
        'BEST ELECTRONICS-Banani', 'MEENA BAZAR-Gulshan',
        'AARONG-Dhanmondi', 'BURGER KING-Uttara',
        'STEP FOOTWEAR-Mirpur', 'AGORA LIMITED-Sylhet',
        'DAILY SHOPPING-Rajshahi', 'BAY EMPORIUM-Chittagong',
        'BATA SHOE-Khulna', 'GLORIA JEAN S COFFEES-Barishal'
    ];
    const statuses = ['Success', 'Success', 'Success', 'Success', 'Failed', 'Pending'];

    transData = [];
    for (let i = 0; i < 200; i++) {
        const status  = statuses[Math.floor(Math.random() * statuses.length)];
        const amount  = (Math.random() * 50000 + 500).toFixed(2);
        const date    = new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000);
        const dateStr = date.toLocaleDateString('en-GB') + ' ' +
                        date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
        transData.push({
            id:       `TXN${Math.floor(Math.random() * 9000000000 + 1000000000)}`,
            merchant: merchants[Math.floor(Math.random() * merchants.length)],
            wallet:   `18${Math.floor(Math.random() * 90000000 + 10000000)}`,
            amount:   `৳ ${parseFloat(amount).toLocaleString()}`,
            type:     types[Math.floor(Math.random() * types.length)],
            date:     dateStr,
            status:   status
        });
    }
}



function loadTransactions() {
    const tbody     = document.getElementById('transactionBody');
    const types     = ['Payment', 'Refund', 'Transfer', 'Collection'];
    const merchants = [
        'BEST ELECTRONICS-Banani', 'MEENA BAZAR-Gulshan',
        'AARONG-Dhanmondi', 'BURGER KING-Uttara',
        'STEP FOOTWEAR-Mirpur', 'AGORA LIMITED-Sylhet',
        'DAILY SHOPPING-Rajshahi', 'BAY EMPORIUM-Chittagong',
        'BATA SHOE-Khulna', 'GLORIA JEAN S COFFEES-Barishal'
    ];
    const statuses = ['Success', 'Success', 'Success', 'Success', 'Failed', 'Pending'];

    tbody.innerHTML = '';
    for (let i = 0; i < 25; i++) {
        const status  = statuses[Math.floor(Math.random() * statuses.length)];
        const color   = status === 'Success' ? '#17a589' : status === 'Failed' ? '#dc3545' : '#e6a817';
        const amount  = (Math.random() * 50000 + 500).toFixed(2);
        const date    = new Date(Date.now() - Math.random() * 14 * 24 * 60 * 60 * 1000);
        const dateStr = date.toLocaleDateString('en-GB') + ' ' + date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
        const wallet  = `18${Math.floor(Math.random() * 90000000 + 10000000)}`;
        const tr      = document.createElement('tr');
        tr.innerHTML  = `
            <td>TXN${Math.floor(Math.random() * 9000000000 + 1000000000)}</td>
            <td>${merchants[Math.floor(Math.random() * merchants.length)]}</td>
            <td>${wallet}</td>
            <td>৳ ${parseFloat(amount).toLocaleString()}</td>
            <td>${types[Math.floor(Math.random() * types.length)]}</td>
            <td>${dateStr}</td>
            <td><span style="color:${color}; font-weight:600; font-size:12px;">${status}</span></td>
        `;
        tbody.appendChild(tr);
    }
}

// =============================================
// QR DOWNLOAD LOGS
// =============================================
let qrLogsData = [];

function showQRLogs(event) {
    if (event) event.stopPropagation();
    document.getElementById('otherTitle').textContent      = 'QR Download Logs';
    document.getElementById('otherBreadcrumb').textContent = 'QR Download Logs';
    document.getElementById('otherFilterCard').style.display    = 'none';
    document.getElementById('otherTableCard').style.display     = 'none';
    document.getElementById('transactionSection').style.display = 'none';
    document.getElementById('qrLogSection').style.display       = 'block';
    showPage('other');
    generateQRLogs();
    renderQRLogs(1);
}

function generateQRLogs() {
    const merchants = [
        'BEST ELECTRONICS-Banani', 'MEENA BAZAR-Gulshan',
        'AARONG-Dhanmondi', 'BURGER KING-Uttara',
        'STEP FOOTWEAR-Mirpur', 'AGORA LIMITED-Sylhet',
        'DAILY SHOPPING-Rajshahi', 'BAY EMPORIUM-Chittagong',
        'BATA SHOE-Khulna', 'GLORIA JEAN S COFFEES-Barishal'
    ];
    const users    = ['Nurun Naher', 'Sifaul Islam', 'Kamal Hossain', 'Fatema Begum'];
    const statuses = ['Success', 'Success', 'Success', 'Failed'];
    const types    = ['Bangla QR', 'Bangla QR', 'Regular QR'];

    qrLogsData = [];
    for (let i = 0; i < 150; i++) {
        const status  = statuses[Math.floor(Math.random() * statuses.length)];
        const date    = new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000);
        const dateStr = date.toLocaleDateString('en-GB') + ' ' +
                        date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
        const wallet  = `18${Math.floor(Math.random() * 90000000 + 10000000)}`;
        qrLogsData.push({
            id:         `LOG${Math.floor(Math.random() * 900000 + 100000)}`,
            merchant:   merchants[Math.floor(Math.random() * merchants.length)],
            wallet:     wallet,
            qrType:     types[Math.floor(Math.random() * types.length)],
            user:       users[Math.floor(Math.random() * users.length)],
            batchSize:  Math.floor(Math.random() * 29 + 1),
            date:       dateStr,
            status:     status
        });
    }
}

function renderQRLogs(page) {
    const tbody    = document.getElementById('qrLogBody');
    const start    = (page - 1) * PAGE_SIZE;
    const end      = start + PAGE_SIZE;
    const pageData = qrLogsData.slice(start, end);
    const total    = qrLogsData.length;

    tbody.innerHTML = '';
    pageData.forEach(log => {
        const color = log.status === 'Success' ? '#17a589' : '#dc3545';
        const tr    = document.createElement('tr');
        tr.innerHTML = `
            <td>${log.id}</td>
            <td>${log.merchant}</td>
            <td>${log.wallet}</td>
            <td>${log.qrType}</td>
            <td>${log.user}</td>
            <td>${log.batchSize}</td>
            <td>${log.date}</td>
            <td><span style="color:${color}; font-weight:600; font-size:12px;">${log.status}</span></td>
        `;
        tbody.appendChild(tr);
    });

    const from = start + 1;
    const to   = Math.min(end, total);
    document.getElementById('qrLogInfo').textContent = `${from}-${to} of ${total}`;
    updatePaginationBtns(page, Math.ceil(total / PAGE_SIZE), 'qrLogPag');
}

// =============================================
// TRANSACTION HISTORY WITH PAGINATION
// =============================================
let transData = [];

function renderTransPage(page) {
    const tbody    = document.getElementById('transactionBody');
    const start    = (page - 1) * PAGE_SIZE;
    const end      = start + PAGE_SIZE;
    const pageData = transData.slice(start, end);
    const total    = transData.length;

    tbody.innerHTML = '';
    pageData.forEach(t => {
        const color = t.status === 'Success' ? '#17a589' : t.status === 'Failed' ? '#dc3545' : '#e6a817';
        const tr    = document.createElement('tr');
        tr.innerHTML = `
            <td>${t.id}</td>
            <td>${t.merchant}</td>
            <td>${t.wallet}</td>
            <td>${t.amount}</td>
            <td>${t.type}</td>
            <td>${t.date}</td>
            <td><span style="color:${color}; font-weight:600; font-size:12px;">${t.status}</span></td>
        `;
        tbody.appendChild(tr);
    });

    // Add pagination to transaction section
    let transPag = document.getElementById('transPagContainer');
    if (!transPag) {
        const transSection = document.getElementById('transactionSection');
        const pag = document.createElement('div');
        pag.className = 'table-pagination';
        pag.innerHTML = `
            <span>Rows per page: 30</span>
            <span id="transInfo">${start+1}-${Math.min(end,total)} of ${total}</span>
            <div class="pagination-btns" id="transPag"></div>
        `;
        pag.id = 'transPagContainer';
        transSection.querySelector('.table-card').appendChild(pag);
    } else {
        document.getElementById('transInfo').textContent =
            `${start+1}-${Math.min(end,total)} of ${total}`;
    }
    updatePaginationBtns(page, Math.ceil(total / PAGE_SIZE), 'transPag');
}