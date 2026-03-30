# app.py - TomFlex Cifras em Python com Flask (replica exata do GAS)
from flask import Flask, render_template, request, jsonify, session
import os
import re
import json
from docx import Document
import pdfplumber
import fitz  # PyMuPDF para PDF com layout preservado
app = Flask(__name__)
app.secret_key = 'tomflex_secret_2024'  # Mude para produção

# Regex e constantes portados do JS (exatos)
CHORD_RE = re.compile(r'(?<![A-Za-z0-9])([A-G](?:#|b)?)([A-Za-z0-9()+-]*)(?:\/([A-G](?:#|b)?|[+\-]?\d+(?:[+\-])?))?(?![A-Za-z0-9])', re.IGNORECASE)
FULL_CHORD_RE = re.compile(r'^([A-G](?:#|b)?)([A-Za-z0-9()+-]*)(?:\/([A-G](?:#|b)?|[+\-]?\d+(?:[+\-])?))?$')
NOTES_SHARP

import os
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
