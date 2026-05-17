# FastAPI low-pass counter

Prosty serwer FastAPI w `main.py`.

## Co robi

- `main.py` montuje ścieżkę `/static` i udostępnia stronę startową z uploadem.
- `GET /` zwraca formularz HTML.
- `POST /api/upload` przyjmuje plik `.csv` i zwraca wynikową liczbę powtórzeń.

## Pseudokod licznika

```python
# main.py
if request.path == '/api/upload' and method == 'POST':
    file = request.file
    csv_path = save_temp_csv(file)

    output_path, repetitions = low_pass_counter(csv_path, output_path=static/'latest_plot.png')
    return {'repetitions': repetitions, 'image_url': '/static/latest_plot.png'}
```

```python
# low_pass_counter.py
df = load_csv(csv_path)
df = normalize_columns(df)
t, axis_label = choose_time_axis(df)
raw_magnitude = compute_magnitude(df)
fs = estimate_sampling_frequency(t)
filtered = lowpass_filter(raw_magnitude, fs, cutoff_hz=5.0)
peaks = find_peaks(filtered)
reps = count_repetitions(peaks)
plot_raw_axes_with_peaks(t, df, peaks)
save_plot(output_path)
return output_path, reps
```

## Najważniejsze funkcje

- `load_accelerometer_csv` — czyta CSV do Pandas DataFrame.
- `normalize_accel_columns` — zmienia nazwy kolumn na `time`, `seconds_elapsed`, `x`, `y`, `z`.
- `choose_time_axis` — wybiera oś czasu z `seconds_elapsed` lub `time` albo indeksu.
- `compute_magnitude` — oblicza długość wektora `sqrt(x^2+y^2+z^2)`.
- `lowpass_filter` — filtruje amplitudę Butterworthem przez `butter` + `filtfilt`.
- `find_reps` — wyszukuje lokalne maksima i zwraca piki.
- `plot_raw_axes_with_peaks` — rysuje osie `x,y,z` i oznacza znalezione piki.

## Start

```shell
cd squat-ct-telemed
python -m uvicorn main:app --reload
```

## Wejście/wyjście

- wejście: `file` w `multipart/form-data` (`.csv`)
- wyjście: JSON z `repetitions` i `image_url`
- wykres: `/static/latest_plot.png`
