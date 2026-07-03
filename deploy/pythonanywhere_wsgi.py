"""
Paste this into PythonAnywhere → Web → WSGI configuration file
(usually /var/www/aralap_pythonanywhere_com_wsgi.py).

Also set in the Web tab:
  - Source code: /home/aralap/maimjaim/maimjaim
  - Virtualenv:  /home/aralap/maimjaim/maimjaim/.venv  (or your venv path)
  - Working directory: /home/aralap/maimjaim/maimjaim

In .env on the server:
  DATABASE_URL=sqlite:///instance/maimjaim.db
  FLASK_ENV=production

Then run once in a Bash console:
  cd /home/aralap/maimjaim/maimjaim && source .venv/bin/activate
  flask --app wsgi db upgrade
"""
import os
import sys

PROJECT_HOME = "/home/aralap/maimjaim/maimjaim"

if PROJECT_HOME not in sys.path:
    sys.path.insert(0, PROJECT_HOME)

os.chdir(PROJECT_HOME)

from app import create_app

application = create_app()
