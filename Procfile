web: cd backend_app && python manage.py migrate --noinput && python setup_admin.py && gunicorn vidnex_platform.wsgi --bind 0.0.0.0:$PORT --log-file -
