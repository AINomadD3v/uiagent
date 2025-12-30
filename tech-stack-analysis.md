# Tech Stack Analysis - UIAutodev

> **DEPRECATION NOTICE** (December 2025)
>
> This document was created in September 2025 and is now significantly outdated.
>
> **Major features NOT documented here:**
> - MCP Server (`mcp_server.py`) - Model Context Protocol integration
> - Screen Detection system (`signatures/`) - UI fingerprinting and screen identification
> - Navigation system (`navigation/`) - Graph-based pathfinding between screens
> - Popup handling system - Automatic popup dismissal patterns
>
> **Known issues:**
> - File paths reference `/home/aidev/tools/uiagent/` which is now `/home/aidev/phone-farm-tools/uiagent/`
> - References removed RAG/CocoIndex system (removed in commit e66c877)
> - Does not reflect current project structure
>
> **For current documentation, see:**
> - `docs/MCP.md` - MCP server architecture and tools
> - `docs/SCREEN-DETECTION.md` - Screen detection and navigation
> - `progress/` - Session progress files with recent development notes

## Executive Summary
- **Primary Language**: Python (24 files) with TypeScript/JavaScript frontend (2,425 files)
- **Architecture Pattern**: Microservices-style with separate frontend/backend
- **Deployment Model**: Container-ready with Nix development environment
- **Database Strategy**: No persistent database detected (in-memory state management)

## Programming Languages & Frameworks

### Primary Stack
- **Python**: 3.13 - 24 files
  - **Framework**: FastAPI
  - **Key Libraries**: Uvicorn (ASGI server), Pydantic (data validation)
  - **Usage Evidence**: `/home/aidev/tools/uiagent/app.py:14` - FastAPI imports, `/home/aidev/tools/uiagent/flake.nix:184-185` - FastAPI/Uvicorn dependencies

### Frontend Stack
- **TypeScript**: 454 files
- **JavaScript**: 1,971 files (including node_modules)
  - **Framework**: SvelteKit 5.0
  - **Build Tool**: Vite 6.2.6
  - **Usage Evidence**: `/home/aidev/tools/uiagent/frontend/package.json:16-18` - SvelteKit and Vite configuration

### Supporting Technologies
- **Android Automation**: uiautomator2, adbutils
- **Image Processing**: PIL/Pillow
- **Configuration**: YAML/JSON configuration files

## Architecture Overview

### Application Structure
```
/home/aidev/tools/uiagent/
├── app.py                    # FastAPI main application
├── frontend/                 # SvelteKit frontend application
├── driver/                   # Android device drivers
├── services/                 # LLM and backend services
├── router/                   # FastAPI route handlers
├── utils/                    # Utility modules
├── model.py                  # Pydantic data models
└── provider.py               # Device provider abstraction
```

### Component Relationships
- **Frontend (SvelteKit)** → **Backend (FastAPI)** via HTTP API
- **Backend** → **Android Devices** via uiautomator2/ADB
- **Backend** → **LLM Services** via modular backend system

## Data Management

### Data Models
- **Primary Models**: Defined in `/home/aidev/tools/uiagent/model.py`
  - **DeviceInfo**: Android device metadata
  - **Node**: UI hierarchy representation
  - **ChatMessageContent**: LLM conversation data
  - **OCRNode**: OCR text recognition results
- **No Persistent Database**: Application uses in-memory state management
- **Data Flow**: REST API → Pydantic models → Android device automation

### State Management
- **Device State**: Tracked in memory via AndroidProvider
- **Process Tracking**: Active processes stored in `ACTIVE_PROCESSES` dict
- **Session Data**: No persistent sessions, stateless API design

## Development Environment

### Package Management
- **Python**: Nix flake - `/home/aidev/tools/uiagent/flake.nix`
  - **Dependencies**: 18 core Python packages including FastAPI, uiautomator2, custom builds
  - **Custom Packages**: apkutils2Custom, uiautomator2Custom, wdapyCustom (lines 87-202)
- **Frontend**: npm - `/home/aidev/tools/uiagent/frontend/package.json`
  - **Dependencies**: 10 production, 8 development packages
  - **Key Dependencies**: CodeMirror for code editing, diff for text comparison

### Build & Development Tools
- **Build System**: Vite (frontend), Uvicorn (backend)
- **Task Runner**: npm scripts for frontend, shell scripts for full-stack
- **Development Server**: Combined startup via `/home/aidev/tools/uiagent/start-dev.sh`
- **Hot Reload**: Available for both frontend (Vite) and backend (Uvicorn --reload)

### Testing Strategy
- **Unit Testing**: pytest available in Nix environment
- **Integration Testing**: No comprehensive test suite detected
- **Test Coverage**: pytest-cov available but no test files found
- **Test Infrastructure**: Test components directory exists at `/home/aidev/tools/uiagent/frontend/src/lib/components/__tests__`

