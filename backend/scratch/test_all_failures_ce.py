import os
import sys
import math
import json

# Bootstrap Paths
BACKEND_DIR = "/Users/ayushiranjan/Desktop/Chatbot/backend"
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "retrieval_intelligence"))

from sentence_transformers import CrossEncoder

cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))

# Load chunks from metadata.json
with open("/Users/ayushiranjan/Desktop/Chatbot/backend/embeddings/metadata.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

chunks_by_id = {c["chunk_id"]: c for c in chunks}

# Target chunks for failures
# Q022 / Q053: Add Delivery Location manual Step 10 Bank Details
bank_chunk = chunks_by_id["3b97da58a590c41e2833e6360925ec9dc0349b82e177e1dadba8fbd85a089d57_c28"]

# Q026: Add Delivery Location manual intro (c3) or check status report (B. Steps to Check the Status...)
# B. Steps to Check... is c32. Let's find it.
status_chunk = None
for c in chunks:
    if "status report" in c["text"].lower() and "delivery location" in c["text"].lower():
        status_chunk = c
        break
if not status_chunk:
    status_chunk = chunks_by_id["3b97da58a590c41e2833e6360925ec9dc0349b82e177e1dadba8fbd85a089d57_c3"]

# Q028: registration manual check status report or active/inactive
# Q029: registration manual submit application (Step 7 or submit form)
submit_chunk = None
for c in chunks:
    if "step 7" in c["text"].lower() and "request id" in c["text"].lower():
        submit_chunk = c
        break

# Q052 / Q068: registration manual Step 2: Supplier PAN details
pan_chunk = None
for c in chunks:
    if "step 2" in c["text"].lower() and "pan" in c["text"].lower():
        pan_chunk = c
        break

# Q059: registration manual Step 4: Contact Details
contact_chunk = None
for c in chunks:
    if "step 4" in c["text"].lower() and "contact" in c["text"].lower():
        contact_chunk = c
        break

# Q060 / Q062: registration manual Step 2 or GSTIN details in Delivery Location manual Step 6
gst_chunk = None
for c in chunks:
    if "step 6" in c["text"].lower() and "gstin" in c["text"].lower():
        gst_chunk = c
        break

# Q066: Add Delivery Location manual Step 9 FSSAI Details
fssai_chunk = None
for c in chunks:
    if "step 9" in c["text"].lower() and "fssai" in c["text"].lower():
        fssai_chunk = c
        break

print("=== Q022 & Q053: Bank Routing / MICR ===")
for q in ["what are the requirements for specifying bank routing codes", 
          "what are the requirements for specifying bank routing codes bank routing codes micr ifsc code", 
          "what are the requirements for specifying bank routing codes ifsc code bank details"]:
    prob = sigmoid(cross_encoder.predict((q, bank_chunk["text"])))
    print(f"  Query: '{q}' -> Prob: {prob:.4f}")

print("\n=== Q026: Delivery Location Status Report ===")
for q in ["how to check status report for delivery location", 
          "how to check status report for delivery location status report delivery location",
          "how to check status report for delivery location check the status of vendor registration"]:
    prob = sigmoid(cross_encoder.predict((q, status_chunk["text"])))
    print(f"  Query: '{q}' -> Prob: {prob:.4f}")

print("\n=== Q028: Vendor Status Active/Inactive ===")
# Let's find correct chunk first
vendor_status_chunk = None
for c in chunks:
    if "status report" in c["text"].lower() and "dropdown menu" in c["text"].lower():
        vendor_status_chunk = c
        break
if vendor_status_chunk:
    for q in ["how to check if vendor status is active or inactive", 
              "how to check if vendor status is active or inactive status report delivery location",
              "how to check if vendor status is active or inactive status of vendor registration active inactive"]:
        prob = sigmoid(cross_encoder.predict((q, vendor_status_chunk["text"])))
        print(f"  Query: '{q}' -> Prob: {prob:.4f}")

print("\n=== Q029: Submit Onboarding Application ===")
# Let's find Step 7: Request ID chunk
req_id_chunk = None
for c in chunks:
    if "step 7: request id" in c["text"].lower():
        req_id_chunk = c
        break
if req_id_chunk:
    for q in ["how do i submit onboarding application after finishing all sections", 
              "how do i submit onboarding application after finishing all sections request id generation approval",
              "how do i submit onboarding application after finishing all sections submit form confirmation"]:
        prob = sigmoid(cross_encoder.predict((q, req_id_chunk["text"])))
        print(f"  Query: '{q}' -> Prob: {prob:.4f}")

print("\n=== Q052 & Q068: PAN Details ===")
if pan_chunk:
    for q in ["documentation guidelines for uploading national identity card numbers", 
              "documentation guidelines for uploading national identity card numbers supplier pan details permanent account number",
              "pan identification page entry rules",
              "pan identification page entry rules supplier pan details permanent account number"]:
        prob = sigmoid(cross_encoder.predict((q, pan_chunk["text"])))
        print(f"  Query: '{q}' -> Prob: {prob:.4f}")

print("\n=== Q059: Contact Detail Fields ===")
if contact_chunk:
    for q in ["how do we assign contact detail fields", 
              "how do we assign contact detail fields contact details contact information"]:
        prob = sigmoid(cross_encoder.predict((q, contact_chunk["text"])))
        print(f"  Query: '{q}' -> Prob: {prob:.4f}")

print("\n=== Q062: Tax Identification Data ===")
if gst_chunk:
    for q in ["instructions for entering tax identification data", 
              "instructions for entering tax identification data gstin details bank account"]:
        prob = sigmoid(cross_encoder.predict((q, gst_chunk["text"])))
        print(f"  Query: '{q}' -> Prob: {prob:.4f}")

print("\n=== Q066: FSSAI Safety License ===")
if fssai_chunk:
    for q in ["verification link for safety license of food products", 
              "verification link for safety license of food products fssai details active inactive status portal link"]:
        prob = sigmoid(cross_encoder.predict((q, fssai_chunk["text"])))
        print(f"  Query: '{q}' -> Prob: {prob:.4f}")
