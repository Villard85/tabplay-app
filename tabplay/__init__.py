#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  tabplay/__init__.py
#  
#  
from flask import Flask

app = Flask(__name__)
app.config.from_object('tabplay.config')

from tabplay.views import views