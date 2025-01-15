# Keymaster

Secure API key management for AI services, with support for OpenAI, Anthropic, Stability AI, and DeepSeek.

## Features

- ✅ Secure key storage using macOS Keychain
- ✅ Multiple environment support (dev/staging/prod)
- ✅ Interactive service and environment selection
- ✅ Encrypted audit logging with timestamps
- ✅ API key validation and testing
- ✅ Key rotation support
- ✅ Environment file generation
- ✅ Case-insensitive service names
- ✅ Secure key backup during replacement
- ✅ SQLite metadata storage
- ✅ Direct API integration with:
  - OpenAI
  - Anthropic
  - Stability AI
  - DeepSeek

## Requirements

- Python 3.11 or higher
- macOS (Keychain support)
- Internet connection for API validation

## Installation

1. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
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
This will:
- Create necessary directories (~/.keymaster)
- Initialize configuration
- Set up logging
- Verify keychain access
- Create SQLite database

### Managing API Keys

#### Add a Key
```bash
# Interactive mode
keymaster add-key

# Non-interactive mode
keymaster add-key --service openai --environment dev --api_key <your_api_key>

# Force replace existing key
keymaster add-key --service openai --environment dev --api_key <your_api_key> --force
```

#### Remove a Key
```bash
# Interactive mode
keymaster remove-key

# Non-interactive mode
keymaster remove-key --service openai --environment dev
```

#### List Keys
```bash
# List all keys
keymaster list-keys

# List keys for specific service
keymaster list-keys --service openai

# Show key values (requires confirmation)
keymaster list-keys --show-values
```

#### Test a Key
```bash
# Interactive mode
keymaster test-key

# Non-interactive mode
keymaster test-key --service openai --environment dev
```

### Environment File Generation

```bash
# Interactive mode
keymaster generate-env

# Non-interactive mode
keymaster generate-env --service openai --environment dev --output .env
```

### Configuration Management

```bash
# Show current configuration
keymaster config show

# Reset configuration
keymaster config reset
```

### Audit Logging

```bash
# View all audit logs
keymaster audit

# Filter by service
keymaster audit --service openai

# Filter by environment
keymaster audit --environment prod

# Filter by date range
keymaster audit --start-date 2024-01-01 --end-date 2024-01-31

# View sensitive data (requires confirmation)
keymaster audit --decrypt
```

## Security Features

- Secure storage in macOS Keychain
- Encrypted audit logs
- Secure key backup before replacement
- SQLite metadata storage
- Automatic directory permission management
- Key validation before storage
- Sensitive data masking in logs

## Directory Structure

```
~/.keymaster/
├── config.yaml      # Configuration file
├── logs/
│   ├── keymaster.log  # Application logs
│   └── audit.log      # Encrypted audit logs
└── db/
    └── keymaster.db   # SQLite metadata database
```

## Supported Services

- **OpenAI**: API key management for OpenAI services
- **Anthropic**: Claude and other Anthropic API services
- **Stability AI**: Image generation and AI models
- **DeepSeek**: AI language models and services

## Development

### Running Tests
```bash
pip install -e ".[test]"  # Install test dependencies
pytest                    # Run tests with coverage
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

