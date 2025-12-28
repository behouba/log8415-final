import requests
import time
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

GATEKEEPER_URL = "http://GATEKEEPER_IP:5000/query"
API_KEY = os.getenv("API_KEY")

def send_query(query, strategy):
    try:
        response = requests.post(
            GATEKEEPER_URL,
            json={"query": query, "strategy": strategy},
            headers={"X-API-Key": API_KEY},
            timeout=10
        )
        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "response_time": response.elapsed.total_seconds()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "response_time": 0
        }

def benchmark_strategy(strategy, num_reads=1000, num_writes=1000):
    print(f"Strategy: {strategy}\n")

    # Read queries
    print(f"Sending {num_reads} READ requests...")
    read_query = "SELECT * FROM actor LIMIT 1"
    read_start = time.time()

    read_results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(send_query, read_query, strategy) for _ in range(num_reads)]
        for future in as_completed(futures):
            read_results.append(future.result())

    read_duration = time.time() - read_start

    # Write queries
    print(f"Sending {num_writes} WRITE requests...")
    write_query = "UPDATE actor SET last_update = NOW() WHERE actor_id = 1"
    write_start = time.time()

    write_results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(send_query, write_query, strategy) for _ in range(num_writes)]
        for future in as_completed(futures):
            write_results.append(future.result())

    write_duration = time.time() - write_start

    # Calculate stats
    read_success = sum(1 for r in read_results if r["success"])
    write_success = sum(1 for w in write_results if w["success"])

    avg_read_time = sum(r["response_time"] for r in read_results if r["success"]) / max(read_success, 1)
    avg_write_time = sum(w["response_time"] for w in write_results if w["success"]) / max(write_success, 1)


    return {
        "strategy": strategy,
        "reads": {
            "total": num_reads,
            "success": read_success,
            "failed": num_reads - read_success,
            "total_time": read_duration,
            "avg_response_time": avg_read_time,
            "throughput": read_success / read_duration
        },
        "writes": {
            "total": num_writes,
            "success": write_success,
            "failed": num_writes - write_success,
            "total_time": write_duration,
            "avg_response_time": avg_write_time,
            "throughput": write_success / write_duration
        }
    }

def main():
    with open('gatekeeper_ip.txt', 'r') as f:
        gatekeeper_ip = f.read().strip()

    global GATEKEEPER_URL
    GATEKEEPER_URL = f"http://{gatekeeper_ip}:5000/query"

    print(f"Gatekeeper URL: {GATEKEEPER_URL}")
    print(f"Starting benchmark...")

    strategies = ["direct_hit", "random", "customized"]
    results = []

    for strategy in strategies:
        result = benchmark_strategy(strategy)
        results.append(result)
        time.sleep(2)

    # Save results
    with open('benchmark_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print("Benchmark completed.")
    print("\nResults saved to benchmark_results.json")

    print("\nSummary:")
    for r in results:
        print(f"  {r['strategy']}: reads={r['reads']['success']}/{r['reads']['total']}, writes={r['writes']['success']}/{r['writes']['total']}")

if __name__ == "__main__":
    main()
