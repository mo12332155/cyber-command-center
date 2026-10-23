
from flask import Flask, jsonify, render_template
import psutil
import platform
import socket
from datetime import datetime
from database import init_db, get_connection


app = Flask(__name__)
init_db()


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/system")
def system_info():
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\\\")

    data = {
        "hostname": socket.gethostname(),
        "operating_system": platform.system(),
        "windows_version": platform.version(),
        "cpu_percent": psutil.cpu_percent(interval=0.3),
        "ram_percent": memory.percent,
        "ram_total_gb": round(memory.total / (1024 ** 3), 2),
        "ram_available_gb": round(memory.available / (1024 ** 3), 2),
        "disk_percent": disk.percent,
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
        "disk_free_gb": round(disk.free / (1024 ** 3), 2),
        "uptime_hours": round(
            (datetime.now().timestamp() - psutil.boot_time()) / 3600, 2
        ),
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    return jsonify(data)


@app.route("/api/processes")
def process_list():
    processes = []

    for proc in psutil.process_iter():
        try:
            info = proc.as_dict(
                attrs=["pid", "name", "memory_percent", "status"]
            )
            processes.append({
                "pid": info["pid"],
                "name": info["name"] or "Unknown",
                "memory_percent": round(
                    info["memory_percent"] or 0, 2
                ),
                "status": info["status"] or "unknown"
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(
        key=lambda p: p["memory_percent"],
        reverse=True
    )

    return jsonify({"processes": processes[:20]})



@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT id, alert_type, message, value, created_at
            FROM alerts
            ORDER BY id DESC
            LIMIT 100
        """).fetchall()

    return jsonify({
        "alerts": [dict(row) for row in rows]
    })


@app.route("/api/alerts", methods=["POST"])
def create_alert():
    from flask import request

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"error": "Expected a JSON object"}), 400

    alert_type = payload.get("alert_type")
    message = payload.get("message")
    value = payload.get("value")

    if alert_type not in ("CPU", "RAM", "SYSTEM"):
        return jsonify({"error": "Invalid alert_type"}), 400

    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "message is required"}), 400

    if value is not None and (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        return jsonify({"error": "value must be numeric or null"}), 400

    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO alerts (alert_type, message, value)
            VALUES (?, ?, ?)
        """, (alert_type, message.strip(), value))

        alert_id = cursor.lastrowid

        row = connection.execute("""
            SELECT id, alert_type, message, value, created_at
            FROM alerts
            WHERE id = ?
        """, (alert_id,)).fetchone()

    return jsonify(dict(row)), 201



if __name__ == "__main__":
    print("Cyber Command Center is starting...")
    print("Open http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
