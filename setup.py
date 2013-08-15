#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(name='logfeed',
      version='1.3',
      description='Read log messages from rotated files',
      author='Artyom Pervukhin',
      author_email='artyom@evasive.ru',
      url='https://github.com/artyom/logfeed',
      py_modules=['logfeed'],
     )
