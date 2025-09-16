# app.py - Flask Web App for Local CFG Visualization
# Run this with: python app.py
# Then visit http://127.0.0.1:5000/ in your browser

from flask import Flask, render_template_string, request, send_file
import os
import tempfile
import subprocess
import sys
from io import BytesIO

# Add the parent directory to sys.path to import CFG modules (assuming structure from provided code)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import the CFGBuilder (assuming it's in CFG/cfg_builder.py as per the code)
from CFG.cfg_builder import CFGBuilder
from CFG.cfg_node import CFGNode  # If needed for type hints

app = Flask(__name__)

# HTML Template as string (simple form with textarea and image display)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Python CFG Visualizer</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        textarea { width: 100%; height: 300px; font-family: monospace; }
        button { padding: 10px 20px; background: #007bff; color: white; border: none; cursor: pointer; }
        button:hover { background: #0056b3; }
        #output { margin-top: 20px; }
        img { max-width: 100%; height: auto; border: 1px solid #ddd; }
        .error { color: red; }
    </style>
</head>
<body>
    <h1>Python Control Flow Graph (CFG) Visualizer</h1>
    <p>Enter Python code below and click "Generate CFG" to see the visual graph.</p>
    <form method="POST">
        <textarea name="code" placeholder="# Example:\nif x > 0:\n    print('Positive')\nelse:\n    print('Non-positive')">{{ code }}</textarea><br><br>
        <button type="submit">Generate CFG</button>
    </form>
    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}
    {% if image_data %}
        <div id="output">
            <h2>Generated CFG Graph:</h2>
            <img src="data:image/png;base64,{{ image_data }}" alt="CFG Graph">
        </div>
    {% endif %}
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    code = ""
    error = None
    image_data = None

    if request.method == 'POST':
        code = request.form.get('code', '')
        if code.strip():
            try:
                # Build CFG using the provided CFGBuilder
                builder = CFGBuilder()
                entry_node = builder.build_cfg(code)

                if entry_node:
                    # Generate DOT string
                    dot_output = builder.to_dot(show_statement_text=True)

                    # Use Graphviz to convert DOT to PNG in memory
                    dot_process = subprocess.Popen(
                        ['dot', '-Tpng'],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    png_output, stderr = dot_process.communicate(input=dot_output.encode('utf-8'))

                    if dot_process.returncode == 0:
                        # Encode PNG to base64 for inline display
                        image_data = png_output.hex()  # Simple hex for demo; use base64.b64encode(png_output).decode() for proper base64
                        import base64
                        image_data = base64.b64encode(png_output).decode('utf-8')
                    else:
                        error = f"Graphviz error: {stderr.decode('utf-8')}"
                else:
                    error = "Failed to generate CFG. Check for syntax errors in the code."
            except Exception as e:
                error = f"Error processing code: {str(e)}"
        else:
            error = "Please enter some Python code."

    return render_template_string(HTML_TEMPLATE, code=code, error=error, image_data=image_data)

if __name__ == '__main__':
    # Ensure Graphviz is installed (run: pip install graphviz or install system-wide)
    print("Starting local CFG Visualizer at http://127.0.0.1:5000/")
    print("Note: Install Graphviz if not available (e.g., brew install graphviz on macOS).")
    app.run(debug=True, host='127.0.0.1', port=5000)