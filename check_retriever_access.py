import os
import google.generativeai as genai
from google.ai.generativelanguage import RetrieverServiceClient
from google.api_core.client_options import ClientOptions
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('GOOGLE_API_KEY')

if not API_KEY:
    print("❌ API Key missing")
    exit(1)

# Configure the lower-level client
try:
    client = RetrieverServiceClient(
        client_options=ClientOptions(api_key=API_KEY)
    )
    print("✅ RetrieverServiceClient initialized")
    
    # Test listing corpora to verify access
    request = {"page_size": 10}
    try:
        response = client.list_corpora(request=request)
        print("✅ API Connection successful. Found Corpora:")
        for corpus in response.corpora:
            print(f"   - {corpus.name} ({corpus.display_name})")
    except Exception as e:
        print(f"❌ Error listing corpora: {e}")
        
except Exception as e:
    print(f"❌ Failed to initialize client: {e}")
