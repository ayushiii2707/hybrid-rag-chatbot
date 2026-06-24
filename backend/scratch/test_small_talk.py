import sys
sys.path.append('/Users/ayushiranjan/Desktop/Chatbot/backend')
from query_engine.query_orchestrator import QueryOrchestrator

orchestrator = QueryOrchestrator()
res = orchestrator._handle_small_talk("good morning how r u")
print("Response:", res)
