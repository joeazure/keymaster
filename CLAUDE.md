# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
- Install dev dependencies: `pip install -e ".[test]"`
- Run all tests: `pytest`
- Run single test: `pytest tests/test_file.py::test_function -v`
- Test with coverage: `pytest --cov=keymaster --cov-report=term-missing`
- Build package: `python -m build`
- Lint: `black src/` and `isort src/`

### Security Tools
- Security checks: `bandit`
- Dependency vulnerability scan: `safety`

## Architecture Overview

### Core Components

1. **CLI Interface (`src/keymaster/cli.py`)**: Click-based command-line interface with commands:
   - `init`: Initialize configuration and directories
   - `add-key`, `remove-key`, `list-keys`: Key management
   - `test-key`: API key validation
   - `generate-env`: Environment file generation
   - `audit`: View encrypted audit logs
   - `config`: Configuration management
   - `register-provider`: Add custom API providers

2. **Security Layer (`src/keymaster/security.py`)**: Cross-platform secure storage using keyring:
   - macOS: Keychain
   - Windows: Windows Credential Locker
   - Linux: SecretService (GNOME Keyring/KWallet)

3. **Provider System (`src/keymaster/providers.py`)**: Extensible API provider framework:
   - Built-in providers: OpenAI, Anthropic, Stability AI, DeepSeek
   - Generic provider system for custom APIs
   - Provider validation and testing

4. **Database Layer (`src/keymaster/db.py`)**: SQLite-based metadata storage:
   - Key metadata (service, environment, timestamps)
   - Service name normalization
   - User tracking for audit trails

5. **Configuration (`src/keymaster/config.py`)**: YAML-based configuration management
   - User preferences and settings
   - Default environments: dev, staging, prod

6. **Audit System (`src/keymaster/audit.py`)**: Encrypted audit logging
   - Sensitive data encryption
   - Timestamped operation logs
   - Filterable by service, environment, date range

7. **Sync Framework (`src/keymaster/sync/`)**: Multi-device synchronization (future feature)
   - Device management models
   - Sync status tracking
   - Conflict resolution framework

### Data Flow

1. **Key Storage**: CLI → Security Layer → System Keyring + SQLite metadata
2. **Key Retrieval**: Database lookup → Keyring retrieval → Provider validation
3. **Audit Trail**: All operations → Encrypted logs → ~/.keymaster/logs/audit.log
4. **Configuration**: ~/.keymaster/config.yaml + ~/.keymaster/providers.json

### File Structure

```
~/.keymaster/
├── config.yaml          # Main configuration
├── providers.json       # Custom API providers
├── logs/
│   ├── keymaster.log    # Application logs
│   └── audit.log        # Encrypted audit logs
└── db/
    └── keymaster.db     # SQLite metadata
```

## Development Guidelines

### Code Style
- Black formatting (line length 88)
- isort with Black profile
- Type annotations required
- Comprehensive docstrings
- snake_case for functions/variables, CamelCase for classes

### Security Requirements
- Never log or expose API keys in plain text
- Use secure storage backends only
- Encrypt sensitive audit data
- Validate all API keys before storage
- Follow principle of least privilege

### Testing
- pytest with fixtures
- Coverage threshold: 90%
- Mock external API calls with responses
- Test error conditions and edge cases
- Use descriptive test names

### Provider Development
- Extend BaseProvider for new APIs
- Implement required methods: validate_key, get_service_name
- Add provider to registry in providers.py
- Include comprehensive error handling

### Error Handling
- Use specific exceptions with context
- Log errors with structured logging
- Provide helpful user messages
- Handle keyring backend failures gracefully

## Implementation Roadmap

### Current Status
✅ **Phase 1 Complete**: Critical security vulnerabilities have been fixed and the project now has a solid, secure foundation. Ready to begin Phase 2 (Architecture Refactoring). See `IMPLEMENTATION_PLAN.md` for detailed roadmap.

### Phase Overview
1. **Phase 1**: Critical Security Fixes ✅ **COMPLETED**
   - ✅ Fixed audit encryption key storage vulnerability  
   - ✅ Added comprehensive input validation
   - ✅ Created proper exception hierarchy
   
2. **Phase 2 (Week 2)**: Architecture Refactoring
   - Eliminate code duplication in CLI
   - Fix provider registration bugs
   - Add fuzzy matching for service names
   
3. **Phase 3 (Week 3)**: Core Features
   - Implement automated key rotation
   - Add backup/restore functionality
   - Memory security improvements
   
4. **Phase 4 (Week 4)**: User Experience
   - Improve CLI with better error messages
   - Add bulk import/export operations
   - Create interactive setup wizard
   
5. **Phase 5 (Week 5)**: Testing & Reliability
   - Expand test coverage to 90%+
   - Add development tools (Makefile, pre-commit hooks)
   - Database performance improvements
   
6. **Phase 6 (Week 6)**: Advanced Features
   - Team collaboration features
   - CI/CD integrations
   - Monitoring and analytics

### Next Steps
- **Immediate Priority**: Phase 1 security fixes (critical vulnerabilities)
- **MVP Target**: End of Phase 3 (3 weeks)
- **Production Ready**: End of Phase 5 (5 weeks)

### Key Files to Monitor
- `src/keymaster/audit.py`: Security vulnerability (lines 30-35)
- `src/keymaster/providers.py`: Provider registration bug
- `src/keymaster/cli.py`: Large functions need refactoring
- `tests/`: Expand coverage significantly

For complete implementation details, timeline, and task breakdown, see `IMPLEMENTATION_PLAN.md`.