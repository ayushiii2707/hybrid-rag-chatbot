import json
import sys
from query_engine.query_orchestrator import QueryOrchestrator

def run_query(query):
    orchestrator = QueryOrchestrator()
    result = orchestrator.answer_query(query)
    # Print the entire result JSON
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_query.py \"<query>\"")
        sys.exit(1)
    query = sys.argv[1]
    run_query(query)
