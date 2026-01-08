import copy
import json
import hashlib
import locale
import re
from urllib.parse import urlparse, urlunparse

from deep_translator import GoogleTranslator
from starlette.requests import Request
from stopwords import get_stopwords


class helper_controller:
    __instance = None

