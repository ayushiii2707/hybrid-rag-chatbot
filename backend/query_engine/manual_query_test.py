import json
import logging
import os
import sys

# Silence logs during interactive CLI execution to avoid cluttering output
logging.getLogger("verify_query_engine").setLevel(logging.WARNING)
logging.getLogger("query_orchestrator").setLevel(logging.WARNING)
logging.getLogger("query_preprocessor").setLevel(logging.WARNING)
logging.getLogger("answer_extractor").setLevel(logging.WARNING)
logging.getLogger("confidence_scorer").setLevel(logging.WARNING)
logging.getLogger("retrieval_engine").setLevel(logging.WARNING)
logging.getLogger("vector_store").setLevel(logging.WARNING)
logging.getLogger("embedding_generator").setLevel(logging.WARNING)

# ── Bootstrap Paths ───────────────────────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "query_engine"))

try:
    from query_orchestrator import QueryOrchestrator
except ImportError as e:
    print(f"Error: Could not import QueryOrchestrator: {e}")
    sys.exit(1)


def main() -> None:
    print("=" * 80)
    print("  LOCAL RAG SEMANTIC RETRIEVAL SYSTEM — INTERACTIVE CLI TESTING")
    print("=" * 80)
    print("Loading query orchestrator and loading local models... Please wait.")
    
    try:
        orchestrator = QueryOrchestrator()
        print("Model and FAISS Index loaded successfully!")
    except Exception as e:
        print(f"\nCritical Error loading Query Orchestrator: {e}")
        print("Please check if verify_embeddings.py was run to initialize the FAISS index.")
        sys.exit(1)
        
    print("\nType your question below. Type 'exit' to quit the interactive shell.")
    print("=" * 80)

    while True:
        try:
            print()
            query = input("> Enter question: ").strip()
            
            if not query:
                continue
                
            if query.lower() == "exit":
                print("\nExiting interactive CLI. Goodbye!")
                break
                
            # Process query
            res = orchestrator.answer_query(query)
            
            # Print Formatted Results
            print("─" * 80)
            print(f"Corrected Query      : {res['corrected_query']}")
            print(f"Confirmation Suggest?: {'YES' if res['confirmation_required'] else 'NO'}")
            print(f"Answer Found?        : {'YES' if res['answer_found'] else 'NO (Low Confidence)'}")
            print(f"Confidence Score     : {res['confidence']:.4f}")
            
            if res["answer_found"] and res["top_match"]:
                top = res["top_match"]
                print(f"\n[TOP GROUNDED EXCERPT]")
                print(f"Source File   : {top['source_file']}")
                print(f"Page Reference: Page {top['page_number']}")
                print(f"Chunk ID      : {top['chunk_id']}")
                print(f"Match Score   : {top['score']:.4f}")
                print(f"\n\"{top['answer_excerpt'].strip()}\"\n")
            else:
                print(f"\n[TOP GROUNDED EXCERPT]")
                print("No relevant grounded answer excerpt matches the confidence threshold.")
                print("Fallback Warning: No relevant information found in indexed documents.\n")

            if res["other_matches"]:
                print(f"[SECONDARY MATCHES]")
                for i, match in enumerate(res["other_matches"]):
                    print(f"  Match {i+1}: {match['source_file']} (Page {match['page_number']}) [Score: {match['score']:.4f}]")
                    snippet = match['answer_excerpt'].replace('\n', ' ')
                    if len(snippet) > 100:
                        snippet = snippet[:100] + "..."
                    print(f"    Excerpt: \"{snippet}\"")
            print("─" * 80)
            
        except KeyboardInterrupt:
            print("\n\nExiting interactive CLI. Goodbye!")
            break
        except Exception as e:
            print(f"\nError processing query: {e}")


if __name__ == "__main__":
    main()
