# LetterGator

**See you later, Alligator!**

LetterGator is a digital vault where users can write a message now and have it delivered to the recipient's email on a future date.

## Stack

- Full Stack: Django templates + static files
- Database: SQLite (temporary)
- Environment: Docker Compose
- Config: `.env` loaded via `python-dotenv`

## Services

- `backend`: Django app on port 8000

## Quick Start

1. Ensure `.env` contains `SQLITE_NAME=db.sqlite3` and
   `TIME_ZONE=Asia/Yerevan` (or your preferred IANA timezone).

2. Build and run:

   ```bash
   docker-compose up --build
   ```

3. Open app:
   - http://localhost:8000/

Letter creation is handled on the dedicated Vault page (`/vault/`) by a standard Django POST view.

## Delivery command

A management command is included as a placeholder scheduler target:

```bash
docker-compose exec backend python manage.py send_due_letters
```

This command sends emails for all letters where:

- `delivery_at <= now`
- `is_delivered == false`

Then it marks each sent letter as delivered.

You can later trigger this command with Celery Beat, cron, or a scheduled container job.

## Notes

- Django migrations are run automatically on backend container startup through `entrypoint.sh`.

## GitHub Actions CI/CD

Two workflows are included in `.github/workflows/`:

- `ci.yml`: runs on push and pull request (`main`, `develop`)
   - installs dependencies
   - waits for MySQL 5.7
   - runs migrations, checks, and tests
- `cd.yml`: deploys to server on successful CI run for `main`
   - connects via SSH
   - updates code from `origin/main`
   - rebuilds and restarts containers with Docker Compose

### Required GitHub Secrets

Set the following repository secrets:

- `SSH_HOST`: server IP or hostname
- `SSH_USER`: SSH user on server
- `SSH_PRIVATE_KEY`: private key for SSH auth
- `SSH_PORT`: SSH port (for example `22`)
- `DEPLOY_PATH`: absolute path to project on server

### One-time Server Preparation

1. Install Docker and Docker Compose on the server.
2. Clone this repository on the server into `DEPLOY_PATH`.
3. Ensure a valid `.env` file exists on the server at the project root.
4. Make sure the branch `main` is available on `origin`.
