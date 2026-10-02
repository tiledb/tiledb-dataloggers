from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify, session
import subprocess
import configparser
import os
import psutil


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")

config = configparser.ConfigParser()
config.read(CONFIG_PATH)

def reload_config():
    config.read(CONFIG_PATH)

reload_config()

app = Flask(__name__)
app.secret_key = config["app"]["secret_key"]


def system_stats():
    return {
        "cpu": psutil.cpu_percent(interval=0),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent
    }



# ---------------- CONFIG HELPERS ----------------

def save_config():
    with open(CONFIG_PATH, "w") as f:
        config.write(f)

def get_services():
    return [
        s.strip()
        for s in config["services"]["list"].splitlines()
        if s.strip()
    ]

def feature_enabled(name):
    return config["features"].getboolean(name, fallback=False)

def auth_enabled():
    return config["auth"].getboolean("enabled", fallback=False)

# ---------------- AUTH ----------------

@app.before_request
def require_login():
    if auth_enabled():
        if request.endpoint not in ("login", "static"):
            if not session.get("logged_in"):
                return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if not auth_enabled():
        return redirect(url_for("index"))

    if request.method == "POST":
        if (request.form["username"] == config["auth"]["username"] and
            request.form["password"] == config["auth"]["password"]):
            session["logged_in"] = True
            return redirect(url_for("index"))
        flash("Invalid credentials", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- SYSTEM ----------------

ALLOWED_ACTIONS = ["start", "stop", "restart", "enable", "disable"]

def run_cmd(cmd, server="local"):
    if server != "local":
        ssh_target = config["servers"][server]
        cmd = ["ssh", ssh_target] + cmd
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def get_status(service):
    stdout, _, _ = run_cmd([
        "systemctl",
        "show",
        service,
        "--property=ActiveState",
        "--property=UnitFileState",
        "--no-page"
    ])

    active = "unknown"
    enabled = "unknown"

    for line in stdout.splitlines():
        if line.startswith("ActiveState="):
            active = line.split("=")[1]
        elif line.startswith("UnitFileState="):
            enabled = line.split("=")[1]

    return {"active": active, "enabled": enabled}



def validate_service(service):
    if service not in get_services():
        abort(403)

# ---------------- WEB UI ----------------

@app.route("/")
def index():
    services = [
        s.strip()
        for s in config["services"]["list"].splitlines()
        if s.strip()
    ]

    statuses = {}
    for svc in services:
        active, _, _ = run_cmd(["systemctl", "is-active", svc])
        enabled, _, _ = run_cmd(["systemctl", "is-enabled", svc])
        statuses[svc] = {"active": active, "enabled": enabled}

    return render_template(
        "index.html",
        statuses=statuses,
        config=config
    )

@app.route("/api/all_status")
def api_all_status():
    services = get_services()
    data = {}
    for svc in services:
        data[svc] = get_status(svc)
    return jsonify(data)



@app.route("/action", methods=["POST"])
def action():
    service = request.form.get("service")
    action = request.form.get("action")

    validate_service(service)

    if action not in ALLOWED_ACTIONS:
        abort(403)

    run_cmd(["systemctl", action, service])
    return redirect(url_for("index"))

@app.route("/logs/<service>")
def logs(service):
    validate_service(service)

    logs, _, _ = run_cmd([
        "journalctl", "-u", service, "-n", "100", "--no-pager"
    ])

    return render_template(
        "logs.html",
        service=service,
        logs=logs,
        live_logs=feature_enabled("live_logs")
    )

@app.route("/logs_stream/<service>")
def logs_stream(service):
    services = get_services()
    if service not in services:
        abort(403)

    logs, _, _ = run_cmd([
        "journalctl",
        "-u", service,
        "-n", "50",
        "--no-pager"
    ])
    return jsonify({"logs": logs})


# ---------------- API ----------------

@app.route("/api/system")
def api_system():
    if not config["features"].getboolean("system_monitoring"):
        abort(403)

    return jsonify(system_stats())



@app.route("/api/status/<service>")
def api_status(service):
    if not feature_enabled("api_enabled"):
        abort(403)

    validate_service(service)
    return jsonify(get_status(service))

@app.route("/api/<action>/<service>", methods=["POST"])
def api_action(action, service):
    if not feature_enabled("api_enabled"):
        abort(403)

    validate_service(service)

    if action not in ALLOWED_ACTIONS:
        abort(403)

    stdout, stderr, code = run_cmd(["systemctl", action, service])

    return jsonify({
        "service": service,
        "action": action,
        "return_code": code,
        "stdout": stdout,
        "stderr": stderr
    })

# ---------------- CONFIG EDITOR ----------------

@app.route("/config", methods=["GET", "POST"])
def config_editor():
    if not feature_enabled("config_editor"):
        abort(403)

    if request.method == "POST":
        config["features"]["api_enabled"] = str("api_enabled" in request.form).lower()
        config["features"]["live_logs"] = str("live_logs" in request.form).lower()
        config["features"]["auto_refresh"] = str("auto_refresh" in request.form).lower()
        config["features"]["config_editor"] = str("config_editor" in request.form).lower()

        config["auth"]["enabled"] = str("auth_enabled" in request.form).lower()
        config["auth"]["username"] = request.form["username"]
        config["auth"]["password"] = request.form["password"]

        config["services"]["list"] = request.form["services"]

        save_config()
        reload_config()

        flash("Configuration updated", "success")
        return redirect(url_for("config_editor"))

    return render_template("config.html", config=config)

# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(
        host=config["app"].get("host", "0.0.0.0"),
        port=config["app"].getint("port", 8080)
    )
