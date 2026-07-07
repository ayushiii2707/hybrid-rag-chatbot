import json
import sys
import os

# Add the backend directory to sys.path for imports
backend_path = os.path.abspath('backend')
sys.path.append(backend_path)

# Import QueryOrchestrator from the query_engine package
from query_engine.query_orchestrator import QueryOrchestrator

def main():
    orchestrator = QueryOrchestrator()
    # Use a concrete query that matches known data
    result = orchestrator.answer_query("What is the link to the supplier registration portal?")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
