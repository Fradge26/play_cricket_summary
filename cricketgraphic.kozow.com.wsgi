 GNU nano 6.2                                                      cricketgraphic.kozow.com.wsgi
import sys
import logging
import os

sys.path.insert(0, '/var/www/cricketgraphic.kozow.com')
sys.path.insert(0, '/var/www/cricketgraphic.kozow.com/venv/lib/python3.10/site-packages/')

#set play cricket api token
os.environ["PLAY_CRICKET_API_TOKEN"] = "198ea055366910f1929b047ce86b6ea9"

# Set up logging
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

# Import and run the Flask app
from application import app as application