"""
PDF Object Hashing Library

A Python library for analyzing PDF structure and generating object hashes.
This allows identification of PDF similarities based on structure rather than content.
"""

from .pdf_lib import pdf_object
from .pdf_param_parser import pdf_param_parser

__version__ = "0.1.0"
__author__ = "Kyle Eaton"

__all__ = ["pdf_object", "pdf_param_parser"]