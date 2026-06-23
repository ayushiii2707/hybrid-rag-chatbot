import sys, json, copy, importlib

# Ensure the correct ContextAssembler module is loaded before QueryOrchestrator imports it.
# The QueryOrchestrator does "from context_assembler import ContextAssembler, ..." which currently resolves to the wrong file.
# Pre‑load the proper module from the query_engine package and register it under the name "context_assembler".

# Import the correct ContextAssembler implementation
correct_ca = importlib.import_module('query_engine.context_assembler')
# Insert into sys.modules under the expected import name
sys.modules['context_assembler'] = correct_ca

# Now import the orchestrator safely
from query_engine.query_orchestrator import QueryOrchestrator

pre_sort = None
post_sort = None

def trace_func(frame, event, arg):
    global pre_sort, post_sort
    if event == 'line' and frame.f_code.co_name == 'answer_query':
        lineno = frame.f_lineno
        # The original source has the sort at line 458 (pre‑sort) and 459 (post‑sort).
        # Capture just before and just after the sort operation.
        if lineno == 458:
            pre_sort = copy.deepcopy(frame.f_locals.get('evaluated_matches'))
        if lineno == 459:
            post_sort = copy.deepcopy(frame.f_locals.get('evaluated_matches'))
    return trace_func

sys.settrace(trace_func)

# Execute the query
qo = QueryOrchestrator()
response = qo.answer_query("where to click for new registration")

sys.settrace(None)

def tie_breaker_key(match):
    score = match.get('score', 0)
    breakdown = match.get('breakdown') or {}
    semantic = breakdown.get('semantic', 0.0)
    excerpt_lower = (match.get('answer_excerpt') or '').lower()
    explicit_phrasing = sum(1 for marker in ["is", "refers to", "exactly", "must be", "ensure", "please", "should", "rule"] if marker in excerpt_lower)
    excerpt_len = len(match.get('answer_excerpt') or '')
    return (-score, -semantic, -explicit_phrasing, excerpt_len)

def format_matches(lst):
    out = []
    for m in lst:
        out.append({
            'chunk_id': m.get('chunk_id'),
            'score': m.get('score'),
            'semantic': (m.get('breakdown') or {}).get('semantic'),
            'answer_excerpt': m.get('answer_excerpt'),
            'tie_key': tie_breaker_key(m)
        })
    return out

print("--- BEFORE SORT ---")
print(json.dumps(format_matches(pre_sort), indent=2))
print("--- AFTER SORT ---")
print(json.dumps(format_matches(post_sort), indent=2))
print("--- FINAL RESPONSE (partial) ---")
print(json.dumps({k: response[k] for k in ['answer_found', 'top_match'] if k in response}, indent=2))
