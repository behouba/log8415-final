# Cloud Design Patterns: Implementing a DB Cluster

## Setup

```bash
# Generate configuration
./setup.sh

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Deploy cluster nodes
python3 main.py

# Setup replication
python3 setup_replication.py

# Launch proxy instance
python3 launch_proxy_instance.py

# Deploy proxy application
python3 deploy_proxy_code.py

# Launch gatekeeper instance
python3 launch_gatekeeper_vm.py

# Deploy gatekeeper application
python3 deploy_gatekeeper_code.py

# Make proxy internal only
python3 secure_proxy.py
```

## Tests

```bash
# Direct Hit (all queries go to Manager)
GATEKEEPER_IP=$(cat gatekeeper_ip.txt) && \
API_KEY=$(grep API_KEY .env | cut -d'=' -f2) && \
curl -s -X POST "http://$GATEKEEPER_IP:5000/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query": "SELECT * FROM actor LIMIT 1", "strategy": "direct_hit"}'

# Random (reads go to random worker)
GATEKEEPER_IP=$(cat gatekeeper_ip.txt) && \
API_KEY=$(grep API_KEY .env | cut -d'=' -f2) && \
curl -s -X POST "http://$GATEKEEPER_IP:5000/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query": "SELECT * FROM actor LIMIT 1", "strategy": "random"}'

# Customized (reads go to lowest-latency worker)
GATEKEEPER_IP=$(cat gatekeeper_ip.txt) && \
API_KEY=$(grep API_KEY .env | cut -d'=' -f2) && \
curl -s -X POST "http://$GATEKEEPER_IP:5000/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query": "SELECT * FROM actor LIMIT 1", "strategy": "customized"}'

# Write operation (always goes to Manager)
GATEKEEPER_IP=$(cat gatekeeper_ip.txt) && \
API_KEY=$(grep API_KEY .env | cut -d'=' -f2) && \
curl -s -X POST "http://$GATEKEEPER_IP:5000/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query": "UPDATE actor SET last_update = NOW() WHERE actor_id = 1", "strategy": "random"}'
```

Security validation:

```bash
# DROP TABLE is blocked
GATEKEEPER_IP=$(cat gatekeeper_ip.txt) && \
API_KEY=$(grep API_KEY .env | cut -d'=' -f2) && \
curl -s -X POST "http://$GATEKEEPER_IP:5000/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query": "DROP TABLE actor", "strategy": "direct_hit"}'

# Request without API key is rejected (returns 401)
GATEKEEPER_IP=$(cat gatekeeper_ip.txt) && \
curl -s -X POST "http://$GATEKEEPER_IP:5000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT 1", "strategy": "direct_hit"}'
```

## Benchmark

1000 read + 1000 write requests for each strategy:

```bash
python3 benchmark.py
```

Results saved to `benchmark_results.json`

## Cleanup

```bash
./cleanup.sh
```
 
