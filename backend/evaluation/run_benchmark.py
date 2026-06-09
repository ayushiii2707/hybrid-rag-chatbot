import os
import sys
import csv
import json
import time
import logging

# Bootstrap Paths
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(EVAL_DIR)
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "query_engine"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "retrieval_intelligence"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "security"))

from query_orchestrator import QueryOrchestrator

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("run_benchmark")

def run():
    print("=" * 80)
    print("  RUNNING QUERY BENCHMARKING FRAMEWORK")
    print("=" * 80)

    # 1. Load benchmark queries dataset
    csv_path = os.path.join(EVAL_DIR, "benchmark_queries.csv")
    if not os.path.exists(csv_path):
        print(f"Error: Benchmark queries CSV not found at {csv_path}")
        sys.exit(1)

    queries = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            queries.append(row)

    print(f"Loaded {len(queries)} benchmark queries successfully.")

    # 2. Instantiate QueryOrchestrator
    print("Initializing QueryOrchestrator (please wait)...")
    orchestrator = QueryOrchestrator()
    
    # Non-intrusive configuration: Disable audit logging to avoid polluting DB or JSONL files
    orchestrator.audit_logger = None
    print("Production logging and DB audit trail successfully disabled for benchmarking.")

    # Initialize results containers
    results = []
    category_data = {}
    
    # 3. Process queries deterministically
    print("\nProcessing queries...")
    for idx, item in enumerate(queries):
        query_id = item["query_id"]
        query_text = item["query_text"]
        category = item["category"]
        expected_behavior = item["expected_behavior"]
        
        # Measure latency
        start_time = time.perf_counter()
        response = orchestrator.answer_query(query_text)
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        
        # Extract pipeline indicators
        blocked = response.get("blocked", False)
        answer_found = response.get("answer_found", False)
        synthesized_answer = response.get("synthesized_answer", "")
        message = response.get("message", "")
        confidence = response.get("confidence", 0.0)
        
        # Map output indicators to final action behaviors
        if blocked:
            final_action = "block_query"
        elif answer_found:
            final_action = "retrieve_answer"
        elif "Did you mean:" in synthesized_answer or "Did you mean:" in message:
            final_action = "suggest_query"
        else:
            final_action = "low_confidence_reject"
            
        is_correct = (final_action == expected_behavior)
        
        # Check for specific failure reasons
        failure_reason = None
        if not is_correct:
            if expected_behavior == "block_query" and final_action != "block_query":
                failure_reason = "Malicious query was not blocked by QueryGuard."
            elif expected_behavior == "suggest_query" and final_action != "suggest_query":
                failure_reason = "Typo query failed to trigger the suggestion layer."
            elif expected_behavior == "retrieve_answer" and final_action == "low_confidence_reject":
                failure_reason = f"Procedural or synonym query was rejected due to low confidence ({confidence:.4f})."
            elif expected_behavior == "retrieve_answer" and final_action == "block_query":
                failure_reason = "Valid query was falsely blocked by QueryGuard."
            elif expected_behavior == "low_confidence_reject" and final_action == "retrieve_answer":
                failure_reason = f"Out-of-domain query falsely accepted with confidence ({confidence:.4f})."
            else:
                failure_reason = f"Expected {expected_behavior}, but got final action {final_action}."
        
        # Verify Problem 8 procedural correctness: check for procedural expansion if category is procedural
        if category == "procedural" and is_correct:
            is_expanded = response.get("procedural_expansion", False)
            if not is_expanded:
                # Let's flag this as incomplete or warning, but not fail the accuracy if answer is found,
                # or we can treat it as a warning in failure cases.
                logger.info(f"Query {query_id} retrieved answer but did not trigger procedural expansion.")
        
        # Gather retrieved chunk IDs
        retrieved_chunks = []
        if response.get("top_match"):
            retrieved_chunks.append(response["top_match"]["chunk_id"])
        if response.get("other_matches"):
            retrieved_chunks.extend([m["chunk_id"] for m in response["other_matches"]])
            
        res_entry = {
            "query_id": query_id,
            "query_text": query_text,
            "category": category,
            "expected_behavior": expected_behavior,
            "final_action": final_action,
            "is_correct": is_correct,
            "confidence_score": confidence,
            "latency_ms": latency_ms,
            "retrieved_chunks": retrieved_chunks,
            "failure_reason": failure_reason
        }
        results.append(res_entry)
        
        # Track categories
        if category not in category_data:
            category_data[category] = []
        category_data[category].append(res_entry)
        
        # Light progress indicator
        if (idx + 1) % 10 == 0 or (idx + 1) == len(queries):
            print(f"Processed {idx + 1}/{len(queries)} queries...")

    # 4. Metrics Computation
    per_category_metrics = {}
    overall_correct = 0
    overall_latencies = []
    failure_cases_summary = []
    
    for cat, cat_results in category_data.items():
        total_queries = len(cat_results)
        correct_queries = sum(1 for r in cat_results if r["is_correct"])
        overall_correct += correct_queries
        
        latencies = [r["latency_ms"] for r in cat_results]
        overall_latencies.extend(latencies)
        
        avg_latency = sum(latencies) / total_queries
        min_latency = min(latencies)
        max_latency = max(latencies)
        
        confidences = [r["confidence_score"] for r in cat_results]
        avg_confidence = sum(confidences) / total_queries
        
        accuracy = correct_queries / total_queries
        
        cat_metrics = {
            "total_queries": total_queries,
            "correct_queries": correct_queries,
            "accuracy": accuracy,
            "average_latency_ms": avg_latency,
            "min_latency_ms": min_latency,
            "max_latency_ms": max_latency,
            "average_confidence": avg_confidence
        }
        
        # Specific sub-metric additions as requested
        if cat == "malicious":
            cat_metrics["block_rate_accuracy"] = accuracy  # since correct action is block_query
        elif cat == "typo":
            # suggestion accuracy (expected suggest_query)
            typo_suggest = [r for r in cat_results if r["expected_behavior"] == "suggest_query"]
            if typo_suggest:
                cat_metrics["suggestion_accuracy"] = sum(1 for r in typo_suggest if r["is_correct"]) / len(typo_suggest)
            else:
                cat_metrics["suggestion_accuracy"] = 0.0
                
            # retrieval accuracy (expected retrieve_answer)
            typo_retrieve = [r for r in cat_results if r["expected_behavior"] == "retrieve_answer"]
            if typo_retrieve:
                cat_metrics["retrieval_accuracy"] = sum(1 for r in typo_retrieve if r["is_correct"]) / len(typo_retrieve)
            else:
                cat_metrics["retrieval_accuracy"] = 0.0
        elif cat == "procedural":
            cat_metrics["retrieval_success_rate"] = accuracy
            
        per_category_metrics[cat] = cat_metrics
        
        # Add failures to summary list
        for r in cat_results:
            if not r["is_correct"]:
                failure_cases_summary.append({
                    "query_id": r["query_id"],
                    "query_text": r["query_text"],
                    "category": r["category"],
                    "expected_behavior": r["expected_behavior"],
                    "final_action": r["final_action"],
                    "confidence_score": r["confidence_score"],
                    "latency_ms": r["latency_ms"],
                    "reason": r["failure_reason"]
                })

    # Overall metrics
    total_queries = len(queries)
    overall_accuracy = overall_correct / total_queries
    avg_overall_latency = sum(overall_latencies) / total_queries
    min_overall_latency = min(overall_latencies)
    max_overall_latency = max(overall_latencies)
    
    overall_metrics = {
        "total_queries": total_queries,
        "correct_queries": overall_correct,
        "overall_accuracy": overall_accuracy,
        "average_overall_latency_ms": avg_overall_latency
    }
    
    latency_summary = {
        "overall": {
            "average_ms": avg_overall_latency,
            "min_ms": min_overall_latency,
            "max_ms": max_overall_latency
        },
        "per_category": {cat: {"average_ms": metrics["average_latency_ms"], "min_ms": metrics["min_latency_ms"], "max_ms": metrics["max_latency_ms"]} for cat, metrics in per_category_metrics.items()}
    }
    
    report = {
        "per_category_metrics": per_category_metrics,
        "overall_metrics": overall_metrics,
        "failure_cases_summary": failure_cases_summary,
        "latency_summary": latency_summary
    }

    # 5. Output Report to JSON
    report_path = os.path.join(EVAL_DIR, "benchmark_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        
    print("\n" + "=" * 80)
    print("  BENCHMARK SUMMARY REPORT")
    print("=" * 80)
    print(f"Overall Accuracy : {overall_accuracy * 100:.2f}% ({overall_correct}/{total_queries})")
    print(f"Overall Avg Latency : {avg_overall_latency:.2f} ms")
    print("-" * 80)
    for cat, metrics in per_category_metrics.items():
        print(f"Category '{cat}':")
        print(f"  Accuracy       : {metrics['accuracy'] * 100:.2f}%")
        print(f"  Avg Latency    : {metrics['average_latency_ms']:.2f} ms")
        print(f"  Avg Confidence : {metrics['average_confidence']:.4f}")
        if "block_rate_accuracy" in metrics:
            print(f"  Block Rate Acc : {metrics['block_rate_accuracy'] * 100:.2f}%")
        if "suggestion_accuracy" in metrics:
            print(f"  Suggestion Acc : {metrics['suggestion_accuracy'] * 100:.2f}%")
        if "retrieval_accuracy" in metrics:
            print(f"  Retrieval Acc  : {metrics['retrieval_accuracy'] * 100:.2f}%")
        if "retrieval_success_rate" in metrics:
            print(f"  Retrieval Rate : {metrics['retrieval_success_rate'] * 100:.2f}%")
        print("-" * 80)
        
    print(f"Report JSON written to: {report_path}")
    print(f"Total failure cases captured: {len(failure_cases_summary)}")
    print("=" * 80)

if __name__ == "__main__":
    run()
