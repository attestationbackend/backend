# backend.py – Admin C2 Server with username tracking
from flask import Flask, request, jsonify, render_template_string
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# ===== Persistent storage =====
DATA_FILE = "players_data.json"

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

PLAYERS = load_data()   # hwid -> { 'first_seen', 'last_seen', 'status', 'settings_override', 'usernames': [] }

ADMIN_PASSWORD = "admin123"  # CHANGE THIS!

# ===== Helper: unique usernames per HWID =====
def add_username(hwid, username):
    if username and username not in PLAYERS[hwid].get('usernames', []):
        PLAYERS[hwid].setdefault('usernames', []).append(username)

# ============================================
# HTML ADMIN DASHBOARD
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
        .btn-kick:hover { background: #f39c12; }
        .btn-ban:hover { background: #c0392b; }
        .btn-unban:hover { background: #2ecc71; }
        .btn-copy:hover { background: #2980b9; }
        .settings-input { width: 80px; padding: 3px; background: #222; color: #fff; border: 1px solid #555; }
        .settings-btn { padding: 3px 8px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer; }
        .settings-btn:hover { background: #2980b9; }
        .timestamp { color: #888; font-size: 0.8em; }
        .log-hwid { font-family: monospace; }
        .username-list { font-weight: bold; color: #0f0; }
        .copy-tooltip { font-size: 12px; color: #aaa; }
    </style>
    <script>
        function copyHWID(hwid) {
            navigator.clipboard.writeText(hwid).then(() => {
                alert('HWID copied: ' + hwid);
            });
        }
    </script>
</head>
<body>
    <h1>⚡ Attestation C2 Console</h1>
    <p>Active players (last 20s): <span id="active-count">{{ active_players|length }}</span></p>
    <table>
        <thead><tr><th>HWID</th><th>Username(s)</th><th>Last Seen</th><th>Status</th><th>Settings Override</th><th>Actions</th></tr></thead>
        <tbody>
        {% for hwid, data in active_players.items() %}
        <tr class="active">
            <td>
                <code>{{ hwid[:8] }}...{{ hwid[-4:] }}</code>
                <button class="btn btn-copy" onclick="copyHWID('{{ hwid }}')">📋</button>
            </td>
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
            <td>
                <code>{{ hwid[:8] }}...{{ hwid[-4:] }}</code>
                <button class="btn btn-copy" onclick="copyHWID('{{ hwid }}')">📋</button>
            </td>
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

    <h2>👤 Users (by Roblox Username)</h2>
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

    <p style="margin-top:20px;color:#888;">Auto-refreshes every 10 seconds.</p>
    <script>setTimeout(() => location.reload(), 10000);</script>
</body>
</html>
"""

# ============================================
# ADMIN PANEL
# ============================================
@app.route('/admin', methods=['GET'])
def admin_panel():
    pwd = request.args.get('pass')
    if pwd != ADMIN_PASSWORD:
        return "Unauthorized", 401

    now = datetime.now()
    # Active players (last 20 seconds)
    active = {}
    for hwid, data in PLAYERS.items():
        last = datetime.fromisoformat(data['last_seen'])
        if (now - last).total_seconds() <= 20:
            active[hwid] = data

    # All players (for history)
    all_players = PLAYERS.copy()

    # Build users table (by username)
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
            # Update first/last seen based on this HWID
            if data['first_seen'] < users[uname]['first_seen']:
                users[uname]['first_seen'] = data['first_seen']
            if data['last_seen'] > users[uname]['last_seen']:
                users[uname]['last_seen'] = data['last_seen']

    return render_template_string(DASHBOARD_HTML,
                                   active_players=active,
                                   all_players=all_players,
                                   users=users)

# ============================================
# CLIENT API
# ============================================
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    hwid = data.get('hwid')
    username = data.get('username', '')
    if not hwid:
        return jsonify({'error': 'missing hwid'}), 400

    now = datetime.now().isoformat()
    if hwid not in PLAYERS:
        PLAYERS[hwid] = {
            'first_seen': now,
            'last_seen': now,
            'status': 'active',
            'settings_override': {},
            'usernames': [username] if username else []
        }
    else:
        PLAYERS[hwid]['last_seen'] = now
        if username:
            add_username(hwid, username)

    # If status is 'kicked', respond with kicked and then reset to active
    status = PLAYERS[hwid]['status']
    if status == 'kicked':
        response = {'status': 'kicked', 'settings_override': PLAYERS[hwid].get('settings_override', {})}
        PLAYERS[hwid]['status'] = 'active'
        PLAYERS[hwid]['settings_override'] = {}
        save_data(PLAYERS)
        return jsonify(response)

    response = {
        'status': PLAYERS[hwid]['status'],
        'settings_override': PLAYERS[hwid].get('settings_override', {})
    }
    save_data(PLAYERS)
    return jsonify(response)

# ============================================
# ADMIN ACTIONS (unchanged)
# ============================================
@app.route('/admin/ban', methods=['POST'])
def ban_player():
    hwid = request.form.get('hwid')
    if hwid in PLAYERS:
        PLAYERS[hwid]['status'] = 'banned'
        save_data(PLAYERS)
    return '', 204

@app.route('/admin/unban', methods=['POST'])
def unban_player():
    hwid = request.form.get('hwid')
    if hwid in PLAYERS:
        PLAYERS[hwid]['status'] = 'active'
        save_data(PLAYERS)
    return '', 204

@app.route('/admin/kick', methods=['POST'])
def kick_player():
    hwid = request.form.get('hwid')
    if hwid in PLAYERS:
        PLAYERS[hwid]['status'] = 'kicked'
        save_data(PLAYERS)
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
    return '', 204

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
