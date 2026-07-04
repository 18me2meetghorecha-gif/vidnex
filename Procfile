web: gunicorn vidnex_platform.wsgi --bind 0.0.0.0:$PORT --chdir backend_app --log-file -
release: python backend_app/manage.py migrate
