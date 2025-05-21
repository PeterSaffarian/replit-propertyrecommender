# Property Recommender System

A system that recommends properties based on user preferences using Trade Me API and OpenAI's LLM technology.

## System Overview

This property recommendation system consists of three main modules:

1. **User Interaction Module** - Collects user preferences through a conversational interface
2. **Data Gathering Module** - Fetches property listings from Trade Me API
3. **Match Reasoning Module** - Scores and ranks properties based on user preferences

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- Trade Me API credentials
- OpenAI API key

### Installation

1. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your API keys and credentials in the `.env` file:
     ```
     OPENAI_API_KEY=your_openai_api_key
     TRADEME_CONSUMER_KEY=your_trademe_consumer_key
     TRADEME_CONSUMER_SECRET=your_trademe_consumer_secret
     TRADEME_OAUTH_TOKEN=your_trademe_oauth_token
     TRADEME_OAUTH_TOKEN_SECRET=your_trademe_oauth_token_secret
     ```

### Obtaining Trade Me API Credentials

1. Register for a Trade Me developer account at [https://developer.trademe.co.nz/](https://developer.trademe.co.nz/)
2. Create a new application to receive your Consumer Key and Consumer Secret
3. Run the token generator script to obtain OAuth tokens:
   ```
   python data_gathering/providers/trademe_token_gen.py
   ```
4. Follow the prompts to authorize the application and receive the tokens

## Usage

Run the main orchestrator to execute the full pipeline:

```
python orchestrator.py
```

This will:
1. Initiate a conversation to collect your property preferences
2. Search Trade Me for matching properties
3. Process and normalize the results
4. Rank properties based on how well they match your preferences
5. Output detailed recommendations with explanations

### Running Individual Modules

You can also run each module separately:

```
# User interaction only
python user_interaction/main.py

# Data gathering only
python data_gathering/orchestrator.py

# Match reasoning only
python match_reasoning/orchestrator.py
```

## Architecture

The system follows a pipeline architecture:

1. **User Profile Collection**:
   - Interactive conversational agent to gather preferences
   - Structured JSON output validated against schema

2. **Data Gathering**:
   - LLM-based query parameter generation
   - Trade Me API integration
   - Data normalization and cleaning

3. **Match Reasoning**:
   - Property scoring using LLM reasoning
   - Detailed match rationales
   - Ranked results

## Files Structure

```
property_recommender/
│
├── orchestrator.py               # Main entry point
├── requirements.txt              # Project dependencies
├── .env                          # Environment variables (add your API keys)
├── .env.example                  # Example environment variables
│
├── user_interaction/             # User profile collection module
│   ├── main.py                   # Module entry point
│   ├── features/                 # Feature implementations
│   │   ├── chat_handler/         # Generic LLM chat interface
│   │   └── prompts.py            # System prompts
│   └── schemas/                  # JSON schemas
│
├── data_gathering/               # Property data collection module
│   ├── orchestrator.py           # Module entry point
│   ├── features/                 # Feature implementations
│   ├── providers/                # API clients
│   │   ├── trademe_api.py        # Trade Me API integration
│   │   └── trademe_token_gen.py  # OAuth token generator
│   └── schemas/                  # JSON schemas
│
└── match_reasoning/              # Property ranking module
    ├── orchestrator.py           # Module entry point
    ├── features/                 # Feature implementations
    │   ├── matcher.py            # Property matcher
    │   └── prompts.py            # System prompts
    └── schemas/                  # JSON schemas
```

## Output Files

The system generates these output files:

- `user_profile.json` - User preferences profile
- `raw_properties.json` - Raw data from Trade Me API
- `clean_properties.json` - Normalized property data
- `property_matches.json` - Final ranked recommendations

## Extending the System

To extend the system:

1. Add new fields to the JSON schemas
2. Update the prompts in `features/prompts.py` files
3. Modify the orchestrator flow in the main `orchestrator.py`