import os
import time
from google.ai.generativelanguage import RetrieverServiceClient
from google.ai.generativelanguage import CreateCorpusRequest, CreateDocumentRequest, CreateChunkRequest
from google.ai.generativelanguage import Corpus, Document, Chunk
from google.ai.generativelanguage import QueryCorpusRequest
from google.api_core.client_options import ClientOptions
from google.protobuf import field_mask_pb2

class RAGManager:
    def __init__(self, api_key):
        self.client = RetrieverServiceClient(
            client_options=ClientOptions(api_key=api_key)
        )
        self.api_key = api_key

    def get_or_create_corpus(self, display_name="Video Library"):
        """
        Get existing corpus or create a new one
        """
        # List existing corpora
        try:
            # Note: page_size limit is often small (e.g. 10 or 20)
            response = self.client.list_corpora(request={"page_size": 10})
            for corpus in response.corpora:
                if corpus.display_name == display_name:
                    print(f"✅ Found existing corpus: {corpus.name}")
                    return corpus.name
        except Exception as e:
            print(f"⚠️ Error listing corpora: {e}")

        # Create new corpus
        try:
            print(f"🆕 Creating new corpus: {display_name}")
            corpus = Corpus(display_name=display_name)
            request = CreateCorpusRequest(corpus=corpus)
            response = self.client.create_corpus(request=request)
            print(f"✅ Created corpus: {response.name}")
            return response.name
        except Exception as e:
            print(f"❌ Error creating corpus: {e}")
            return None

    def create_document(self, corpus_name, doc_display_name, metadata=None):
        """
        Create a document entry in the corpus
        """
        try:
            document = Document(display_name=doc_display_name)
            if metadata:
                # Add metadata support if needed (requires Metadata proto)
                pass
                
            request = CreateDocumentRequest(parent=corpus_name, document=document)
            response = self.client.create_document(request=request)
            return response.name
        except Exception as e:
            print(f"❌ Error creating document {doc_display_name}: {e}")
            return None

    def ingest_text(self, document_name, text_content, chunk_size=2000):
        """
        Ingest text into a document by creating chunks
        """
        # Simple chunking logic
        chunks = []
        for i in range(0, len(text_content), chunk_size):
            chunk_text = text_content[i:i + chunk_size]
            chunk = Chunk(data={'string_value': chunk_text})
            chunks.append(chunk)

        # Batch create chunks (max 100 per batch usually)
        # Note: The API technically supports batch_create_chunks, but for simplicity
        # and stability with this version, we'll iterate or use single create if batch fails.
        
        count = 0
        for chunk in chunks:
            try:
                request = CreateChunkRequest(parent=document_name, chunk=chunk)
                self.client.create_chunk(request=request)
                count += 1
                if count % 10 == 0:
                    print(".", end="", flush=True)
            except Exception as e:
                print(f"⚠️ Error creating chunk: {e}")
        
        print(f"\n✅ Ingested {count} chunks for {document_name}")
        return count

    def query(self, corpus_name, query_text, limit=5):
        """
        Semantic search against the corpus
        """
        try:
            request = QueryCorpusRequest(
                name=corpus_name,
                query=query_text,
                results_count=limit
            )
            response = self.client.query_corpus(request=request)
            
            results = []
            for chunk in response.relevant_chunks:
                score = chunk.chunk_relevance_score
                text = chunk.chunk.data.string_value
                results.append({'text': text, 'score': score})
                
            return results
        except Exception as e:
            print(f"❌ Error querying corpus: {e}")
            return []

    def list_documents(self, corpus_name):
        """
        List all documents in the corpus
        """
        try:
            # We need to use the DocumentService to list documents
            # But the RetrieverServiceClient also has list_documents
            request = {"parent": corpus_name, "page_size": 100}
            response = self.client.list_documents(request=request)
            
            docs = []
            for doc in response.documents:
                docs.append({
                    'name': doc.name,
                    'display_name': doc.display_name
                })
            return docs
        except Exception as e:
            print(f"❌ Error listing documents: {e}")
            return []

    def delete_document(self, document_name):
        """
        Delete a specific document
        """
        try:
            # document_name format: corpora/corpus-id/documents/doc-id
            request = {"name": document_name, "force": True}
            self.client.delete_document(request=request)
            print(f"🗑️ Deleted document: {document_name}")
            return True
        except Exception as e:
            print(f"❌ Error deleting document: {e}")
            return False

