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
import sys
import glob
from rag_manager import RAGManager

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
    Check if the URL should be treated as a playlist.
    Rule: Must have 'list' param AND NO 'v' param.
    If 'v' is present, it is treated as a single video regardless of 'list'.
    """
    try:
        parsed_url = urlparse(url)
        if 'youtube.com' in url:
            query_params = parse_qs(parsed_url.query)
            
            # STRICT RULE: If 'v' exists, it's a single video (even if it has a list)
            if 'v' in query_params:
                return False
                
            # If 'list' exists (and we passed the 'v' check above), it's a playlist
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
    """
    try:
        api_url = f"https://www.youtube.com/playlist?list={playlist_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(api_url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        videos_info = []

        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'ytInitialData' in script.string:
                try:
                    json_start = script.string.find('var ytInitialData = ') + len('var ytInitialData = ')
                    json_end = script.string.find('};', json_start) + 1
                    json_data = script.string[json_start:json_end]
                    data = json.loads(json_data)

                    def extract_video_info_from_json(obj, videos):
                        if isinstance(obj, dict):
                            if 'videoId' in obj and isinstance(obj['videoId'], str):
                                video_id = obj['videoId']
                                title = "Unknown Title"
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
                    continue

        if not videos_info:
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'watch?v=' in href and 'list=' in href:
                    video_id = extract_video_id(f"https://youtube.com{href}")
                    if video_id:
                        videos_info.append({'id': video_id, 'title': 'Unknown Title'})

        seen_ids = set()
        filtered_videos = []
        for video in videos_info:
            if len(video['id']) == 11 and video['id'] not in seen_ids:
                filtered_videos.append(video)
                seen_ids.add(video['id'])

        videos_info = filtered_videos
        global video_titles
        video_titles = {v['id']: v['title'] for v in videos_info}

        print(f"📋 Found {len(videos_info)} videos in playlist")
        return [v['id'] for v in videos_info]

    except Exception as e:
        print(f"❌ Error extracting playlist videos: {e}")
        return []


def extract_video_id(url):
    """
    Extract video ID from YouTube URL
    """
    try:
        if 'youtu.be' in url:
            path = urlparse(url).path
            return path.lstrip('/')
        if 'youtube.com' in url:
            parsed_url = urlparse(url)
            if 'v' in parse_qs(parsed_url.query):
                return parse_qs(parsed_url.query)['v'][0]
        
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
        return None


def get_video_transcript(video_id, languages=None):
    """
    Get transcript from YouTube video using yt-dlp library.
    """
    if languages is None:
        languages = ['tr', 'en']

    print(f"📥 Fetching transcript for video {video_id}...")
    
    cookies_file = 'cookies.txt'
    has_cookies = os.path.exists(cookies_file)

    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': languages,
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookies_file if has_cookies else None,
        'sleep_interval': 5,
        'max_sleep_interval': 10,
        'format': 'best',
        'ignoreerrors': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            url = f"https://www.youtube.com/watch?v={video_id}"
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Unknown Title')
            
            subtitles = info.get('subtitles') or {}
            auto_subtitles = info.get('automatic_captions') or {}
            
            found_sub_url = None
            found_lang = None
            
            # Check manual subtitles
            for lang in languages:
                if lang in subtitles:
                    for fmt in subtitles[lang]:
                        if fmt['ext'] == 'json3':
                            found_sub_url = fmt['url']
                            found_lang = lang
                            break
                    if found_sub_url: break
            
            # Check auto subtitles
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
                print(f"❌ No subtitles found")
                return None, video_title
                
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
                except:
                    pass

            response = requests.get(found_sub_url, headers=headers, cookies=cookies_dict)
            response.raise_for_status()
            sub_data = response.json()
            
            full_text = []
            if 'events' in sub_data:
                for event in sub_data['events']:
                    if 'segs' in event:
                        for seg in event['segs']:
                            if 'utf8' in seg and seg['utf8'] != '\n':
                                full_text.append(seg['utf8'])
            
            transcript_text = "".join(full_text).strip()
            transcript_text = re.sub(r'\s+', ' ', transcript_text)
            
            return transcript_text, video_title

    except Exception as e:
        print(f"❌ Error getting transcript: {e}")
        return None, "Unknown Title"


def ingest_playlist_to_corpus(url, rag_manager, corpus_name):
    """
    Process playlist and ingest into RAG Corpus
    """
    playlist_id = extract_playlist_id(url)
    if not playlist_id:
        print("❌ Invalid playlist URL")
        return None

    video_ids = get_playlist_video_ids(playlist_id)
    if not video_ids:
        return None
    
    print(f"🚀 Starting RAG Ingestion for {len(video_ids)} videos...")
    
    for i, video_id in enumerate(video_ids, 1):
        # Rate limiting
        if i > 1:
            time.sleep(random.uniform(2, 5))
            
        video_title = video_titles.get(video_id, "Unknown Title")
        print(f"\nProcessing {i}/{len(video_ids)}: {video_title}")
        
        transcript, fetched_title = get_video_transcript(video_id)
        if fetched_title != "Unknown Title":
            video_title = fetched_title
            
        if transcript:
            # Create Document in Corpus
            doc_name = rag_manager.create_document(corpus_name, f"{video_id} - {video_title}")
            if doc_name:
                # Add title to transcript content for better context
                content = f"Video Title: {video_title}\nVideo ID: {video_id}\n\n{transcript}"
                rag_manager.ingest_text(doc_name, content)
                print(f"✅ Ingested into Corpus")
            else:
                print("❌ Failed to create document")
        else:
            print(f"❌ Failed to get transcript for {video_id}")

    return True


