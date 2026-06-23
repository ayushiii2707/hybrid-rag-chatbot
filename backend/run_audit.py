import json
import logging
from query_engine.query_orchestrator import QueryOrchestrator
from query_engine.context_assembler import classify_query_granularity
from query_engine.answer_extractor import AnswerExtractor


def run_audit(query: str):
    qo = QueryOrchestrator()
    # Preprocess
    prep = qo.preprocessor.preprocess_query(query)
    corrected = prep["corrected_query"]
    granularity = classify_query_granularity(corrected)
    # Retrieval
    retrieval_q = qo.preprocessor.expand_synonyms(corrected)
    candidates = qo.retrieval_engine.retrieve_best_chunk(
        retrieval_q, top_k=qo.retrieval_top_k, original_query=corrected
    )
    # Print retrieved candidates with required fields
    print("--- Retrieved Candidates ---")
    for cand in candidates:
        chunk_id = cand.get('chunk_id')
        metadata = cand.get('metadata', {})
        procedure_id = metadata.get('procedure_id')
        score = cand.get('score')
        text = cand.get('text', '')
        print(f"chunk_id: {chunk_id}")
        print(f"procedure_id: {procedure_id}")
        print(f"score: {score}")
        print(f"text: {text[:200]}...\n")
    # Select top candidate for answer extraction
    top_candidate = candidates[0] if candidates else None
    if top_candidate:
        extractor = AnswerExtractor(generator=qo.retrieval_engine.generator)
        excerpt_res = extractor.extract_answer_excerpt(
            qo.retrieval_engine.generator.generate_embeddings([retrieval_q])[0],
            top_candidate.get('text', '')
        )
        print("--- AnswerExtractor Output ---")
        print(f"input_context (first 200 chars): {top_candidate.get('text','')[:200]}...")
        print(f"selected_answer_span: {excerpt_res['excerpt']}")
    # Context Assembly selection
    is_procedural = granularity in ("procedural", "workflow")
    if not is_procedural:
        assembly_candidates = [top_candidate] if top_candidate else []
    else:
        assembly_candidates = candidates
    assembly_result = qo.context_assembler.assemble(corrected, assembly_candidates, query_granularity=granularity)
    # Print ContextAssembler outputs
    print("--- ContextAssembler Output ---")
    print("selected_chunks object:")
    print(json.dumps(assembly_candidates, indent=2))
    print("context_string object:")
    print(assembly_result.get('assembled_context'))
    # Final response using orchestrator for completeness
    final_resp = qo.answer_query(query)
    print("--- Final Response ---")
    print(json.dumps(final_resp, indent=2))

if __name__ == "__main__":
    run_audit("where to click for new registration")
