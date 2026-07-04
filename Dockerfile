FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files (use dummy key for build only)
RUN SECRET_KEY=build-time-dummy-key-not-used-in-production cd backend_app && python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Start gunicorn
CMD gunicorn vidnex_platform.wsgi --bind 0.0.0.0:$PORT --chdir backend_app --log-file -
