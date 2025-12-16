from flask import Flask, request, jsonify
import pymysql
import random
import subprocess
import time

app = Flask(__name__)


MANAGER_IP = ""
WORKER_IPS = []

DB_USER = "replica_user"
DB_PASS = "replica_password"
DB_NAME = "sakila"

def get_db_connection(ip):
    return pymysql.connect(
        host=ip,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=2,
    )


def ping_time(ip):
    try:
        output = subprocess.check_output(
            ["ping", "-c", "1", "-W", "1", ip],
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )

        if "time=" in output:
            part = output.split("time=")[1]
            ms = part.split(" ")[0]
            return float(ms)
    except Exception:
        return 9999 # Return a high ping time on failure
    return 9999


# Strategies

# Always hit the manager
def strategy_direct_hit():
    return MANAGER_IP 

# Randomly choose between manager and workers
def strategy_random():
    if not WORKER_IPS:
        return MANAGER_IP
    return random.choice(WORKER_IPS)


# Select worker with lowest ping time
def strategy_customized():
    if not WORKER_IPS:
        return MANAGER_IP
    
    best_ip = WORKER_IPS[0]
    best_time = 9999

    for ip in WORKER_IPS:
        t = ping_time(ip)
        print(f"Ping time to {ip}: {t} ms")
        if t < best_time:
            best_time = t
            best_ip = ip
    return best_ip

@app.route('/query', methods=['POST'])
def proxy_query():
    data = request.json
    sql = data.get('query', '').strip()
    strategy = data.get('strategy', 'direct_hit')

    if not sql:
        return jsonify({"error": "No SQL query provided."}), 400
    
    # Determine target IP based on strategy
    is_read = sql.lower().startswith("select")

    target_ip = MANAGER_IP
    node_role = "Manager"

    if is_read:
        if strategy == "random":
            target_ip = strategy_random()
            node_role = "Worder (Random)"
        elif strategy == "customized":
            target_ip = strategy_customized()
            node_role = "Worker (Ping Optimized)"
        else:
            # Default to direct hit
            target_ip = MANAGER_IP
            node_role = "Manager (Direct Hit)"
    else:
        # Writes always go to manager
        target_ip = MANAGER_IP
        node_role = "Manager (Write)"

    # Execute the query
    try:
        conn = get_db_connection(target_ip)
        with conn.cursor() as cursor:
            cursor.execute(sql)
            if is_read:
                result = cursor.fetchall()
            else:
                conn.commit()
                result = {"affected_rows": cursor.rowcount}
        conn.close()

        return jsonify({
            "executed_on": target_ip,
            "role": node_role,
            "strategy": strategy,
            "data": result
        })
    except Exception as e:
        return jsonify({"error": str(e), "node": target_ip}), 500
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
