# FastAPI low-pass counter

Prosty serwer FastAPI w `main.py`.

## Co robi

- `main.py` tworzy aplikację FastAPI i montuje katalog statyczny pod `/static`.
- statyczny katalog wybierany jest tak:
  - `STATIC_ROOT` z env, jeśli ustawione
  - `public_html` w katalogu roboczym lub w katalogu wyżej, jeśli istnieje
  - inaczej `./static` obok `main.py`
- endpointy:
  - `GET /` – zwraca prostą stronę HTML z formularzem uploadu
  - `POST /api/upload` – przyjmuje plik `.csv` lub `.zip` i zwraca JSON

## Jak działa `POST /api/upload`

- jeśli wysłany plik to `.csv`, zapisuje go tymczasowo i przekazuje do `low_pass_counter`
- jeśli `.zip`, wypakowuje pierwszy plik CSV z nazwą zawierającą `accelerometer`, albo dowolny plik `.csv`
- wynikowy wykres zapisuje jako `latest_plot.png` w katalogu statycznym
- odpowiedź JSON zawiera `repetitions` i `image_url`

## `low_pass_counter.py`

- ładuje CSV do DataFrame Pandas
- normalizuje nazwy kolumn do `time`, `seconds_elapsed`, `x`, `y`, `z`
- wybiera oś czasu (`seconds_elapsed`, `time`, albo indeks)
- oblicza wektorową wielkość przyspieszenia z osi `x`, `y`, `z`
- szuka lokalnych maksimów znaczonych jako powtórzenia za pomocą `scipy.signal.argrelextrema`
- tworzy wykres surowych osi z oznaczonymi szczytami
- zapisuje wykres i zwraca liczbę powtórzeń

## Start

```shell
cd squat-ct-telemed
python -m uvicorn main:app --reload
```

## Wejście/wyjście

- wejście: `file` w `multipart/form-data` (`.csv` lub `.zip`)
- wyjście: JSON z `repetitions` i `image_url`
- wykres: `/static/latest_plot.png`
