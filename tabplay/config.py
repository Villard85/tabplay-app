#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  tabplay/config.py
#  

import os

SECRET_KEY = os.environ.get("SECRET_KEY")
DEBUG = os.environ.get("DEBUG")
MAX_CONTENT_LENGTH = 3*1024+256
SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE")
UPLOAD_EXTENSIONS = os.environ.get("UPLOAD_EXTENSIONS")
