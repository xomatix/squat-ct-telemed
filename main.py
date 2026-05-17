import io
import os
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from low_pass_counter import low_pass_counter

app = FastAPI()
root_dir = Path(__file__).resolve().parent

static_dir = None
static_root_env = os.environ.get("STATIC_ROOT")
if static_root_env:
    static_dir = Path(static_root_env)
else:
    candidates = [
        Path.cwd() / "public_html",
        root_dir.parent / "public_html",
        Path.home() / "public_html",
        root_dir / "static",
    ]
    static_dir = next((candidate for candidate in candidates if candidate.exists()), root_dir / "static")

static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

OUTPUT_IMAGE_NAME = "latest_plot.png"
OUTPUT_IMAGE_PATH = static_dir / OUTPUT_IMAGE_NAME

INDEX_HTML = """<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Low-pass counter</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 0; padding: 0; background:#f7f7f7; }
    .page { max-width: 720px; margin: 0 auto; padding: 24px; }
    .card { background: #fff; border-radius: 12px; box-shadow: 0 12px 32px rgba(0,0,0,0.08); padding: 20px; }
    h1 { margin: 0 0 16px; font-size: 1.6rem; }
    label { display: block; margin-bottom: 10px; font-weight: 600; }
    input[type=file] { width: 100%; }
    button { margin-top: 14px; width: 100%; padding: 12px; border: none; border-radius: 8px; background: #2f69ff; color: #fff; font-size: 1rem; cursor: pointer; }
    button:disabled { opacity: 0.65; cursor: default; }
    .result { margin-top: 20px; }
    .result img { width: 100%; max-width: 100%; border-radius: 10px; margin-top: 12px; }
    .status { margin-top: 12px; font-size: 1rem; }
    .footer { margin-top: 24px; font-size: 0.9rem; color: #555; }
  </style>
</head>
<body>
  <div class="page">
    <div class="card">
      <h1>Low-pass Counter</h1>
      <p>Wgraj plik <code>.csv</code> lub <code>.zip</code> z plikiem Accelerometer.csv.</p>
      <label for="fileInput">Wybierz plik</label>
      <input id="fileInput" type="file" accept=".csv,.zip" />
      <button id="uploadButton" type="button">Prześlij i policz</button>
      <div class="result" id="result"></div>
      <div class="footer">Po załadowaniu zobaczysz liczbę powtórzeń oraz wygenerowany wykres.</div>
    </div>

    <div class="card" style="margin-top: 20px;">
      <h2>API docs</h2>
      <p><strong>POST</strong> <code>/api/upload</code></p>
      <p>Obsługiwane pliki:</p>
      <ul>
        <li><code>.csv</code> - pojedynczy plik Accelerometer.csv</li>
        <li><code>.zip</code> - archiwum zawierające plik <code>Accelerometer*.csv</code></li>
      </ul>
      <p>Form-data:</p>
      <pre style="background:#f4f4f4;padding:10px;border-radius:8px;">file: [plik.csv lub plik.zip]</pre>
      <p>Odpowiedź JSON:</p>
      <pre style="background:#f4f4f4;padding:10px;border-radius:8px;">{
  "repetitions": 12,
  "image_url": "/static/latest_plot.png"
}</pre>
      <p>Wygenerowany obraz jest dostępny pod ścieżką <code>/static/latest_plot.png</code>.</p>
    </div>
  </div>

  <script>
    const fileInput = document.getElementById('fileInput');
    const uploadButton = document.getElementById('uploadButton');
    const result = document.getElementById('result');

    uploadButton.addEventListener('click', async () => {
      if (!fileInput.files.length) {
        result.innerHTML = '<div class="status">Wybierz plik przed wysłaniem.</div>';
        return;
      }

      uploadButton.disabled = true;
      result.innerHTML = '<div class="status">Przetwarzanie...</div>';

      const formData = new FormData();
      formData.append('file', fileInput.files[0]);

      try {
        const response = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          const error = await response.text();
          throw new Error(error || 'Błąd serwera');
        }

        const data = await response.json();
        const timestamp = Date.now();
        result.innerHTML = `
          <div class="status"><strong>Policzono:</strong> ${data.repetitions}</div>
          <img src="${data.image_url}?t=${timestamp}" alt="Wykres pików" />
        `;
      } catch (err) {
        result.innerHTML = `<div class="status">Błąd: ${err.message}</div>`;
      } finally {
        uploadButton.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


def extract_accelerometer_csv_from_zip(data: bytes, temp_dir: Path) -> Path:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        candidates = []
        for name in zf.namelist():
            lower = Path(name).name.lower()
            if lower.endswith('.csv') and 'accelerometer' in lower:
                candidates.append(name)
        if not candidates:
            for name in zf.namelist():
                if Path(name).suffix.lower() == '.csv':
                    candidates.append(name)
        if not candidates:
            raise ValueError('Brak pliku CSV w archiwum ZIP.')

        source_name = candidates[0]
        dest_path = temp_dir / Path(source_name).name
        with zf.open(source_name) as source, open(dest_path, 'wb') as dest:
            dest.write(source.read())
        return dest_path


@app.get('/', response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(content=INDEX_HTML, status_code=200)


@app.post('/api/upload')
def upload_file(file: UploadFile = File(...)) -> JSONResponse:
    filename = file.filename or ''
    lower_name = filename.lower()

    with TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        if lower_name.endswith('.zip'):
            payload = file.file.read()
            try:
                csv_path = extract_accelerometer_csv_from_zip(payload, temp_dir)
            except (zipfile.BadZipFile, ValueError) as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        elif lower_name.endswith('.csv'):
            csv_path = temp_dir / Path(filename).name
            with open(csv_path, 'wb') as out_file:
                out_file.write(file.file.read())
        else:
            raise HTTPException(status_code=400, detail='Obsługiwane pliki: .csv lub .zip')

        try:
            output_path, repetitions = low_pass_counter(csv_path, output_path=OUTPUT_IMAGE_PATH)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    image_url = f'/static/{OUTPUT_IMAGE_NAME}'
    return JSONResponse(content={'repetitions': repetitions, 'image_url': image_url})