def answer_with_rag(question, rag_manager, corpus_name):
    """
    Answer user question using RAG + Gemini
    """
    # 1. Retrieve relevant chunks
    print("🔍 Searching Corpus...")
    chunks = rag_manager.query(corpus_name, question)
    
    if not chunks:
        return "❌ No relevant information found in the video library."
        
    # 2. Construct Prompt
    context = "\n\n".join([f"--- RELEVANT CHUNK ---\n{c['text']}" for c in chunks])
    
    prompt = f"""
    You are a helpful assistant answering questions about a video library.
    Use the following retrieved context to answer the user's question.
    
    CONTEXT:
    {context}
    
    USER QUESTION: 
    {question}
    
    INSTRUCTIONS:
    - Answer solely based on the provided context.
    - If the answer is not in the context, say "I couldn't find that information in the videos."
    - Cite the video title if mentioned in the text.
    - Answer in Turkish.
    """
    
    # 3. Generate Answer
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    return response.text


def main():
    parser = argparse.ArgumentParser(description='Google RAG Video Agent (Corpus API)')
    parser.add_argument('--url', type=str, help='YouTube playlist URL')
    parser.add_argument('--chat', action='store_true', help='Start chat mode with existing corpus')
    parser.add_argument('--list', action='store_true', help='List all stored videos')
    parser.add_argument('--delete', type=str, help='Delete a video by ID or Name')
    args = parser.parse_args()

    # ---------------------------------------------------------
    # 🔗 SET YOUR PLAYLIST URL HERE (Overrides command line if set)
    # Example: "https://www.youtube.com/playlist?list=PL..."
    HARDCODED_URL = "https://www.youtube.com/watch?v=9Ky3le8Tuw4&list=PLTB38N73SAXtABJiU3PUQXFkQSnTRt5oP" 
    # ---------------------------------------------------------

    print("🎥 Google Semantic Retriever Agent (Real RAG)")
    print("=" * 50)
    
    if not GOOGLE_API_KEY:
        print("Please set GOOGLE_API_KEY in .env")
        return

    # Determine URL to use
    target_url = HARDCODED_URL if HARDCODED_URL else args.url

    # Initialize RAG Manager
    rag = RAGManager(GOOGLE_API_KEY)
    
    # Get or Create Corpus
    corpus_name = rag.get_or_create_corpus(display_name="My Video Playlist")
    if not corpus_name:
        print("❌ Failed to initialize Corpus")
        return

    # Handle List Command
    if args.list:
        print("\n📋 Stored Videos in Corpus:")
        docs = rag.list_documents(corpus_name)
        if not docs:
            print("   (Empty)")
        else:
            for doc in docs:
                # doc['name'] looks like: corpora/xxxx/documents/yyyy
                print(f"   • {doc['display_name']}")
                print(f"     ID: {doc['name']}")
        return

    # Handle Delete Command
    if args.delete:
        print(f"\n🗑️ Attempting to delete: {args.delete}")
        docs = rag.list_documents(corpus_name)
        found = False
        for doc in docs:
            # Check if arg matches display name or full ID
            if args.delete in doc['display_name'] or args.delete == doc['name']:
                rag.delete_document(doc['name'])
                found = True
        
        if not found:
            print("❌ Video not found.")
        else:
            print("✅ Deletion complete.")
        return

    if target_url:
        if is_playlist_url(target_url):
            print(f"Please wait, processing playlist...")
            ingest_playlist_to_corpus(target_url, rag, corpus_name)
        else:
            # Single Video Logic
            print(f"Processing single video...")
            video_id = extract_video_id(target_url)
            if video_id:
                print(f"Found Video ID: {video_id}")
                transcript, title = get_video_transcript(video_id)
                if transcript:
                    doc_name = rag.create_document(corpus_name, f"{video_id} - {title}")
                    if doc_name:
                        content = f"Video Title: {title}\nVideo ID: {video_id}\n\n{transcript}"
                        rag.ingest_text(doc_name, content)
                        print(f"✅ Ingested single video into Corpus")
            else:
                print("❌ Invalid URL (Neither Playlist nor Video)")
                return
            
    # Chat Loop
    print("\n🤖 RAG System Ready!")
    print(f"Connected to Corpus: {corpus_name}")
    print("Type 'quit' to exit.")
    print("-" * 50)

    while True:
        try:
            question = input("\n❓ Question: ").strip()
            if question.lower() in ['quit', 'exit', 'q']:
                break
            if not question:
                continue
                
            print("Thinking...")
            answer = answer_with_rag(question, rag, corpus_name)
            print(f"\n📝 Answer: {answer}")
            
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
