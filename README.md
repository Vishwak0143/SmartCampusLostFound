# Smart Campus Lost-and-Found Management System

A small Flask and SQLite web application prototype for reporting lost/found campus items and managing claims.

## Features
- Student registration and login with password hashing
- Student and officer roles (officer accounts are provisioned by an administrator)
- Lost/found item reporting and browsing
- Category, location and type filters
- Claim submission and officer approval/rejection
- Dashboard and management summary reports
- Health endpoint at `/health`

## Requirements
- Python 3.13+
- Git
- Docker (optional, for containerization)

## Local setup (Windows PowerShell)
```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Tests
```powershell
pytest -v
```

## Create an officer account
1. Register a normal account in the application.
2. Stop the Flask server.
3. Run:
```powershell
flask --app app promote-officer
```
4. Enter the email address of the account to promote.
5. Restart the application and sign in with that account.

This command is intended only for local academic setup. In production, officer role assignment must be restricted to a trusted administrator.

## Docker
```powershell
docker build -t campusfind:1.0 .
docker run --name campusfind -p 5000:5000 -e SECRET_KEY="replace-with-a-long-random-secret" campusfind:1.0
```
Open http://127.0.0.1:5000

## Notes
- SQLite is suitable for this small single-instance demonstration. A production multi-instance deployment should use a managed database such as PostgreSQL.
- The default secret key is for local development only. Set a strong `SECRET_KEY` in any shared environment.
- This is an academic prototype. It does not include email/SMS notifications, image uploads, campus SSO or production-grade account administration.
