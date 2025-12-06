const API_URL = ""; // Empty because frontend/backend are on same server

// --- AUTHENTICATION ---
async function handleAuth(type) {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    let endpoint = type === 'register' ? '/register' : '/login';
    let bodyData = type === 'register' 
        ? JSON.stringify({ email, password }) 
        : new URLSearchParams({ username: email, password: password }); // Login expects form data
    
    let headers = type === 'register' 
        ? { 'Content-Type': 'application/json' }
        : { 'Content-Type': 'application/x-www-form-urlencoded' };

    try {
        const res = await fetch(endpoint, { method: 'POST', headers: headers, body: bodyData });
        const data = await res.json();
        
        if (res.ok) {
            if (type === 'login') {
                localStorage.setItem('token', data.access_token); // Save Token!
                window.location.href = 'dashboard.html';
            } else {
                alert("Registered! Please login.");
                window.location.href = 'login.html';
            }
        } else {
            alert(data.detail);
        }
    } catch (e) { console.error(e); alert("Error connecting to server"); }
}

function logout() {
    localStorage.removeItem('token');
    window.location.href = 'index.html';
}

// --- DASHBOARD FUNCTIONS ---
function getToken() {
    const t = localStorage.getItem('token');
    if (!t) window.location.href = 'login.html'; // Redirect if not logged in
    return t;
}

async function generateProduct() {
    const name = document.getElementById('prodInput').value;
    const token = getToken();

    const res = await fetch('/generate', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}` // Send Token
        },
        body: JSON.stringify({ product_name: name })
    });
    
    const data = await res.json();
    if(res.ok) {
        loadHistory(); // Refresh list
    } else {
        alert("Failed: " + data.detail);
    }
}

async function loadHistory() {
    const token = getToken();
    const res = await fetch('/my-history', {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await res.json();
    
    const grid = document.getElementById('historyGrid');
    grid.innerHTML = data.map(item => `
        <div class="product-card">
            <img src="${item.image_url}">
            <div class="p-content">
                <h3>${item.name}</h3>
                <p style="font-size: 0.8rem; color: #666;">${item.description}</p>
            </div>
        </div>
    `).join('');
}

// --- ADMIN FUNCTIONS ---
async function loadAdminStats() {
    const token = getToken();
    const res = await fetch('/admin/stats', {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (res.status === 403) {
        alert("You are not an Admin!");
        window.location.href = 'dashboard.html';
        return;
    }
    
    const data = await res.json();
    document.getElementById('totalUsers').innerText = data.total_users;
    document.getElementById('totalProds').innerText = data.total_products;
    
    document.getElementById('userList').innerHTML = data.users.map(u => 
        `<li>ID: ${u.id} - ${u.email}</li>`
    ).join('');
                  }

