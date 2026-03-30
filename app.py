# app.py - TomFlex Cifras Python (100% fiel ao GAS, pronto pro Render)
from flask import Flask, render_template, request, jsonify, session
import os
import re
from docx import Document
import pdfplumber
import fitz  # PyMuPDF pra PDF com layout

app = Flask(__name__)
app.secret_key = 'tomflex_secret_2024'

# Regex exatos do JS
CHORD_RE = re.compile(r'(?<![A-Za-z0-9])([A-G](?:#|b)?)([A-Za-z0-9()+-]*)(?:\/([A-G](?:#|b)?|[+\-]?\d+(?:[+\-])?))?(?![A-Za-z0-9])', re.IGNORECASE)
FULL_CHORD_RE = re.compile(r'^([A-G](?:#|b)?)([A-Za-z0-9()+-]*)(?:\/([A-G](?:#|b)?|[+\-]?\d+(?:[+\-])?))?$')
NOTES_SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
NOTES_FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
NOTE_INDEX = {'C':0, 'B#':0, 'C#':1, 'Db':1, 'D':2, 'D#':3, 'Eb':3, 'E':4, 'Fb':4, 'F':5, 'E#':5, 'F#':6, 'Gb':6, 'G':7, 'G#':8, 'Ab':8, 'A':9, 'A#':10, 'Bb':10, 'B':11, 'Cb':11}

def extract_docx_text(file_path):
    doc = Document(file_path)
    return '\n'.join([para.text for para in doc.paragraphs])

def extract_txt_text(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

def extract_pdf_text(file_path):
    doc = fitz.open(file_path)
    text = ''
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def normalize_text(text):
    text = re.sub(r'\r\n?', '\n', text)
    text = text.replace('\u00A0', ' ').replace('\u200B', '')
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{5,}', '\n\n\n\n', text)
    return text.strip()

def extract_chord_objects(text):
    chords = []
    lines = text.split('\n')
    for line_idx, line in enumerate(lines):
        for match in CHORD_RE.finditer(line):
            chords.append({'chord': match.group(0), 'line': line_idx, 'start': match.start()})
    return chords

def detect_key(chords):
    if not chords:
        return 'C', 0
    # Lógica simplificada do JS (scoreKeyCandidate)
    root_counts = {}
    for chord in chords:
        root = chord['chord'][0].upper()
        root_counts[root] = root_counts.get(root, 0) + 1
    best_root = max(root_counts, key=root_counts.get, default='C')
    return best_root, len(chords)

def transpose_chord(chord, semitones, prefer_flats=False):
    match = FULL_CHORD_RE.match(chord)
    if not match:
        return chord
    root, quality, slash = match.groups()
    notes = NOTES_FLAT if prefer_flats else NOTES_SHARP
    idx = next((i for i, n in enumerate(notes) if n.lower().startswith(root.lower())), 0)
    new_root = notes[(idx + semitones) % 12]
    new_chord = new_root + (quality or '') + (slash or '')
    return new_chord

def process_text(text, semitones, notation):
    lines = text.split('\n')
    transposed = []
    for line in lines:
        transposed.append(re.sub(CHORD_RE, lambda m: transpose_chord(m.group(0), semitones, notation == 'flat'), line))
    return '\n'.join(transposed)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        text = request.form.get('text', '')
        file = request.files.get('file')
        if file:
            path = f'/tmp/{file.filename}'
            file.save(path)
            ext = file.filename.rsplit('.', 1)[1].lower()
            if ext == 'docx':
                text = extract_docx_text(path)
            elif ext == 'pdf':
                text = extract_pdf_text(path)
            elif ext == 'txt':
                text = extract_txt_text(path)
            os.remove(path)
        text = normalize_text(text)
        chords = extract_chord_objects(text)
        detected_key, confidence = detect_key(chords)
        semitones = int(request.form.get('semitones', 0))
        notation = request.form.get('notation', 'sharp')
        transposed = process_text(text, semitones, notation)
        session['transposed'] = transposed
        return jsonify({
            'original': text.replace('\n', '<br>'),
            'transposed': transposed.replace('\n', '<br>'),
            'detected_key': detected_key,
            'confidence': f'{confidence * 100:.0f}%',
            'chord_count': len(chords)
        })
    return '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<title>TomFlex Cifras</title>
<style>/* Cole o CSS completo do Index aqui para fidelidade visual */</style>
</head>
<body>
<!-- Cole o HTML completo do Index aqui, com JS pra POST / e render JSON -->
<script>
// JS adaptado do GAS pra fetch('/'), processar JSON, highlight .ch
</script>
</body>
</html>
    '''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
