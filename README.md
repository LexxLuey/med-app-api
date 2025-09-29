# Backend - RCM Validation Engine

FastAPI backend implementing the complete RCM validation engine with integrated data pipeline. **Phases 2 & 4 Complete**.

## Features
- ✅ **Complete API**: All required endpoints implemented
- ✅ **Data Pipeline**: Integrated rule parsing, validation, and LLM evaluation
- ✅ **File Processing**: Excel/CSV claims upload with auto claim_id generation
- ✅ **Authentication**: JWT-based security for all protected endpoints
- ✅ **Database**: PostgreSQL with full schema (Master/Refined/Metrics/Audit tables)
- ✅ **Rule Engine**: PDF parsing for technical/medical rules
- ✅ **LLM Integration**: Google Gemini 1.5 Flash for medical validation
- ✅ **Multi-tenant**: Environment-based configuration
- ✅ **Sample Compatible**: Works with provided case study artifacts

## Quick Setup

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your database credentials

# Run database migrations
alembic upgrade head

# Start development server
uvicorn main:app --reload --port 8000
```

## Environment Variables

### Required
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: JWT signing key (generate random string)
- `GEMINI_API_KEY`: Google Gemini API key for LLM evaluation

### Optional
- `REDIS_URL`: Redis for caching (optional)
- `PORT`: Server port (default: 8000)
- `TENANT_ID`: Multi-tenant identifier (default: "default")
- `PAID_AMOUNT_THRESHOLD`: Technical validation threshold (default: 1000)
- `APPROVAL_NUMBER_MIN`: Minimum approval number length (default: 100000)
- `DEBUG`: Enable debug mode (default: false)

### CORS Configuration (12-Factor compliant)
- `CORS_ALLOW_ORIGINS`: Comma-separated allowed origins (default: "*")
- `CORS_ALLOW_CREDENTIALS`: Allow credentials (default: true)
- `CORS_ALLOW_METHODS`: Comma-separated allowed methods (default: "*")
- `CORS_ALLOW_HEADERS`: Comma-separated allowed headers (default: "*")

## API Endpoints

### Authentication
- `POST /api/v1/auth/token` - Login with username/password, returns JWT

### Claims CRUD
- `GET /api/v1/claims/` - List claims (paginated, authenticated)
- `POST /api/v1/claims/` - Create new claim (authenticated)
- `GET /api/v1/claims/{claim_id}` - Get specific claim (authenticated)
- `PUT /api/v1/claims/{claim_id}` - Update claim (authenticated)
- `DELETE /api/v1/claims/{claim_id}` - Delete claim (authenticated)

### File Upload
- `POST /api/v1/upload/claims` - Upload Excel/CSV claims file (authenticated)
- `POST /api/v1/upload/rules/technical` - Upload technical rules PDF (authenticated)
- `POST /api/v1/upload/rules/medical` - Upload medical rules PDF (authenticated)

### Validation Pipeline
- `POST /api/v1/validation/run` - Trigger background validation processing (authenticated)
- `GET /api/v1/validation/status/{task_id}` - Check specific task status and progress (authenticated)
- `GET /api/v1/validation/tasks` - List all user's background tasks (authenticated)
- `GET /api/v1/validation/results` - Get validation metrics and results (authenticated)

### System
- `GET /api/v1/audit/` - View audit logs (authenticated)
- `GET /api/v1/health/` - Health check (public)

## Testing with Sample Data

The backend is fully compatible with the provided case study artifacts:

```bash
# 1. Get authentication token
curl -X POST "http://localhost:8000/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=pass"

# 2. Upload sample claims (from project root)
curl -X POST "http://localhost:8000/api/v1/upload/claims" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@091325_Humaein Recruitment_Claims File_vShared.xlsx"

# 3. Upload technical rules
curl -X POST "http://localhost:8000/api/v1/upload/rules/technical" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@Humaein_Technical_Rules.pdf"

# 4. Upload medical rules
curl -X POST "http://localhost:8000/api/v1/upload/rules/medical" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@Humaein_Medical_Rules.pdf"

# 5. Run validation pipeline
RESPONSE=$(curl -X POST "http://localhost:8000/api/v1/validation/run" \
  -H "Authorization: Bearer YOUR_TOKEN")
TASK_ID=$(echo $RESPONSE | jq -r '.task_id')
echo "Task started with ID: $TASK_ID"

# 6. Check task status (repeat until complete)
curl -X GET "http://localhost:8000/api/v1/validation/status/$TASK_ID" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 7. Check all user tasks
curl -X GET "http://localhost:8000/api/v1/validation/tasks" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 8. Get final results
curl -X GET "http://localhost:8000/api/v1/validation/results" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Architecture

```
backend/
├── main.py                 # FastAPI app with lifespan & CORS
├── pipeline/               # Integrated data processing
│   ├── __init__.py
│   ├── rules.py           # PDF parsing & rule evaluation
│   ├── llm.py             # Gemini medical validation
│   └── tasks.py           # Background claim processing
├── auth/router.py         # JWT authentication
├── claims/router.py       # Claims CRUD operations
├── upload/router.py       # File ingestion with parsing
├── validation/router.py   # Pipeline orchestration
├── audit/router.py        # Audit logging
└── shared/                # Common utilities
    ├── config.py         # Pydantic settings
    ├── database.py       # SQLAlchemy connection
    ├── models.py         # Database models
    └── schemas.py        # API schemas
```

## Database Schema

### MasterTable (Raw Claims)
All 14 required fields from case study specifications.

### RefinedTable (Processed Claims)
Validated claims with error classifications and recommendations.

### MetricsTable (Aggregations)
Validation statistics by error type and tenant.

### AuditLog (Activity Tracking)
User actions and system events.

## Data Pipeline Flow

1. **Upload**: Claims Excel/CSV → auto claim_id generation → MasterTable
2. **Rule Parsing**: PDF documents → extracted rules → Redis cache
3. **Validation**: Background processing → technical + medical evaluation
4. **Results**: Updated MasterTable + RefinedTable + MetricsTable

## Development

### Code Quality
```bash
# Format code
black .

# Lint code
flake8
ruff check .

# Type checking (optional)
mypy .
```

### Testing
```bash
# Run tests
pytest

# With coverage
pytest --cov=. --cov-report=html
```

### Database Management
```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Downgrade (if needed)
alembic downgrade -1
```

## API Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## Deployment

### Render.com (Recommended)
1. Create PostgreSQL database instance
2. Create Redis instance (optional, for caching)
3. Deploy web service with environment variables
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Environment Variables for Production
```bash
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://host:6379
SECRET_KEY=your-256-bit-secret
GEMINI_API_KEY=your-gemini-api-key
PORT=10000
DEBUG=false
```

## Troubleshooting

### Common Issues
- **Excel upload fails**: Ensure `openpyxl` is installed
- **PDF parsing fails**: Check file is valid PDF
- **LLM errors**: Verify Gemini API key and credits
- **Database connection**: Check DATABASE_URL format

### Logs
```bash
# Enable debug logging
export DEBUG=true
uvicorn main:app --reload --log-level debug
```

## Security Notes
- JWT tokens expire in 30 minutes
- All data endpoints require authentication
- File uploads are validated for type and content
- Database credentials never logged
- Gemini API key stored securely in environment

## Performance
- Background processing for large claim batches
- Redis caching for parsed rules
- Database connection pooling
- Pagination for large result sets
- Async file processing

## Contributing
See root [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines.
