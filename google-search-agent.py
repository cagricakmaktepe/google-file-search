import re
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import os
import json
from datetime import datetime
import argparse
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Google Gemini AI
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    print("✅ Google Gemini AI configured successfully")
else:
    print("⚠️  Warning: GOOGLE_API_KEY not found in environment variables")
    print("   Please create a .env file with your Google AI Studio API key")


def embed_transcript_with_gemini(transcript_text):
    """
    Create embeddings for transcript using Google Gemini
    """
    try:
        if not GOOGLE_API_KEY:
            print("❌ Cannot embed: No Google API key configured")
            return None

        print("🔄 Creating embeddings with Google Gemini...")

        result = genai.embed_content(
            model="models/embedding-001",
            content=transcript_text,
            task_type="retrieval_document"
        )

        print("✅ Transcript embedded successfully")
        return result['embedding']

    except Exception as e:
        print(f"❌ Embedding failed: {e}")
        return None


def save_embeddings_to_file(video_id, embeddings):
    """
    Save embeddings to a JSON file
    """
    try:
        embeddings_data = {
            "video_id": video_id,
            "embeddings": embeddings,
            "created_at": str(datetime.now())
        }

        filename = f"embeddings_{video_id}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(embeddings_data, f, indent=2)

        print(f"💾 Embeddings saved to: {filename}")
        return filename

    except Exception as e:
        print(f"❌ Could not save embeddings: {e}")
        return None


def load_embeddings_from_file(video_id):
    """
    Load embeddings from file
    """
    try:
        filename = f"embeddings_{video_id}.json"
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"❌ Could not load embeddings: {e}")
        return None


def list_available_models():
    """
    List available Gemini models for debugging
    """
    try:
        if not GOOGLE_API_KEY:
            return "❌ No API key configured"

        models = genai.list_models()
        print("📋 Available Gemini Models:")
        for model in models:
            if 'generateContent' in model.supported_generation_methods:
                print(f"  ✅ {model.name}")
        return True
    except Exception as e:
        print(f"❌ Could not list models: {e}")
        return False

def answer_question_with_gemini(question, transcript_text):
    """
    Answer questions using Gemini AI with transcript context
    """
    try:
        if not GOOGLE_API_KEY:
            return "❌ Cannot answer: No Google API key configured"

        print(f"🤖 Answering: {question}")

        model = genai.GenerativeModel('gemini-2.5-flash')

        # Limit transcript context to avoid token limits
        max_context_length = 4000
        if len(transcript_text) > max_context_length:
            transcript_text = transcript_text[:max_context_length] + "..."

        prompt = f"""
        You are a helpful AI assistant analyzing a YouTube video transcript.

        TRANSCRIPT CONTEXT:
        {transcript_text}

        USER QUESTION:
        {question}

        INSTRUCTIONS:
        - Answer based only on the transcript content
        - Be accurate and helpful
        - If the transcript doesn't contain relevant information, say so
        - Keep answers concise but complete
        - Answer in Turkish since the transcript is in Turkish

        ANSWER:"""

        response = model.generate_content(prompt)
        answer = response.text.strip()

        print("✅ Answer generated successfully")
        return answer

    except Exception as e:
        error_msg = f"❌ Answer generation failed: {e}"
        print(error_msg)
        return error_msg


def extract_video_id(url):
    """
    Extract video ID from YouTube URL
    Returns the video ID or None if not found
    """
    try:
        # Handle youtu.be short URLs
        if 'youtu.be' in url:
            path = urlparse(url).path
            return path.lstrip('/')

        # Handle youtube.com URLs
        if 'youtube.com' in url:
            parsed_url = urlparse(url)
            if 'v' in parse_qs(parsed_url.query):
                return parse_qs(parsed_url.query)['v'][0]

        # Try regex as fallback for edge cases
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None
    except Exception as e:
        print(f"Error extracting video ID: {e}")
        return None


def get_video_transcript(video_id, languages=None):
    """
    Get transcript from YouTube video using video ID
    Returns the transcript text or None if not available

    Args:
        video_id: YouTube video ID
        languages: List of language codes in priority order (e.g., ['tr', 'en'])
                  If None, defaults to Turkish first, then English
    """
    if languages is None:
        languages = ['tr', 'en']  # Turkish first, English as fallback

    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=languages)

        # Combine all transcript pieces into one text
        transcript_text = ""
        for entry in transcript:
            transcript_text += entry.text + " "

        return transcript_text.strip()

    except TranscriptsDisabled:
        print("Transcripts are disabled for this video")
        return None
    except NoTranscriptFound:
        print(f"No transcript available for this video in languages: {languages}")
        return None
    except Exception as e:
        print(f"Error getting transcript: {e}")
        return None


