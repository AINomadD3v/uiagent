# Development Guide

## Quick Start

### Prerequisites

1. **Nix Package Manager** (Recommended)
   ```bash
   # Install Nix (if not already installed)
   curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install

   # Enable direnv for automatic environment activation
   echo 'eval "$(direnv hook bash)"' >> ~/.bashrc
   ```

2. **Android Device with USB Debugging**
   - Enable Developer Options on your Android device
   - Enable USB Debugging in Developer Options
   - Connect device via USB and authorize the computer

3. **ADB (Android Debug Bridge)**
   - Included automatically in Nix environment
   - Manual installation: Download from Android SDK Platform Tools

### Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd uiagent

# Enter Nix development environment (automatic with direnv)
nix develop

# Verify environment setup
python --version  # Should show Python 3.13.x
node --version    # Should show Node.js version
adb version       # Should show ADB version

# Verify device connection
adb devices       # Should list your connected device
```

### Starting Development Servers

```bash
# Single command to start both frontend and backend
./start-dev.sh

# Services will be available at:
# - Frontend: http://localhost:5173 (SvelteKit + Vite)
# - Backend: http://localhost:20242 (FastAPI + Uvicorn)
# - API Docs: http://localhost:20242/docs (Interactive documentation)
```

## Development Environment Details

### Nix Development Environment

UIAutodev uses Nix flakes for reproducible development environments. The `flake.nix` file defines all dependencies and their exact versions.

**Key Benefits**:
- **Reproducible**: Identical environment across all development machines
- **Isolated**: No conflicts with system packages
- **Declarative**: All dependencies explicitly defined
- **Automatic**: Environment activated via direnv when entering the project directory

**Custom Package Builds**:
The flake includes custom builds for several Python packages with specific patches:
- `uiautomator2Custom`: Enhanced Android automation capabilities
- `apkutils2Custom`: APK analysis and manipulation
- `wdapyCustom`: WebDriver automation protocol support

### Directory Structure

```
uiagent/
├── app.py                          # FastAPI main application
├── model.py                        # Pydantic data models
├── provider.py                     # Device provider abstraction
├── common.py                       # Shared utilities
├── command_types.py                # Command type definitions
├── command_proxy.py                # Command proxy implementation
├── exceptions.py                   # Custom exceptions
├── start-dev.sh                    # Development server startup script
├── flake.nix                       # Nix development environment
├── flake.lock                      # Locked dependency versions
├── .envexample                     # Environment variables template
├── frontend/                       # SvelteKit frontend application
│   ├── src/
│   │   ├── lib/
│   │   │   └── components/         # Svelte components
│   │   ├── routes/                 # SvelteKit routes
│   │   └── app.html               # Main HTML template
│   ├── package.json               # Node.js dependencies
│   ├── vite.config.js             # Vite configuration
│   └── tsconfig.json              # TypeScript configuration
├── driver/                        # Device driver implementations
│   └── android.py                 # Android device driver
├── router/                        # FastAPI route handlers
│   └── device.py                  # Device-related API routes
├── services/                      # Backend services
│   └── llm/                       # LLM integration services
│       ├── backends/              # LLM provider backends
│       ├── prompt/                # Prompt management
│       └── tools/                 # LLM tools and utilities
├── utils/                         # Utility modules
│   ├── common.py                  # Common utilities
│   └── interactive_executor.py    # Python code execution
├── progress/                      # Development progress tracking
└── docs/                          # Documentation
    ├── diagrams/                  # PlantUML architecture diagrams
    ├── ARCHITECTURE.md            # System architecture
    ├── API.md                     # API documentation
    ├── DEVELOPMENT.md             # This file
    └── DEPLOYMENT.md              # Deployment guide
```

## Development Workflow

### Code Organization Principles

1. **Separation of Concerns**: Clear boundaries between frontend, API, business logic, and integrations
2. **Type Safety**: Comprehensive use of TypeScript (frontend) and Python type hints (backend)
3. **Pydantic Models**: Centralized data models in `model.py` for API validation
4. **Provider Pattern**: Abstracted device providers for extensibility
5. **Async by Default**: FastAPI with async/await patterns throughout

### Backend Development

#### Adding New API Endpoints

1. **Define Data Models** (in `model.py`):
   ```python
   class NewFeatureRequest(BaseModel):
       parameter: str
       options: Dict[str, Any] = Field(default_factory=dict)

   class NewFeatureResponse(BaseModel):
       result: str
       success: bool
   ```

2. **Create Route Handler**:
   ```python
   # In appropriate router file (e.g., router/device.py)
   @router.post("/new-feature", response_model=NewFeatureResponse)
   async def new_feature_endpoint(request: NewFeatureRequest):
       # Implementation here
       return NewFeatureResponse(result="success", success=True)
   ```

3. **Register Router** (in `app.py`):
   ```python
   app.include_router(device_router, prefix="/api/devices", tags=["devices"])
   ```

#### Python Code Quality

**Linting and Formatting**:
```bash
# Run linting (available in Nix environment)
ruff check .

