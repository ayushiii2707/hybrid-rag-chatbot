import os
import sys
import math

# Bootstrap Paths
BACKEND_DIR = "/Users/ayushiranjan/Desktop/Chatbot/backend"
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "retrieval_intelligence"))

from sentence_transformers import CrossEncoder

cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))

chunk_text = """A. Add Delivery Location Process
Step 10: Bank Details
10.1. Fill the correct bank details in this fields.

Account Number
Valid bank account number
IFSC Code
Valid IFSC code of the bank
Bank Name
Automatically fetched from the IFSC
Branch Name
Automatically fetched from the IFSC
Document Type
Select document type used to verify bank details
Bank Document
Upload the scanned copy of document selected in above option"""

queries = [
    "how to input micr code in bank details",
    "how to input micr code in bank details bank routing code magnetic ink character recognition",
    "how to input micr code in bank details ifsc",
    "how to input bank details ifsc",
    "how to input bank details ifsc code",
    "how to register bank details",
    "how to input micr code in bank details ifsc code",
    "how to input ifsc code in bank details",
]

for q in queries:
    logit = cross_encoder.predict((q, chunk_text))
    prob = sigmoid(logit)
    print(f"Query: '{q}'\n  Logit: {logit:.4f} | Prob: {prob:.4f}")