def save_transcript(video_id, transcript, url, status_updates=None):
    """
    Save transcript to a JSON file for later use with status tracking

    Args:
        video_id: YouTube video ID
        transcript: Transcript text
        url: Original video URL
        status_updates: Dict of status updates to merge (optional)
    """
    try:
        filename = f"transcript_{video_id}.json"

        # Load existing data if file exists, otherwise create new
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
        else:
            transcript_data = {
                "video_id": video_id,
                "url": url
            }

        # Update transcript data
        if transcript:
            transcript_data["transcript"] = transcript
            transcript_data["timestamp"] = str(datetime.now())

        # Initialize status if not exists
        if "status" not in transcript_data:
            transcript_data["status"] = {}

        # Update status
        if status_updates:
            transcript_data["status"].update(status_updates)

        # Save updated data
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(transcript_data, f, indent=2, ensure_ascii=False)

        print(f"💾 Transcript saved to: {filename}")
        return filename
    except Exception as e:
        print(f"Warning: Could not save transcript: {e}")
        return None


def load_transcript_data(video_id):
    """
    Load existing transcript data for a video ID

    Returns:
        dict: Transcript data if file exists, None otherwise
    """
    try:
        filename = f"transcript_{video_id}.json"
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"Warning: Could not load transcript data: {e}")
        return None


def process_youtube_video(url):
    """
    Main function to process a YouTube URL and get transcript
    Returns tuple: (transcript, video_id)
    """
    print(f"Processing YouTube URL: {url}")

    # Extract video ID
    video_id = extract_video_id(url)
    if not video_id:
        print("Could not extract video ID from URL")
        return None, None

    print(f"Extracted video ID: {video_id}")

    # Get transcript
    transcript = get_video_transcript(video_id)
    if not transcript:
        print("Could not get transcript for this video")
        return None, None

    print(f"Successfully got transcript ({len(transcript)} characters)")
    print("🎯 Language preference: Turkish (tr) first, English (en) fallback")
    return transcript, video_id


def process_video_smart(url, force_reembed=False):
    """
    Smart video processing that checks status and only does necessary work

    Args:
        url: YouTube video URL
        force_reembed: Force re-embedding even if already done

    Returns:
        tuple: (transcript_data, video_id) or (None, None) if failed
    """
    print(f"🎥 Processing YouTube URL: {url}")

    # Extract video ID
    video_id = extract_video_id(url)
    if not video_id:
        print("❌ Could not extract video ID from URL")
        return None, None

    print(f"📹 Video ID: {video_id}")

    # Load existing transcript data
    existing_data = load_transcript_data(video_id)

    if existing_data:
        print("📂 Found existing transcript file")
        status = existing_data.get('status', {})

        # Check if already fully processed (transcript extracted AND embedded)
        if status.get('transcript_extracted') and status.get('embedded') and not force_reembed:
            print("✅ Video fully processed (transcript + embeddings)")
            print(f"📅 Last embedded: {status.get('last_embedded', 'Unknown')}")
            return existing_data, video_id

        # Check if transcript already extracted
        if status.get('transcript_extracted'):
            print("✅ Transcript already extracted")
            transcript = existing_data.get('transcript')
        else:
            print("📝 Extracting transcript...")
            transcript = get_video_transcript(video_id)
            if not transcript:
                print("❌ Could not get transcript for this video")
                return None, None
            # Save transcript with status update
            save_transcript(video_id, transcript, url, {'transcript_extracted': True})

        # Check if embedding needed
        if not status.get('embedded') or force_reembed:
            if force_reembed:
                print("🔄 Force re-embedding requested...")
            else:
                print("🔄 Creating embeddings with Google Gemini...")

            # Create embeddings with Google Gemini
            embeddings = embed_transcript_with_gemini(transcript)

            if embeddings:
                # Save embeddings to file
                save_embeddings_to_file(video_id, embeddings)

                # Mark as embedded in transcript status
                save_transcript(video_id, None, url, {
                    'embedded': True,
                    'last_embedded': str(datetime.now())
                })
                print("✅ Successfully embedded with Gemini AI")
            else:
                print("❌ Embedding failed - transcript saved but not embedded")
        else:
            print("✅ Embeddings already exist")

    else:
        print("🆕 New video - starting fresh processing...")

        # Get transcript
        transcript = get_video_transcript(video_id)
        if not transcript:
            print("❌ Could not get transcript for this video")
            return None, None

        print(f"✅ Got transcript ({len(transcript)} characters)")

        # Save transcript with initial status
        save_transcript(video_id, transcript, url, {'transcript_extracted': True})

        # Create embeddings with Google Gemini
        embeddings = embed_transcript_with_gemini(transcript)

        if embeddings:
            # Save embeddings to file
            save_embeddings_to_file(video_id, embeddings)

            # Mark as embedded in transcript status
            save_transcript(video_id, None, url, {
                'embedded': True,
                'last_embedded': str(datetime.now())
            })
        else:
            print("❌ Embedding failed - transcript saved but not embedded")

    # Load final data
    final_data = load_transcript_data(video_id)
    print("🎯 Video processing complete!")
    return final_data, video_id