## Deployment & Infrastructure

### Containerization
- **Nix Development Environment**: Full declarative environment in flake.nix
  - **Custom Package Builds**: 5 custom Python packages with patches
  - **System Dependencies**: Android tools, Poetry, Git
  - **Environment Isolation**: Complete development environment via `nix develop`

### Development Workflow
- **Startup Command**: `./start-dev.sh` - Parallel frontend/backend development
- **Backend**: `uvicorn app:app --host 127.0.0.1 --port 20242 --reload`
- **Frontend**: `npm run dev` (Vite dev server on port 5173)
- **API Documentation**: Available at http://127.0.0.1:20242/docs

### Environment Configuration
- **Environment Variables**: `.env` file support with `.envexample` template
- **Configuration Management**: FastAPI dependency injection pattern
- **Development Mode**: Hot reload enabled for both frontend and backend

## External Dependencies & APIs

### Android Device Integration
- **uiautomator2**: Primary Android automation framework
- **adbutils**: Android Debug Bridge utilities
- **Device Discovery**: Automatic device detection and management
- **UI Hierarchy**: XML parsing and Node tree construction

### LLM Integration
- **Provider System**: Modular LLM backend architecture
- **Supported Providers**: DeepSeek (detected in `/home/aidev/tools/uiagent/services/llm/backends/deepseek.py`)
- **Streaming Responses**: Server-Sent Events for real-time LLM communication

### Code Intelligence
- **Python Completion**: Jedi-based autocompletion system
- **Code Execution**: Interactive Python execution with process management
- **Syntax Highlighting**: CodeMirror with Python language support

## Security Considerations

### API Security
- **CORS**: Configured for development (allow all origins)
- **Input Validation**: Pydantic models for request/response validation
- **Error Handling**: Structured exception handling with logging

### Process Management
- **Process Isolation**: Individual process tracking per device
- **Interrupt Handling**: SIGINT-based process termination
- **Resource Cleanup**: Proper cleanup on server shutdown

## Performance & Monitoring

### Performance Features
- **Async Architecture**: FastAPI with async/await patterns
- **Streaming**: Server-Sent Events for real-time communication
- **Process Management**: Background process execution with tracking

### Monitoring & Logging
- **Logging Framework**: Python standard logging with configurable levels
- **Environment-Based**: Log level controlled via `UIAUTODEV_LOG_LEVEL`
- **Error Tracking**: Comprehensive exception logging throughout codebase

## Development Workflow

### Code Organization
- **Flat Structure**: Recent refactoring flattened directory structure
- **Module Separation**: Clear separation between UI automation, LLM services, and web API
- **Type Safety**: Extensive use of Pydantic models and Python type hints

### Developer Onboarding
- **Nix Environment**: Declarative development environment
- **Single Command Setup**: `./start-dev.sh` starts entire development stack
- **Documentation**: API documentation auto-generated via FastAPI

## Recommendations for New Developers

### Getting Started Priority
1. **Understand the Nix Environment**: Essential for dependency management and consistent development
2. **Explore the API Documentation**: Visit http://127.0.0.1:20242/docs after starting servers
3. **Review the Frontend Components**: SvelteKit components in `/home/aidev/tools/uiagent/frontend/src/lib/components/`

### Key Files to Examine
- `/home/aidev/tools/uiagent/app.py` - Main FastAPI application with all endpoints
- `/home/aidev/tools/uiagent/model.py` - Complete data model definitions
- `/home/aidev/tools/uiagent/driver/android.py` - Android device automation core
- `/home/aidev/tools/uiagent/frontend/src/routes/+page.svelte` - Main frontend application

### Common Development Tasks
- **Start Development**: `./start-dev.sh`
- **Run Tests**: `pytest` (via Nix environment)
- **Build Frontend**: `cd frontend && npm run build`
- **Environment Setup**: `nix develop` (automatic via direnv)

### Recent Refactoring Impact
- **Flattened Structure**: Components moved to root level for simpler imports
- **Progress Tracking**: Active development tracked in `/home/aidev/tools/uiagent/progress/` directory
- **UI Improvements**: Recent fixes to screenshot viewer, element selection, and hierarchy scrolling

---
*Analysis completed on 2025-09-19 | Total files analyzed: 2,449 | Technologies detected: 15 major components*

## Technology Stack Summary

**Core Technologies:**
- Backend: Python 3.13 + FastAPI + Uvicorn
- Frontend: TypeScript + SvelteKit 5.0 + Vite
- Android: uiautomator2 + adbutils
- LLM: Modular provider system with streaming
- Development: Nix + direnv for environment management

**Architecture:** Microservices-style with REST API communication, real-time streaming capabilities, and comprehensive Android device automation.