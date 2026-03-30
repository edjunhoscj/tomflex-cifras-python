# requirements.txt (simulado em comentários)
# Flask==2.3.3
# python-docx==1.1.0
# pdfplumber==0.9.0
# PyMuPDF==1.23.3
# Jinja2==3.1.2

# app.py

from flask import Flask, render_template, request, jsonify, session
import os
import re
import json
from docx import Document
import pdfplumber
import fitz  # PyMuPDF

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Para sessões

# Regex patterns (portados do JS)
CHORD_RE = re.compile(r'\b([A-G](#|b)?)(m|maj|min|dim|aug|sus|add|7|9|11|13|6|5|4|2)?(/([A-G](#|b)?))?\b', re.IGNORECASE)
FULL_CHORD_RE = re.compile(r'\b([A-G](#|b)?)(m|maj|min|dim|aug|sus|add|7|9|11|13|6|5|4|2)?(/([A-G](#|b)?))?\b', re.IGNORECASE)

# Notas musicais
NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
FLAT_NOTES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

# Função para extrair texto de DOCX
def extract_docx_text(file_path):
    doc = Document(file_path)
    text = '\n'.join([para.text for para in doc.paragraphs])
    return text

# Função para extrair texto de TXT
def extract_txt_text(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

# Função para extrair texto de PDF preservando layout
def extract_pdf_text(file_path):
    doc = fitz.open(file_path)
    text_blocks = []
    for page in doc:
        blocks = page.get_text('dict')['blocks']
        lines = {}
        for block in blocks:
            if 'lines' in block:
                for line in block['lines']:
                    y = round(line['bbox'][1], 0)  # Agrupar por Y
                    if y not in lines:
                        lines[y] = []
                    for span in line['spans']:
                        lines[y].append((span['bbox'][0], span['text']))
        # Ordenar linhas por Y
        sorted_lines = sorted(lines.items())
        for y, tokens in sorted_lines:
            sorted_tokens = sorted(tokens, key=lambda x: x[0])
            line_text = ''
            prev_x = 0
            for x, token in sorted_tokens:
                spaces = max(0, int((x - prev_x) / 10))  # Espaços proporcionais
                line_text += ' ' * spaces + token
                prev_x = x + len(token) * 10  # Aproximação
            text_blocks.append(line_text)
    return '\n'.join(text_blocks)

# Normalizar texto
def normalize_text(text):
    text = text.replace('\r', '').replace('\u00A0', ' ')
    text = re.sub(r'\n+', '\n', text)
    return text.strip()

# Função para extrair objetos de acordes (portada de extractChordObjectsFromText)
def extract_chord_objects_from_text(text):
    chords = []
    lines = text.split('\n')
    for line_idx, line in enumerate(lines):
        matches = list(CHORD_RE.finditer(line))
        for match in matches:
            chord = match.group(0)
            start = match.start()
            chords.append({
                'chord': chord,
                'line': line_idx,
                'start': start,
                'end': match.end()
            })
    return chords

# Função para pontuar candidato de tom (portada de scoreKeyCandidate)
def score_key_candidate(chords, key):
    score = 0
    tonic_hits = 0
    # Lógica simplificada: contar ocorrências de acordes na escala
    major_pattern = [0, 2, 4, 5, 7, 9, 11]  # Semitons
    minor_pattern = [0, 2, 3, 5, 7, 8, 10]
    pattern = major_pattern if 'm' not in key.lower() else minor_pattern
    root_note = key[0].upper() + key[1:] if len(key) > 1 else key.upper()
    root_idx = NOTES.index(root_note) if root_note in NOTES else FLAT_NOTES.index(root_note)
    scale_notes = [(root_idx + p) % 12 for p in pattern]
    for chord_obj in chords:
        chord_root = chord_obj['chord'][0].upper()
        if chord_root in NOTES:
            idx = NOTES.index(chord_root)
        elif chord_root in FLAT_NOTES:
            idx = FLAT_NOTES.index(chord_root)
        else:
            continue
        if idx in scale_notes:
            score += 1
            if idx == root_idx:
                tonic_hits += 1
    return score, tonic_hits

# Função para detectar tom provável (portada de detectLikelyKey)
def detect_likely_key(chords):
    candidates = []
    for note in NOTES + FLAT_NOTES:
        for mode in ['', 'm']:
            key = note + mode
            score, tonic_hits = score_key_candidate(chords, key)
            candidates.append((key, score, tonic_hits))
    # Ordenar por score, depois tonic_hits
    candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return candidates[0][0] if candidates else 'C'

# Função para classificar linha (portada de classifyLine)
def classify_line(line):
    if CHORD_RE.search(line):
        return 'chord'
    elif line.strip():
        return 'lyric'
    else:
        return 'empty'

# Função para transpor acorde (portada de transposeChord)
def transpose_chord(chord, semitones, prefer_sharps=True):
    # Lógica simplificada
    root_match = re.match(r'^([A-G](#|b)?)', chord, re.IGNORECASE)
    if not root_match:
        return chord
    root = root_match.group(0).upper()
    notes = NOTES if prefer_sharps else FLAT_NOTES
    idx = notes.index(root) if root in notes else 0
    new_idx = (idx + semitones) % 12
    new_root = notes[new_idx]
    return new_root + chord[len(root):]

# Função para transpor linha (portada de transposeChordLine)
def transpose_chord_line(line, semitones, prefer_sharps=True):
    def replace_chord(match):
        return transpose_chord(match.group(0), semitones, prefer_sharps)
    return CHORD_RE.sub(replace_chord, line)

# Função para transpor inline (portada de transposeInlineLine)
def transpose_inline_line(line, semitones, prefer_sharps=True):
    # Similar a chord line
    return transpose_chord_line(line, semitones, prefer_sharps)

# Função para validar linhas (portada de validateLines)
def validate_lines(lines):
    suspicious = []
    for idx, line in enumerate(lines):
        if classify_line(line) == 'chord' and len(CHORD_RE.findall(line)) > 5:
            suspicious.append(idx)
    return suspicious

# Função para contar acordes
def count_chords(chords):
    count = {}
    for chord_obj in chords:
        chord = chord_obj['chord']
        count[chord] = count.get(chord, 0) + 1
    return count

# Função para renderizar HTML com highlights
def render_highlighted_html(text, chords, transposed_chords=None):
    lines = text.split('\n')
    html = ''
    for line_idx, line in enumerate(lines):
        line_html = line
        # Inserir spans para acordes
        offset = 0
        for chord_obj in [c for c in chords if c['line'] == line_idx]:
            start = chord_obj['start'] + offset
            end = chord_obj['end'] + offset
            chord_html = f"<span class='ch'>{chord_obj['chord']}</span>"
            line_html = line_html[:start] + chord_html + line_html[end:]
            offset += len(chord_html) - (end - start)
        # Para transpostos, adicionar .new se diferente
        if transposed_chords:
            # Similar lógica
            pass  # Simplificado
        html += f"<div>{line_html}</div>"
    return html

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    text = ''
    if 'file' in request.files:
        file = request.files['file']
        if file.filename:
            file_path = os.path.join('/tmp', file.filename)
            file.save(file_path)
            ext = file.filename.split('.')[-1].lower()
            if ext == 'docx':
                text = extract_docx_text(file_path)
            elif ext == 'txt':
                text = extract_txt_text(file_path)
            elif ext == 'pdf':
                text = extract_pdf_text(file_path)
            os.remove(file_path)
    elif 'text' in request.form:
        text = request.form['text']
    
    text = normalize_text(text)
    chords = extract_chord_objects_from_text(text)
    detected_key = detect_likely_key(chords)
    semitones = int(request.form.get('semitones', 0))
    prefer_sharps = request.form.get('prefer_sharps', 'true') == 'true'
    mode = request.form.get('mode', 'faithful')
    
    # Transpor
    transposed_text = '\n'.join([transpose_chord_line(line, semitones, prefer_sharps) for line in text.split('\n')])
    transposed_chords = extract_chord_objects_from_text(transposed_text)
    
    # Análise
    chord_count = count_chords(chords)
    suspicious_lines = validate_lines(text.split('\n'))
    confidence = len(chords) / len(text.split()) if text.split() else 0
    
    # HTML
    original_html = render_highlighted_html(text, chords)
    transposed_html = render_highlighted_html(transposed_text, transposed_chords)
    
    # Salvar em sessão
    session['original_text'] = text
    session['transposed_text'] = transposed_text
    
    return jsonify({
        'original_highlighted': original_html,
        'transposed_highlighted': transposed_html,
        'detected_key': detected_key,
        'chord_count': chord_count,
        'suspicious_lines': suspicious_lines,
        'confidence': confidence
    })

if __name__ == '__main__':
    app.run(debug=True)

# templates/index.html
"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>TomFlex Cifras</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <div class="hero">TomFlex Cifras V2.1.1</div>
    <div class="sidebar">
        <form id="upload-form" enctype="multipart/form-data">
            <input type="file" name="file" accept=".docx,.pdf,.txt">
            <textarea name="text" placeholder="Ou cole o texto aqui"></textarea>
            <input type="number" name="semitones" placeholder="Semitons" value="0">
            <select name="prefer_sharps">
                <option value="true">Prefer Sharps</option>
                <option value="false">Prefer Flats</option>
            </select>
            <select name="mode">
                <option value="faithful">Faithful</option>
                <option value="editable">Editable</option>
            </select>
            <button type="submit">Processar</button>
        </form>
        <div id="analysis-grid">
            <!-- Análise será preenchida via JS -->
        </div>
    </div>
    <div class="main">
        <div id="original-viewer"></div>
        <div id="transposed-viewer"></div>
        <div id="warnings"></div>
    </div>
    <script src="{{ url_for('static', filename='js/app.js') }}"></script>
</body>
</html>
"""

# static/css/style.css
"""
body { background: #121212; color: #fff; font-family: Arial; }
.hero { background: #333; padding: 20px; text-align: center; }
.sidebar { width: 300px; float: left; padding: 20px; }
.main { margin-left: 320px; padding: 20px; }
.ch { color: #ff0; }
.new { color: #0f0; }
/* Adicionar mais CSS para dark theme, layout idêntico */
"""

# static/js/app.js
"""
document.getElementById('upload-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    fetch('/process', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('original-viewer').innerHTML = data.original_highlighted;
        document.getElementById('transposed-viewer').innerHTML = data.transposed_highlighted;
        // Preencher analysis-grid, warnings
        // Adicionar botões copiar, download, print
    });
});

// Funções para copiar, download TXT, print
"""
