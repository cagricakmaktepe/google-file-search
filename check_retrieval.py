import google.generativeai as genai
import inspect

print("Checking for Corpus/Retrieval methods...")

if hasattr(genai, 'create_corpus'):
    print("✅ genai.create_corpus exists")
else:
    print("❌ genai.create_corpus MISSING")

if hasattr(genai, 'create_document'):
    print("✅ genai.create_document exists")

# Check if it's hidden under a submodule
try:
    from google.generativeai import retrieval
    print("✅ google.generativeai.retrieval imported")
    print(dir(retrieval))
except ImportError:
    print("❌ google.generativeai.retrieval ImportError")

# Check for tools in model
try:
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("Model methods:", dir(model))
except:
    pass

