# Spira Architecture

This document describes the modular architecture of Spira, organized into separate application and backend components.

## 📁 Project Structure

```
spira/
├── src/
│   ├── spira/                    # Main package (coordinator)
│   │   └── __init__.py          # Imports from backend and app
│   ├── spira_backend/           # Backend/Core Logic
│   │   ├── __init__.py          # Backend exports
│   │   ├── cli.py               # Backend CLI commands
│   │   ├── config.py            # Configuration management
│   │   ├── knowledge_base.py    # Knowledge base builder
│   │   ├── query_engine.py      # SQL generation engine
│   │   ├── glue_catalog.py      # AWS Glue integration
│   │   ├── notebook_parser.py   # Notebook processing
│   │   ├── sql_analyzer.py      # SQL pattern analysis
│   │   ├── opensearch_client.py # Vector search
│   │   └── embeddings.py        # Embedding generation
│   ├── spira_app/               # Frontend/UI
│   │   ├── __init__.py          # App exports
│   │   ├── cli.py               # App CLI commands
│   │   └── app.py               # Streamlit application
│   └── spira_cli.py             # Main CLI coordinator
├── tests/                       # Test suites
├── examples/                    # Example scripts
├── docs/                        # Documentation
└── pyproject.toml              # Package configuration
```

## 🔧 Components

### Backend (`spira_backend/`)

The backend contains the core business logic and data processing components:

#### **Configuration Management**
- `config.py`: YAML-based configuration with validation
- Supports environment variables and multiple deployment environments
- Validates AWS service configurations

#### **Data Processing Pipeline**
- `notebook_parser.py`: Parallel processing of Jupyter/Zeppelin notebooks
- `sql_analyzer.py`: Pattern extraction and business logic analysis
- `glue_catalog.py`: AWS Glue Catalog metadata extraction
- `embeddings.py`: AWS Bedrock embedding generation

#### **Search & Storage**
- `opensearch_client.py`: Vector similarity search with OpenSearch
- `knowledge_base.py`: End-to-end pipeline orchestration
- Supports hybrid search (text + semantic)

#### **Query Generation**
- `query_engine.py`: RAG-based SQL generation using Claude
- Confidence scoring and validation
- Citation system with similarity scores

### Frontend (`spira_app/`)

The frontend contains the user interface components:

#### **Web Application**
- `app.py`: Streamlit web interface
- Interactive query interface
- Real-time SQL generation
- Visual citations and confidence scores

#### **CLI Interface**
- `cli.py`: Command-line interface for the web app
- Port and host configuration
- Logging and error handling

### Coordination (`spira_cli.py`)

Main CLI coordinator that provides unified entry points:
- Routes commands to appropriate components
- Provides help and usage information
- Supports interactive query mode

## 🚀 Command Line Interface

### Available Commands

```bash
# Build knowledge base (backend)
spira-build --config config.yaml

# Run web application (frontend)
spira-app --port 8080

# Interactive querying (coordinator)
spira --config config.yaml
```

### Command Details

#### `spira-build`
- **Purpose**: Build knowledge base from notebooks
- **Module**: `spira_backend.cli:build_knowledge_base`
- **Dependencies**: AWS services (Bedrock, OpenSearch, Glue)

#### `spira-app`
- **Purpose**: Run Streamlit web application
- **Module**: `spira_app.cli:run_app`
- **Dependencies**: Streamlit, backend components

#### `spira`
- **Purpose**: Interactive query interface
- **Module**: `spira_cli:main`
- **Dependencies**: Backend query engine

## 🔄 Data Flow

### Knowledge Base Building
```
Notebooks → Parser → SQL Analysis → Embeddings → OpenSearch Index
    ↓
Glue Catalog → Schema Extraction → Metadata Storage
```

### Query Processing
```
User Question → Embedding → Vector Search → Context Retrieval
    ↓
Claude + Context → SQL Generation → Validation → Response
```

## 🛠️ Development

### Backend Development
```bash
# Work on core logic
cd src/spira_backend/

# Run tests
pytest tests/ -k backend

# Build knowledge base
python -m spira_backend.cli build --config config.yaml
```

### Frontend Development
```bash
# Work on UI
cd src/spira_app/

# Run app
python -m spira_app.cli

# Test UI components
streamlit run app.py
```

### Integration Testing
```bash
# Test full pipeline
spira-build --config config.yaml
spira-app --port 8501
```

## 📦 Package Management

### Installation
```bash
# Install full package
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"
```

### Package Structure
- **spira**: Main package with unified imports
- **spira_backend**: Core logic and data processing
- **spira_app**: User interface and web application

### Import Patterns
```python
# Use main package for convenience
from spira import Config, QueryEngine, StreamlitApp

# Use specific components for development
from spira_backend.config import Config
from spira_app.app import StreamlitApp
```

## 🔐 Security & Deployment

### Backend Security
- AWS IAM integration for all services
- No storage of sensitive data
- Query validation and sanitization

### Frontend Security
- Configuration file upload validation
- Error handling without data exposure
- Session state management

### Production Deployment
- Backend can run as separate service
- Frontend can be deployed independently
- Horizontal scaling supported

## 🧪 Testing Strategy

### Backend Tests
- Unit tests for each component
- Integration tests with AWS services
- Mock configurations for CI/CD

### Frontend Tests
- UI component testing
- User interaction flows
- Error handling scenarios

### End-to-End Tests
- Full pipeline validation
- Performance benchmarking
- Error recovery testing

## 📈 Monitoring & Observability

### Backend Metrics
- Knowledge base build times
- Query generation latency
- AWS service usage

### Frontend Metrics
- User interaction patterns
- Query success rates
- Performance metrics

### Logging
- Structured logging throughout
- Error tracking and alerting
- Performance monitoring

This modular architecture enables:
- **Independent development** of frontend and backend
- **Flexible deployment** options
- **Better testing** and maintainability
- **Clear separation** of concerns