import re
from urllib.parse import urlparse, parse_qs
import yt_dlp
import time
import random
import os
import json
from datetime import datetime
import argparse
import google.generativeai as genai
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

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

# Global variable to store video titles
video_titles = {}


def is_playlist_url(url):
    """
    Check if the URL is a YouTube playlist URL
    Returns True only for full playlist URLs (no video ID)
    Returns False for single videos (even if they have a list parameter)
    """
    try:
        parsed_url = urlparse(url)
        if 'youtube.com' in url:
            query_params = parse_qs(parsed_url.query)
            
            # If there's a video ID ('v'), it's a single video, not a full playlist page
            if 'v' in query_params:
                return False
                
            # If there's list but no video ID, it's a full playlist
            if 'list' in query_params:
                return True
        return False
    except:
        return False


def extract_playlist_id(url):
    """
    Extract playlist ID from YouTube playlist URL
    """
    try:
        parsed_url = urlparse(url)
        if 'list' in parse_qs(parsed_url.query):
            return parse_qs(parsed_url.query)['list'][0]
        return None
    except:
        return None


def get_playlist_video_ids(playlist_id):
    """
    Extract all video IDs from a YouTube playlist using web scraping
    Returns list of video IDs
    """
    try:
        # Use YouTube's public playlist page
        api_url = f"https://www.youtube.com/playlist?list={playlist_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(api_url, headers=headers)
        response.raise_for_status()

        # Parse the HTML to find video IDs in ytInitialData
        soup = BeautifulSoup(response.text, 'html.parser')

        videos_info = []  # List of {'id': video_id, 'title': title}

        # Look for ytInitialData script containing playlist data
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'ytInitialData' in script.string:
                try:
                    # Extract the JSON data from the script
                    json_start = script.string.find('var ytInitialData = ') + len('var ytInitialData = ')
                    json_end = script.string.find('};', json_start) + 1
                    json_data = script.string[json_start:json_end]

                    import json
                    data = json.loads(json_data)

                    # Navigate through the JSON structure to find video IDs and titles
                    def extract_video_info_from_json(obj, videos):
                        if isinstance(obj, dict):
                            # Look for videoId and title together
                            if 'videoId' in obj and isinstance(obj['videoId'], str):
                                video_id = obj['videoId']
                                title = "Unknown Title"

                                # Try to extract title from various possible locations
                                if 'title' in obj:
                                    title_obj = obj['title']
                                    if isinstance(title_obj, str):
                                        title = title_obj
                                    elif isinstance(title_obj, dict) and 'runs' in title_obj:
                                        runs = title_obj['runs']
                                        if runs and isinstance(runs[0], dict) and 'text' in runs[0]:
                                            title = runs[0]['text']
                                    elif isinstance(title_obj, dict) and 'simpleText' in title_obj:
                                        title = title_obj['simpleText']

                                videos.append({'id': video_id, 'title': title})

                            for value in obj.values():
                                extract_video_info_from_json(value, videos)
                        elif isinstance(obj, list):
                            for item in obj:
                                extract_video_info_from_json(item, videos)

                    extract_video_info_from_json(data, videos_info)

                    break
                except Exception as e:
                    print(f"⚠️  Error parsing ytInitialData: {e}")
                    continue

        # Fallback: Look for video links in the HTML
        if not videos_info:
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'watch?v=' in href and 'list=' in href:
                    video_id = extract_video_id(f"https://youtube.com{href}")
                    if video_id:
                        videos_info.append({'id': video_id, 'title': 'Unknown Title'})

        # Remove duplicates and filter valid video IDs
        seen_ids = set()
        filtered_videos = []
        for video in videos_info:
            if len(video['id']) == 11 and video['id'] not in seen_ids:
                filtered_videos.append(video)
                seen_ids.add(video['id'])

        videos_info = filtered_videos

        print(f"📋 Found {len(videos_info)} videos in playlist")
        for video in videos_info[:3]:  # Show first 3 as sample
            print(f"   • {video['id']} - {video['title']}")

        # Store titles globally for use in processing
        global video_titles
        video_titles = {v['id']: v['title'] for v in videos_info}

        # Return just the IDs for backward compatibility
        return [v['id'] for v in videos_info]

    except Exception as e:
        print(f"❌ Error extracting playlist videos: {e}")
        return []


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
    Get transcript from YouTube video using yt-dlp library.
    This method is more robust against IP blocking than standard scraping.

    Args:
        video_id: YouTube video ID
        languages: List of language codes in priority order (e.g., ['tr', 'en'])
                  If None, defaults to Turkish first, then English

    Returns:
        tuple: (transcript_text, video_title)
    """
    if languages is None:
        languages = ['tr', 'en']  # Turkish first, English as fallback

    print(f"📥 Fetching transcript for video {video_id} using yt-dlp...")
    
    # Check for cookies.txt
    cookies_file = 'cookies.txt'
    has_cookies = os.path.exists(cookies_file)
    if has_cookies:
        print(f"🍪 Found cookies.txt, using for authentication")

    # Configure yt-dlp options
    ydl_opts = {
        'skip_download': True,      # Don't download the video
        'writesubtitles': True,     # Download subtitles
        'writeautomaticsub': True,  # Download auto-generated subs too
        'subtitleslangs': languages, # Preferred languages
        'quiet': True,              # Less terminal noise
        'no_warnings': True,
        'cookiefile': cookies_file if has_cookies else None, # Use cookies if available
        'sleep_interval': 5,        # Internal rate limiting for safety
        'max_sleep_interval': 10,
        'format': 'best',
        'ignoreerrors': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Get video info
            url = f"https://www.youtube.com/watch?v={video_id}"
            info = ydl.extract_info(url, download=False)
            
            video_title = info.get('title', 'Unknown Title')
            
            # Check for subtitles
            subtitles = info.get('subtitles') or {}
            auto_subtitles = info.get('automatic_captions') or {}
            
            # Find the best matching language
            found_sub_url = None
            found_lang = None
            
            # 1. Check manual subtitles first
            for lang in languages:
                if lang in subtitles:
                    # Usually multiple formats, prefer 'vtt' or 'json3'
                    for fmt in subtitles[lang]:
                        if fmt['ext'] == 'json3':
                            found_sub_url = fmt['url']
                            found_lang = lang
                            break
                    if found_sub_url: break
            
            # 2. Check automatic subtitles if no manual found
            if not found_sub_url:
                for lang in languages:
                    if lang in auto_subtitles:
                        for fmt in auto_subtitles[lang]:
                            if fmt['ext'] == 'json3':
                                found_sub_url = fmt['url']
                                found_lang = lang
                                break
                        if found_sub_url: break
            
            if not found_sub_url:
                print(f"❌ No subtitles found in languages: {languages}")
                return None, video_title
                
            print(f"✅ Found subtitle in language: {found_lang}")
            
            # Download the subtitle JSON
            # We must use cookies if we have them, otherwise requests will be blocked
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': f'https://www.youtube.com/watch?v={video_id}',
            }
            
            cookies_dict = {}
            if has_cookies:
                try:
                    with open(cookies_file, 'r') as f:
                        for line in f:
                            if not line.startswith('#') and line.strip():
                                parts = line.split('\t')
                                if len(parts) >= 7:
                                    cookies_dict[parts[5]] = parts[6].strip()
                except Exception as e:
                    print(f"⚠️  Error parsing cookies.txt: {e}")

            # Use requests with cookies
            response = requests.get(found_sub_url, headers=headers, cookies=cookies_dict)
            response.raise_for_status()
            
            sub_data = response.json()
            
            # Extract text from JSON3 format
            full_text = []
            if 'events' in sub_data:
                for event in sub_data['events']:
                    # Some events are just metadata and don't have 'segs'
                    if 'segs' in event:
                        for seg in event['segs']:
                            if 'utf8' in seg and seg['utf8'] != '\n':
                                full_text.append(seg['utf8'])
            
            transcript_text = "".join(full_text).strip()
            
            # Simple cleanup of extra spaces
            transcript_text = re.sub(r'\s+', ' ', transcript_text)
            
            return transcript_text, video_title

    except Exception as e:
        print(f"❌ Error getting transcript with yt-dlp: {e}")
        return None, "Unknown Title"


def save_transcript(video_id, transcript, url, status_updates=None, video_title=None):
    """
    Save transcript to transcripts/ folder with organized naming

    Args:
        video_id: YouTube video ID
        transcript: Transcript text
        url: Original video URL
        status_updates: Dict of status updates to merge (optional)
        video_title: Video title for better filename (optional)
    """
    try:
        # Create transcripts folder if it doesn't exist
        os.makedirs('transcripts', exist_ok=True)

        # Generate filename with video title if available
        if video_title and video_title != "Unknown Title":
            # Clean title for filename
            clean_title = re.sub(r'[^\w\s-]', '', video_title).replace(' ', '_')[:50]
            filename = f"transcripts/transcript_{video_id}_{clean_title}.json"
        else:
            filename = f"transcripts/transcript_{video_id}.json"

        # Load existing data if file exists, otherwise create new
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
        else:
            transcript_data = {
                "video_id": video_id,
                "url": url,
                "title": video_title or "Unknown Title"
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
    transcript, video_title = get_video_transcript(video_id)
    if not transcript:
        print("Could not get transcript for this video")
        return None, None

    print(f"Successfully got transcript ({len(transcript)} characters)")
    print("🎯 Language preference: Turkish (tr) first, English (en) fallback")
    return transcript, video_id


def process_playlist(url, force_reembed=False, do_embedding=True):
    """
    Process all videos in a YouTube playlist

    Args:
        url: YouTube playlist URL
        force_reembed: Force re-embedding even if already done
        do_embedding: Whether to create embeddings

    Returns:
        tuple: (processed_videos, failed_videos)
    """
    print(f"🎬 Processing YouTube Playlist: {url}")

    # Extract playlist ID
    playlist_id = extract_playlist_id(url)
    if not playlist_id:
        print("❌ Could not extract playlist ID from URL")
        return [], []

    print(f"📋 Playlist ID: {playlist_id}")

    # Get all video info (IDs + titles) from playlist
    video_ids = get_playlist_video_ids(playlist_id)
    if not video_ids:
        print("❌ Could not extract video information from playlist")
        return [], []

    # Video titles are now available in global video_titles dict

    processed_videos = []
    failed_videos = []

    print(f"🚀 Starting batch processing of {len(video_ids)} videos...")
    print("-" * 60)

    for i, video_id in enumerate(video_ids, 1):
        # 🛑 GÜVENLİK BEKLEMESİ (Sadece ilk video hariç)
        if i > 1:
            wait_time = random.uniform(5, 12) # 5 ile 12 saniye arası rastgele
            print(f"⏳ Waiting {wait_time:.1f} seconds to avoid YouTube block...")
            time.sleep(wait_time)

        video_title = video_titles.get(video_id, "Unknown Title")
        print(f"\n📹 Processing Video {i}/{len(video_ids)}: {video_id} - {video_title}")

        # Construct video URL
        video_url = f"https://www.youtube.com/watch?v={video_id}&list={playlist_id}"

        # Process the video with title
        video_title = video_titles.get(video_id, "Unknown Title")
        transcript_data, processed_video_id = process_video_smart(video_url, force_reembed, do_embedding, video_title)

        if transcript_data and processed_video_id:
            processed_videos.append(processed_video_id)
            print(f"✅ Video {i} processed successfully")
        else:
            failed_videos.append(video_id)
            print(f"❌ Video {i} failed to process")

        print("-" * 40)

    print(f"\n🎯 Playlist processing complete!")
    print(f"✅ Successfully processed: {len(processed_videos)} videos")
    if failed_videos:
        print(f"❌ Failed videos: {len(failed_videos)} - {failed_videos}")

    return processed_videos, failed_videos


def process_video_smart(url, force_reembed=False, do_embedding=True, video_title=None):
    """
    Smart video processing that checks status and only does necessary work

    Args:
        url: YouTube video URL
        force_reembed: Force re-embedding even if already done
        do_embedding: Whether to create embeddings (default: True)
        video_title: Video title (optional)

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
            # Note: get_video_transcript now returns tuple (transcript, title)
            transcript, fetched_title = get_video_transcript(video_id)
            
            # Update video title if we got a better one from yt-dlp
            if fetched_title and fetched_title != "Unknown Title":
                video_title = fetched_title
                
            if not transcript:
                print("❌ Could not get transcript for this video")
                return None, None
            # Save transcript with status update
            save_transcript(video_id, transcript, url, {'transcript_extracted': True}, video_title)

        # Check if embedding needed (only if do_embedding is True)
        if do_embedding and (not status.get('embedded') or force_reembed):
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
                }, video_title)
                print("✅ Successfully embedded with Gemini AI")
            else:
                print("❌ Embedding failed - transcript saved but not embedded")
        elif not do_embedding:
            print("⏭️  Embedding skipped (transcript only mode)")
        else:
            print("✅ Embeddings already exist")

    else:
        print("🆕 New video - starting fresh processing...")

        # Get transcript
        # Note: get_video_transcript now returns tuple (transcript, title)
        transcript, fetched_title = get_video_transcript(video_id)
        
        # Update video title if we got a better one from yt-dlp
        if fetched_title and fetched_title != "Unknown Title":
            video_title = fetched_title
            
        if not transcript:
            print("❌ Could not get transcript for this video")
            return None, None

        print(f"✅ Got transcript ({len(transcript)} characters)")

        # Save transcript with initial status
        save_transcript(video_id, transcript, url, {'transcript_extracted': True}, video_title)

        # Create embeddings with Google Gemini (only if do_embedding is True)
        if do_embedding:
            embeddings = embed_transcript_with_gemini(transcript)

            if embeddings:
                # Save embeddings to file
                save_embeddings_to_file(video_id, embeddings)

                # Mark as embedded in transcript status
                save_transcript(video_id, None, url, {
                    'embedded': True,
                    'last_embedded': str(datetime.now())
                }, video_title)
            else:
                print("❌ Embedding failed - transcript saved but not embedded")
        else:
            print("⏭️  Embedding skipped (transcript only mode)")

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
                       default="https://www.youtube.com/watch?v=Pg6stnkEkEo&list=PLTB38N73SAXtABJiU3PUQXFkQSnTRt5oP&index=2",
                       help='YouTube video URL to process')
    parser.add_argument('--force-reembed', action='store_true',
                       help='Force re-embedding even if already done')
    parser.add_argument('--no-embed', action='store_true',
                       help='Skip embedding creation (transcript only)')
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

    # Check if this is a playlist URL
    if is_playlist_url(VIDEO_URL):
        print(f"🎬 Processing YouTube Playlist: {VIDEO_URL}")
        if args.force_reembed:
            print("🔄 Force re-embedding enabled")
        if args.no_embed:
            print("⏭️  Embedding disabled (transcript only)")
        print()

        # Process the entire playlist
        do_embedding = False  # User's preference: no embedding for now
        processed_videos, failed_videos = process_playlist(VIDEO_URL, args.force_reembed, do_embedding)

        print(f"\n🎯 Batch processing complete!")
        print(f"📊 Results: {len(processed_videos)} successful, {len(failed_videos)} failed")

        # Show summary of processed videos
        if processed_videos:
            print("\n📋 Processed Videos:")
            for video_id in processed_videos:
                transcript_file = f"transcripts/transcript_{video_id}.json"
                if os.path.exists(transcript_file):
                    try:
                        with open(transcript_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            title = data.get('title', 'Unknown Title')
                            status = data.get('status', {})
                            embedded = "✅" if status.get('embedded') else "⏭️"
                            print(f"  {embedded} {video_id} - {title}")
                    except:
                        print(f"  ❓ {video_id} - Could not read file")

        return

    else:
        # Single video processing (existing logic)
        print(f"🎬 Processing single video: {VIDEO_URL}")
        if args.force_reembed:
            print("🔄 Force re-embedding enabled")
        if args.no_embed:
            print("⏭️  Embedding disabled (transcript only)")
        print()

        # Use smart processing with embedding control
        do_embedding = True  # User's preference: no embedding for now
        video_title = "Unknown Title"  # For single videos, we'll use unknown title for now
        transcript_data, video_id = process_video_smart(VIDEO_URL, args.force_reembed, do_embedding, video_title)

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
