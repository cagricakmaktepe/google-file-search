import google.generativeai as genai
import inspect

print(f"GenAI Version: {genai.__version__}")
print("dir(genai):", dir(genai))

if hasattr(genai, 'upload_file'):
    print("✅ genai.upload_file exists")
else:
    print("❌ genai.upload_file MISSING")

if hasattr(genai, 'get_file'):
    print("✅ genai.get_file exists")

if hasattr(genai, 'delete_file'):
    print("✅ genai.delete_file exists")

try:
    from google.generativeai import retrieval
    print("✅ retrieval module exists")
except ImportError:
    print("❌ retrieval module MISSING")
