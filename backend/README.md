# DermaSphere API

FastAPI service for the DermaSphere MySQL-backed skincare marketplace.

## Local setup

1. Copy `.env.example` to `.env` and set a strong `JWT_SECRET` and your MySQL connection URL.
2. Create a MySQL database with `utf8mb4` encoding and create a least-privilege application user.
3. Install dependencies: `python -m venv .venv`, activate it, then `pip install -r requirements.txt`.
4. Start the API from this directory with `uvicorn app.main:app --reload`.
5. Open `/docs` for the interactive API reference.

The API creates the initial relational schema at startup for local development. Production schema changes should be managed with reviewed migrations.

## Security notes

Registration supports customer and seller accounts; it never accepts administrator role assignment. Store production secrets outside source control. All private routes verify the signed bearer token and resource ownership/role.
