from flask import Flask, request, jsonify
import requests
import re

app = Flask(__name__)

PROXY_HOST = "172.31.37.224"
PROXY_PORT = 5000

# API key for authentication (injected during deployment)
API_KEY = "10820d8b3d3cd2d4baf7263af34cdbc1a727e39f0bc86365"

BLOCKED_PATTERNS = [
    r'\bDROP\s+TABLE\b',
    r'\bDROP\s+DATABASE\b',
    r'\bDELETE\s+FROM\s+\w+\s*;?\s*$',  # match DELETE without WHERE
    r'\bTRUNCATE\b',
]

def is_query_safe(query):
    query_upper = query.upper()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, query_upper, re.IGNORECASE):
            return False
    return True

@app.route('/query', methods=['POST'])
def gateway():
    # Check API key authentication
    api_key = request.headers.get('X-API-Key')
    if api_key != API_KEY:
        return jsonify({"error": "Unauthorized - Invalid or missing API key"}), 401

    data = request.json
    query = data.get('query', '').strip()
    strategy = data.get('strategy', 'direct_hit')

    if not query:
        return jsonify({"error": "No query provided"}), 400

    if not is_query_safe(query):
        return jsonify({"error": "Query blocked for security reasons"}), 403

    # Forward to trusted host (proxy)
    try:
        response = requests.post(
            f"http://{PROXY_HOST}:{PROXY_PORT}/query",
            json={"query": query, "strategy": strategy},
            timeout=30
        )
        return response.json(), response.status_code
    except Exception as e:
        return jsonify({"error": f"Proxy communication failed: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
