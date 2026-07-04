# Vidnex Full-Stack Verification Platform (Django)

This is a full-stack web application implementing the workflow:

1. User registration/login
2. Verification form + document upload
3. Admin approval/rejection
4. Verified-only access to bidding, earnings, and withdraw features

## Tech Stack

- Backend: Django 3.2 + Django REST Framework
- Database: SQLite (default)
- Auth: Session-based authentication
- File Uploads: Django media storage (local in development)
- Email Notifications: Django console email backend

## Project Structure

- `core/models.py`: Database schema
- `core/views.py`: Page views + API endpoints
- `core/serializers.py`: Request/response validation
- `core/urls.py`: Routes
- `templates/core/`: UI pages
- `static/css/app.css`: Styling
- `static/js/*.js`: Frontend logic

## Database Schema

Implemented tables/entities:

- `User` (Django auth user)
- `UserProfile` (full_name, role, status, rejection_reason)
- `VerificationDetail` (experience, education, resume, certificates, id_proof)
- `Project`
- `Bid` (user_id, project_id, amount, status)
- `Earning` (total, pending, withdrawn)
- `Transaction`
- `WithdrawRequest` (amount, status, payment details)

## Run Instructions

### 1. Install dependencies

```powershell
cd backend_app
"C:/Program Files (x86)/Microsoft Visual Studio/Shared/Python37_64/python.exe" -m pip install -r requirements.txt
```

### 2. Run migrations

```powershell
"C:/Program Files (x86)/Microsoft Visual Studio/Shared/Python37_64/python.exe" manage.py migrate
```

### 3. Create admin user

```powershell
"C:/Program Files (x86)/Microsoft Visual Studio/Shared/Python37_64/python.exe" manage.py createsuperuser
```

Then set admin role/status for dashboard access:

```powershell
"C:/Program Files (x86)/Microsoft Visual Studio/Shared/Python37_64/python.exe" manage.py shell
```

```python
from django.contrib.auth.models import User
u = User.objects.get(username="YOUR_ADMIN_EMAIL@gmail.com")
u.profile.role = "admin"
u.profile.status = "verified"
u.profile.save()
```

### 4. Start server

```powershell
"C:/Program Files (x86)/Microsoft Visual Studio/Shared/Python37_64/python.exe" manage.py runserver
```

Open:

- User app: `http://127.0.0.1:8000/login/`
- Admin dashboard: `http://127.0.0.1:8000/admin-dashboard/`
- Django admin: `http://127.0.0.1:8000/admin/`

## API Endpoints

### Auth

- `POST /api/auth/register`
  - body: `{ "full_name", "email", "password" }`
- `POST /api/auth/login`
  - body: `{ "email", "password" }`
- `POST /api/auth/logout`
- `GET /api/auth/me`

### Verification

- `POST /api/verification/submit`
  - multipart/form-data:
    - `work_company`, `work_role`, `work_years`
    - `education_degree`, `education_university`, `education_year`
    - `resume`, `certificates`, `id_proof`
- `GET /api/verification/status`

### Bidding

- `GET /api/projects`
- `POST /api/bids/place`
  - body: `{ "project_id", "amount", "proposal_note" }`
- `GET /api/bids/my`

### Earnings + Withdraw

- `GET /api/earnings`
- `POST /api/withdraw/request`
  - body: `{ "amount", "payment_method", "payment_details" }`
- `GET /api/withdraw/my`

### Admin Verification

- `GET /api/admin/pending-users`
- `POST /api/admin/users/<user_id>/approve`
- `POST /api/admin/users/<user_id>/reject`
  - body optional: `{ "reason": "..." }`

## Workflow Mapping to Requirements

1. On registration, profile status defaults to `pending_verification`.
2. After login, non-verified users are expected to complete `/verification/` page.
3. Admin can approve/reject from `/admin-dashboard/`.
4. Bidding/earnings/withdraw APIs enforce verified status.
5. Non-verified users see `Your account is under verification` messaging on dashboard and blocked API actions.

## Notes

- Email notifications are printed in the server console (development mode).
- Uploaded files are stored under `backend_app/media/`.
- For production, replace local file storage and console email backend with S3/Firebase + SMTP provider.
