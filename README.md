# Retail Data Platform

**Retail Data Platform** is a modular backend application providing APIs for store analytics, inventory management, sales forecasting, NLP-based insights, and more. It’s built on Flask (a lightweight WSGI web framework and uses Celery for background processing (a distributed task queue). The application runs in Docker containers and uses SQLAlchemy (ORM) with Alembic for the database layer.

## Features

- **API Services:** Domain-specific modules (e.g. customers, products, orders, analytics, forecasting, NLP) exposed via REST endpoints.
- **Background Tasks:** Long-running or scheduled jobs handled asynchronously by Celery workers.
- **Data Persistence:** Relational database with SQLAlchemy ORM models and Alembic migrations for schema changes.
- **Containerized:** All components (Flask API, message broker, database) orchestrated via Docker Compose【23†L157-L160】.
- **Testing:** Comprehensive test suite using pytest (each module has corresponding `test_*.py`).

## Getting Started

**Prerequisites:** Install [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/). Clone the repository:

```bash
git clone https://github.com/username/retail-data-platform.git
cd RetailIQ
```

### Setup

1. Copy `.env.example` to `.env` and fill in required environment variables (database URL, message broker URL, etc).
2. Build and start services with Docker Compose:
   ```bash
   docker-compose up --build
   ```
   This will start the Flask API server, a message broker (e.g. Redis/RabbitMQ), and the database. Docker Compose centralizes the multi-container setup into a single YAML configuration【23†L157-L160】. On first run, the database container is initialized and Alembic runs any pending migrations automatically.

### Configuration

- API server listens on port **5000** by default. You can change ports or add services in `docker-compose.yml`.
- Environment variables (in `.env`) include settings like `DATABASE_URL`, `CELERY_BROKER_URL`, etc.
- Sensitive data (secrets, API keys) should go into `.env` or Docker secrets, not checked into source.

## Usage

- **API Endpoints:** Use a tool like `curl` or Postman to interact with the API. Example endpoints:
  - `POST /api/customers` – create a new customer.
  - `GET /api/products` – list inventory items.
  - `POST /api/forecast` – start a sales forecasting job (this enqueues a Celery task).
- **Async Tasks:** Actions that require heavy computation (e.g. generating reports or forecasts) are handled in the background. When you hit an endpoint that triggers a task, the API immediately returns a job ID while Celery workers process the task asynchronously. Celery is designed for this purpose.
- **Database:** Inspect the Postgres (or other) database to see tables. SQLAlchemy models (in `app/models/`) define the schema. To update the schema, edit models and create a new Alembic migration. The `migrations/` folder contains versioned migration scripts; apply them with `flask db upgrade` (handled automatically on startup).

## Development

- **Virtual Environment:** Create a Python venv (outside the repo directory) and run `pip install -r requirements.txt`.
- **Running Locally:** You can also run the Flask app locally (without Docker) by setting `FLASK_APP=app` and `FLASK_ENV=development` in `.env`, then using `flask run`.
- **Blueprints:** The code uses Flask Blueprints to organize features. For example, each subfolder under `app/` (like `analytics/`, `auth/`, `customers/`) is a separate blueprint.
- **Database Migrations:** Use `flask db migrate` and `flask db upgrade` to manage schema changes. Alembic (via Flask-Migrate) handles applying these changes.
- **Ignored Files:** Do not commit the local virtual environment or caches. For example, `.venv/` and `.pytest_cache/` are listed in `.gitignore` as recommended.

## Testing

Run the test suite with:

```bash
pytest
```

Tests are in the `tests/` directory, following a one-to-one module-to-test pattern. Ensure you have a test database configured or the environment in `.env` supports testing. The Flask tutorial suggests ignoring the `.pytest_cache/` directory and other build artifacts in version control.

## Contributing

Contributions are welcome! Please fork the repository and submit pull requests. Ensure all new features come with appropriate tests. When committing, remember to avoid including local environment files (see **Ignored Files** above). Follow the existing code style and update documentation as needed.

## License

This project is open source under the MIT License. See the `LICENSE` file for details. 

**Note:** The above README assumes a Python 3 environment, Docker setup, and basic familiarity with Flask and Celery. For further reading on the technologies used, see the official docs of: Flask, Celery, SQLAlchemy/Alembic, and Docker Compose.
