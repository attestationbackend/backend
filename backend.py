# backend.py – Admin C2 Server for Attestation ESP
from flask import Flask, request, jsonify, render_template_string
import json
from datetime import datetime

app = Flask(__name__)

# In-memory storage (bans reset on restart – save to file if needed)
PLAYERS = {}  # hwid -> { 'last_seen': timestamp, 'status': 'active'|'banned', 'settings_override': {} }

ADMIN_PASSWORD = "admin123"  # CHANGE THIS!

# ========== HTML DASHBOARD ==========
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>ESP C2 Admin Panel</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial; background: #0d0d0d; color: #eee; padding: 20px; }
        h1 { color: #00ff00; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { padding: 10px; border: 1px solid #333; text-align: left; }
        th { background: #1a1a1a; color: #0f0; }
        .banned { background: #2a0a0a; color: #ff4444; }
        .active { background: #0a2a0a; color: #44ff44; }
        .btn { padding: 5px 12px; border: none; border-radius: 4px; cursor: pointer; }
        .btn-kick { background: #e67e22; color: white; }
        .btn-ban { background: #e74c3c; color: white; }
        .btn-unban { background: #27ae60; color: white; }
        .btn-kick:hover { background: #f39c12; }
        .btn-ban:hover { background: #c0392b; }
        .btn-unban:hover { background: #2ecc71; }
        .settings-input { width: 80px; padding: 3px; background: #222; color: #fff; border: 1px solid #555; }
        .settings-btn { padding: 3px 8px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer; }
        .settings-btn:hover { background: #2980b9; }
    </style>
</head>
<body>
    <h1>⚡ Attestation C2 Console</h1>
    <p>Total players online: <span id="count">{{ players|length }}</span></p>
    <table>
        <thead>
            <tr><th>HWID</th><th>Last Seen</th><th>Status</th><th>Settings Override</th><th>Actions</th></tr>
        </thead>
        <tbody>
            {% for hwid, data in players.items() %}
            <tr class="{{ 'banned' if data.status == 'banned' else 'active' }}">
                <td><code>{{ hwid[:8] }}...{{ hwid[-4:] }}</code></td>
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
    <p style="margin-top:20px;color:#888;">Auto-refreshes every 10 seconds.</p>
    <script>setTimeout(() => location.reload(), 10000);</script>
</body>
</html>
"""

@app.route('/admin', methods=['GET'])
def admin_panel():
    pwd = request.args.get('pass')
    if pwd != ADMIN_PASSWORD:
        return "Unauthorized", 401
    return render_template_string(DASHBOARD_HTML, players=PLAYERS)

# ========== CLIENT API ==========
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    hwid = data.get('hwid')
    if not hwid:
        return jsonify({'error': 'missing hwid'}), 400

    now = datetime.now().strftime("%H:%M:%S")
    if hwid not in PLAYERS:
        PLAYERS[hwid] = {
            'last_seen': now,
            'status': 'active',
            'settings_override': {}
        }
    else:
        PLAYERS[hwid]['last_seen'] = now

    player = PLAYERS[hwid]
    response = {
        'status': player['status'],
        'settings_override': player.get('settings_override', {})
    }
    return jsonify(response)

# ========== ADMIN ACTIONS ==========
@app.route('/admin/ban', methods=['POST'])
def ban_player():
    hwid = request.form.get('hwid')
    if hwid in PLAYERS:
        PLAYERS[hwid]['status'] = 'banned'
    return '', 204

@app.route('/admin/unban', methods=['POST'])
def unban_player():
    hwid = request.form.get('hwid')
    if hwid in PLAYERS:
        PLAYERS[hwid]['status'] = 'active'
    return '', 204

@app.route('/admin/kick', methods=['POST'])
def kick_player():
    hwid = request.form.get('hwid')
    if hwid in PLAYERS:
        PLAYERS[hwid]['status'] = 'kicked'
    return '', 204

@app.route('/admin/settings', methods=['POST'])
def set_settings():
    hwid = request.form.get('hwid')
    setting = request.form.get('setting')
    value = request.form.get('value')
    if hwid in PLAYERS and setting and value:
        # Convert string to bool/int if possible
        if value.lower() == 'true':
            value = True
        elif value.lower() == 'false':
            value = False
        elif value.isdigit():
            value = int(value)
        PLAYERS[hwid]['settings_override'] = {'setting': setting, 'value': value}
    return '', 204

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)