def main():
    """
    Main function - process video transcript and accept questions with smart caching
    """
    parser = argparse.ArgumentParser(description='Google RAG Video Q&A Agent')
    parser.add_argument('--url', type=str,
                       default="https://www.youtube.com/watch?v=Pg6stnkEkEo&list=PLXrRC--1DgPab9DaC_WSUsrMEeMa3uhD7&index=3",
                       help='YouTube video URL to process')
    parser.add_argument('--force-reembed', action='store_true',
                       help='Force re-embedding even if already done')
    parser.add_argument('--list-processed', action='store_true',
                       help='List all processed videos')
    parser.add_argument('--list-models', action='store_true',
                       help='List available Gemini models')

    args = parser.parse_args()

    print("🎥 Google File Search Agent")
    print("=" * 50)

    # Handle list processed videos option
    if args.list_processed:
        print("📋 Processed Videos:")
        print("-" * 30)

        # Find all transcript files
        transcript_files = [f for f in os.listdir('.') if f.startswith('transcript_') and f.endswith('.json')]
        if not transcript_files:
            print("No processed videos found.")
            return

        for filename in transcript_files:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    video_id = data.get('video_id', 'Unknown')
                    status = data.get('status', {})
                    embedded = status.get('embedded', False)
                    last_embedded = status.get('last_embedded', 'Never')

                    if embedded:
                        status_icon = "✅"
                        status_text = f"Embedded: {embedded} ({last_embedded})"
                    else:
                        status_icon = "⏳"
                        status_text = "Transcript extracted, embedding pending"
                    print(f"{status_icon} {video_id} - {status_text}")
            except Exception as e:
                print(f"⚠️  Error reading {filename}: {e}")
        return

    # Handle list models option
    if args.list_models:
        print("🤖 Gemini Models Check:")
        print("-" * 30)
        list_available_models()
        return

    VIDEO_URL = args.url
    print(f"🎬 Processing video: {VIDEO_URL}")
    if args.force_reembed:
        print("🔄 Force re-embedding enabled")
    print()

    # Use smart processing
    transcript_data, video_id = process_video_smart(VIDEO_URL, args.force_reembed)

    if not transcript_data:
        print("❌ Failed to process video. Exiting...")
        return

    print(f"\n✅ Video processed successfully!")
    transcript = transcript_data.get('transcript', '')
    print(f"📝 Transcript length: {len(transcript)} characters")
    print("\n🤖 Ready to answer questions about this video!")
    print("Type your questions below (or 'quit' to exit):")
    print("-" * 50)

    # Check if running interactively or has piped input
    import sys
    import select
    is_interactive = sys.stdin.isatty() and sys.stdout.isatty()
    has_piped_input = not sys.stdin.isatty() and select.select([sys.stdin], [], [], 0)[0]

    if is_interactive or has_piped_input:
        # Interactive question answering loop
        print("\n" + "="*50)
        while True:
            try:
                question = input("❓ Your question: ").strip()

                if question.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break

                if not question:
                    continue

                # Answer the question using Gemini AI with transcript context
                transcript_text = transcript_data.get('transcript', '')

                if not transcript_text:
                    print("❌ No transcript available for this video")
                    continue

                answer = answer_question_with_gemini(question, transcript_text)

                print(f"\n📝 Answer: {answer}")
                print("-" * 50)

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except EOFError:
                print("\n👋 Goodbye!")
                break
    else:
        # Demo mode - show example questions
        print("\n" + "="*50)
        print("📋 DEMO MODE - Example questions you can ask:")
        print("• What is this song about?")
        print("• What does the singer promise?")
        print("• What emotions are expressed?")
        print("• Tell me about the lyrics")
        print("\n💡 To ask questions interactively, run:")
        print("   python google-search-agent.py")
        print("   (in an interactive terminal)")


if __name__ == "__main__":
    main()