# Auto-format code
ruff format .

# Type checking
mypy app.py
```

**Testing**:
```bash
# Run tests
pytest

# With coverage
pytest --cov=. --cov-report=html
```

### Frontend Development

#### SvelteKit 5.0 Development

**Component Structure**:
```svelte
<!-- src/lib/components/DeviceViewer.svelte -->
<script lang="ts">
  import type { DeviceInfo } from '../types';

  interface Props {
    device: DeviceInfo;
    onScreenshot: (device: DeviceInfo) => void;
  }

  let { device, onScreenshot }: Props = $props();
</script>

<div class="device-viewer">
  <h3>{device.name} ({device.serial})</h3>
  <button onclick={() => onScreenshot(device)}>
    Take Screenshot
  </button>
</div>
```

**Type Definitions**:
```typescript
// src/lib/types.ts
export interface DeviceInfo {
  serial: string;
  model: string;
  name: string;
  status: string;
  enabled: boolean;
}

export interface ScreenshotResponse {
  image_data: string;
  width: number;
  height: number;
  timestamp: string;
}
```

#### Frontend Development Commands

```bash
cd frontend

# Start development server (or use ./start-dev.sh from root)
npm run dev

# Type checking
npm run check

# Build for production
npm run build

# Preview production build
npm run preview
```

### Real-time Features

#### Server-Sent Events (SSE)

**Backend Implementation**:
```python
from fastapi.responses import StreamingResponse

@app.post("/api/stream")
async def stream_endpoint():
    async def generate():
        for i in range(10):
            yield f"data: {{'count': {i}}}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache"}
    )
```

**Frontend Implementation**:
```typescript
// Subscribe to server-sent events
const eventSource = new EventSource('/api/stream');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

#### WebSocket Support

For bidirectional communication, UIAutodev can be extended with WebSocket support:

```python
# Backend WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Echo: {data}")
```

## Testing Strategy

### Backend Testing

**Unit Tests**:
```python
# test_device_provider.py
import pytest
from provider import AndroidProvider

@pytest.fixture
def android_provider():
    return AndroidProvider()

def test_list_devices(android_provider):
    devices = android_provider.list_devices()
    assert isinstance(devices, list)
    # Add more assertions
```

**Integration Tests**:
```python
# test_api_integration.py
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_device_list_endpoint():
    response = client.get("/api/devices/list")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

**API Testing with Actual Devices**:
```bash
# Requires connected Android device
pytest tests/integration/ -v
```

### Frontend Testing

**Component Tests**:
```typescript
// src/lib/components/__tests__/DeviceViewer.test.ts
import { render, screen } from '@testing-library/svelte';
import DeviceViewer from '../DeviceViewer.svelte';

test('renders device information', () => {
  const device = {
    serial: 'TEST123',
    model: 'TestDevice',
    name: 'Test Device',
    status: 'device',
    enabled: true
  };

  render(DeviceViewer, { device });

  expect(screen.getByText('Test Device (TEST123)')).toBeInTheDocument();
});
```

**End-to-End Testing**:
```bash
# Install Playwright for E2E tests
npm install -D @playwright/test

