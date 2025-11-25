# Google RAG Video Q&A Agent

An AI agent system that extracts YouTube transcripts and uses Google Gemini AI for intelligent question answering.

## Features

- 🎥 **YouTube Transcript Extraction**: Automatically extracts transcripts from YouTube videos
- 🧠 **Google Gemini AI Integration**: Uses Google's latest AI for embeddings and question answering
- 💾 **Smart Caching**: Avoids re-processing already analyzed videos
- 🌍 **Multi-language Support**: Works with Turkish and English transcripts
- 🔒 **Secure API Management**: Environment-based API key management

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Get Google AI Studio API Key
1. Go to [https://aistudio.google.com/api-keys](https://aistudio.google.com/api-keys)
2. Create a new API key
3. Copy the API key

### 3. Create Environment File
```bash
cp .env.example .env
# Edit .env and replace 'your_api_key_here' with your actual API key
```

### 4. Run the System
```bash
python google-search-agent.py
```

## Usage

### Basic Usage
```bash
# Process default video
python google-search-agent.py

# Process specific video
python google-search-agent.py --url "https://www.youtube.com/watch?v=VIDEO_ID"

# Force re-embedding
python google-search-agent.py --force-reembed

# List processed videos
python google-search-agent.py --list-processed
```

### Interactive Q&A
After processing a video, you can ask questions interactively:
```
❓ Your question: Bu videoda hangi muhasebe işleminden bahsediliyor?
📝 Answer: [Gemini AI generates answer based on transcript]
```

## File Structure

```
├── google-search-agent.py    # Main application
├── requirements.txt          # Dependencies
├── .env                      # API keys (not in git)
├── .env.example             # API key template
├── .gitignore               # Git ignore rules
├── transcript_*.json        # Extracted transcripts
└── embeddings_*.json        # AI embeddings
```

## How It Works

1. **Transcript Extraction**: Downloads YouTube video transcripts
2. **Smart Caching**: Checks if video already processed
3. **AI Embedding**: Creates vector embeddings using Google Gemini
4. **Question Answering**: Uses Gemini AI with transcript context
5. **Status Tracking**: Maintains processing status for each video

## Cost Information

- **Gemini API**: ~$0.001-0.002 per question
- **Embeddings**: ~$0.0001-0.0005 per 1K tokens
- **Free Tier**: Available for testing

## Security

- API keys are stored in `.env` file (not committed to git)
- Embeddings and transcripts are cached locally
- No data is sent to external servers except Google AI

## Troubleshooting

### "No Google API key configured"
- Make sure `.env` file exists with your API key
- Check that `GOOGLE_API_KEY=your_key_here` is set correctly

### "Embedding failed"
- Verify your API key is valid
- Check Google AI Studio console for usage limits
- Ensure internet connection is stable

## License

This project is for educational and testing purposes with Google's AI technology.
