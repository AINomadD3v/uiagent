# UIAutodev Frontend

Modern SvelteKit 5.0 frontend for the UIAutodev Android automation platform.

## Overview

This frontend provides a real-time web interface for Android device automation, featuring:
- Live device screen viewing and interaction
- UI hierarchy inspection and element selection
- Interactive Python console with code execution
- AI-powered automation chat interface
- Real-time streaming updates via Server-Sent Events

## Quick Start

From the project root, use the unified development script:

```bash
# Start both frontend and backend together
./start-dev.sh
```

The frontend will be available at: http://localhost:5173

## Development

For frontend-only development:

```bash
# Enter the Nix development environment
nix develop

# Start the development server
npm run dev

# Or open in browser automatically
npm run dev -- --open
```

## Building

To create a production build:

```bash
npm run build
```

Preview the production build:

```bash
npm run preview
```

## Technology Stack

- **SvelteKit 5.0** - Modern full-stack framework
- **TypeScript** - Type-safe development
- **Vite 6.2.6** - Fast build tooling
- **TailwindCSS** - Utility-first styling
- **Server-Sent Events** - Real-time updates from backend

## Key Features

- **Device Management**: Connect and control Android devices
- **Live Screen View**: Real-time device screenshots with interaction
- **UI Inspector**: Browse and interact with Android UI hierarchy
- **Code Console**: Execute Python code with live feedback
- **AI Chat**: Natural language automation via LLM integration

For complete documentation, see the main project [README.md](../README.md) and [docs/](../docs/) directory.
