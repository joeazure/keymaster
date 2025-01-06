# Keymaster

Secure API key management for AI services, focusing on OpenAI, Anthropic, and Stability AI.

## Features

- ✅ Secure key storage using macOS Keychain
- ✅ Multiple environment support (dev/staging/prod)
- ✅ Encrypted audit logging
- ✅ API key validation
- ✅ Key rotation support
- ✅ Environment file generation
- ✅ Direct API integration with:
  - OpenAI
  - Anthropic
  - Stability AI

## Requirements

- Python 3.11 or higher
- macOS (Keychain support)
- Internet connection for API validation

## Installation

1. Create and activate a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install from source:
```bash
git clone https://github.com/joeazure/keymaster.git
cd keymaster
pip install -e .
```

## Usage

### Initialize Keymaster
```bash
keymaster init
```

### Add an API key
```bash
keymaster add --service openai --environment dev --api_key <your_api_key>
```