# Run E2E tests
npx playwright test
```

## Code Quality Standards

### Python Code Standards

1. **Type Hints**: All functions must have type hints
   ```python
   def process_device(device_id: str) -> DeviceInfo:
       pass
   ```

2. **Pydantic Models**: Use Pydantic for all data validation
   ```python
   class ApiRequest(BaseModel):
       device_id: str = Field(..., description="Device serial number")
       action: str = Field(..., regex="^(tap|swipe|type)$")
   ```

3. **Error Handling**: Proper exception handling with logging
   ```python
   try:
       result = device.execute_command(command)
   except DeviceError as e:
       logger.error(f"Device command failed: {e}")
       raise HTTPException(status_code=500, detail=str(e))
   ```

4. **Async/Await**: Use async patterns for I/O operations
   ```python
   async def capture_screenshot(device_id: str) -> bytes:
       return await device.screenshot_async()
   ```

### TypeScript Code Standards

1. **Strict Type Checking**: Enable strict mode in `tsconfig.json`
2. **Interface Definitions**: Define interfaces for all data structures
3. **Component Props**: Use proper prop typing in Svelte components
4. **Error Boundaries**: Implement error handling in components

### Documentation Standards

1. **Docstrings**: All functions must have descriptive docstrings
2. **API Documentation**: Endpoints automatically documented via FastAPI
3. **Type Documentation**: Types serve as documentation
4. **README Updates**: Keep documentation current with code changes

## Debugging and Development Tools

### Backend Debugging

**Logging Configuration**:
```python
# Set log level via environment variable
export UIAUTODEV_LOG_LEVEL=DEBUG

# Or in .env file
UIAUTODEV_LOG_LEVEL=DEBUG
```

**Interactive Debugging**:
```python
# Add breakpoints in code
import pdb; pdb.set_trace()

# Or use modern debugger
import ipdb; ipdb.set_trace()
```

**Performance Profiling**:
```bash
# Profile API endpoints
pip install py-spy
py-spy record -o profile.svg -- python -m uvicorn app:app
```

### Frontend Debugging

**Browser Developer Tools**:
- Network tab for API request monitoring
- Console for JavaScript errors and logging
- Sources tab for breakpoint debugging

**Svelte DevTools**:
```bash
# Install browser extension for Svelte debugging
# Available for Chrome and Firefox
```

**Vite Development Features**:
- Hot Module Replacement (HMR) for instant updates
- Source maps for debugging production builds
- Built-in proxy for API requests

## Environment Variables

### Backend Configuration

Create `.env` file from `.envexample`:
```bash
cp .envexample .env
```

**Key Variables**:
```bash
# Logging
UIAUTODEV_LOG_LEVEL=INFO

# LLM Configuration
DEEPSEEK_API_KEY=your_deepseek_api_key
OPENAI_API_KEY=your_openai_api_key

# Device Configuration
ADB_PATH=/usr/bin/adb
DEVICE_TIMEOUT=30

# Development
DEVELOPMENT_MODE=true
CORS_ORIGINS=http://localhost:5173
```

### Frontend Configuration

**Vite Environment Variables** (in `frontend/.env`):
```bash
VITE_API_BASE_URL=http://localhost:20242
VITE_WS_URL=ws://localhost:20242
```

## Contributing Guidelines

### Code Contribution Process

1. **Fork and Clone**: Fork the repository and clone your fork
2. **Feature Branch**: Create a feature branch from `main`
3. **Development**: Implement your feature with tests
4. **Quality Checks**: Run linting, formatting, and tests
5. **Documentation**: Update documentation as needed
6. **Pull Request**: Submit PR with clear description

### Commit Message Format

```
type(scope): brief description

Longer description explaining the change and its impact.

Fixes #123
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Pull Request Guidelines

1. **Clear Title**: Descriptive PR title
2. **Description**: Explain what, why, and how
3. **Tests**: Include relevant tests
4. **Documentation**: Update docs if needed
5. **Breaking Changes**: Clearly mark breaking changes

## Troubleshooting

### Common Development Issues

#### Device Connection Problems
```bash
# Check ADB connection
adb devices

# Restart ADB server
adb kill-server
adb start-server

# Check device authorization
adb shell
```

#### Python Environment Issues
```bash
# Rebuild Nix environment
nix develop --rebuild

# Clear Python cache
find . -name "__pycache__" -exec rm -rf {} +
find . -name "*.pyc" -delete
```

#### Frontend Build Issues
```bash
cd frontend

# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear Vite cache
rm -rf .vite
```

#### Port Conflicts
```bash
# Check what's using ports
lsof -i :20242  # Backend
lsof -i :5173   # Frontend

# Kill processes if needed
kill -9 <PID>
```

### Development Performance Tips

1. **Use SSD**: Development on SSD significantly improves performance
2. **Increase Node Memory**: For large frontend builds
   ```bash
   export NODE_OPTIONS="--max-old-space-size=4096"
   ```
3. **Parallelize Tasks**: Use `./start-dev.sh` for concurrent development
4. **Hot Reload**: Keep hot reload enabled for faster development cycles

---

For deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).
For architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md).