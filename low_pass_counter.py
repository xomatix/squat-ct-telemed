import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from scipy.signal import butter, filtfilt, argrelextrema
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


def normalize_accel_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for col in df.columns:
        key = col.strip().lower()
        if key == "time":
            mapping[col] = "time"
        elif key == "seconds_elapsed":
            mapping[col] = "seconds_elapsed"
        elif key == "x":
            mapping[col] = "x"
        elif key == "y":
            mapping[col] = "y"
        elif key == "z":
            mapping[col] = "z"
    return df.rename(columns=mapping)


def load_accelerometer_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = normalize_accel_columns(df)
    return df


def choose_time_axis(df: pd.DataFrame) -> tuple[np.ndarray, str]:
    if "seconds_elapsed" in df.columns:
        return df["seconds_elapsed"].astype(float).to_numpy(), "seconds_elapsed"
    if "time" in df.columns:
        return df["time"].astype(float).to_numpy(), "time"
    return np.arange(len(df), dtype=float), "index"


def compute_magnitude(df: pd.DataFrame) -> np.ndarray:
    x = df["x"].astype(float).to_numpy()
    y = df["y"].astype(float).to_numpy()
    z = df["z"].astype(float).to_numpy()
    return np.sqrt(x * x + y * y + z * z)


def lowpass_filter(signal: np.ndarray, fs: float, cutoff_hz: float = 5.0, order: int = 4) -> np.ndarray:
    if not SCIPY_AVAILABLE:
        raise RuntimeError("scipy.signal.butter and filtfilt required for lowpass_filter")

    signal = np.asarray(signal, dtype=float)
    if fs <= 0:
        raise ValueError("Sampling frequency must be positive")

    b, a = butter(order, cutoff_hz, btype='low', fs=fs)
    return filtfilt(b, a, signal)


def get_output_plot_path(csv_path: Path, output_path: Path | None = None) -> Path:
    csv_path = Path(csv_path)
    if output_path is None:
        output_path = csv_path.with_name(f"{csv_path.stem}_raw_peaks.png")
    return Path(output_path)


def plot_raw_axes_with_peaks(t: np.ndarray, df: pd.DataFrame, peaks: np.ndarray, title: str, axis_label: str) -> None:
    plt.figure(figsize=(10, 4))
    plt.plot(t, df["x"], label="x")
    plt.plot(t, df["y"], label="y")
    plt.plot(t, df["z"], label="z")
    if peaks.size:
        plt.scatter(t[peaks], df["x"].iloc[peaks], color="red", marker="o", s=50, label="peaks x")
        plt.scatter(t[peaks], df["y"].iloc[peaks], color="magenta", marker="^", s=50, label="peaks y")
        plt.scatter(t[peaks], df["z"].iloc[peaks], color="orange", marker="s", s=50, label="peaks z")
    plt.xlabel(axis_label)
    plt.ylabel("acceleration")
    plt.title(title)
    plt.legend()
    plt.tight_layout()


def low_pass_counter(csv_path: str | Path, output_path: str | Path | None = None) -> tuple[Path, int]:
    csv_path = Path(csv_path)
    df = load_accelerometer_csv(csv_path)

    missing_axes = [axis for axis in ["x", "y", "z"] if axis not in df.columns]
    if missing_axes:
        raise RuntimeError(f"Missing required axes columns: {missing_axes}")

    t, axis_label = choose_time_axis(df)
    raw_magnitude = compute_magnitude(df)
    fs = estimate_sampling_frequency(t)

    filtered_magnitude = lowpass_filter(raw_magnitude, fs, cutoff_hz=5.0, order=4)
    threshold = np.mean(filtered_magnitude) + 0.1 * np.std(filtered_magnitude)
    peaks, _ = find_reps(
        filtered_magnitude,
        fs,
        order=10,
        threshold=threshold,
        min_interval_s=0.35,
        min_drop_ratio=0.4,
    )

    output_path = get_output_plot_path(csv_path, Path(output_path) if output_path is not None else None)
    plot_raw_axes_with_peaks(
        t,
        df,
        peaks,
        f"{csv_path.name} - Raw accelerometer axes with detected peaks",
        axis_label,
    )
    plt.savefig(output_path, dpi=150)
    plt.close()

    peak_count = max(peaks.size - 1, 0)
    reps = int(math.ceil(peak_count / 2))
    return output_path, reps


def estimate_sampling_frequency(t: np.ndarray) -> float:
    if len(t) < 2:
        return 50.0
    dt = np.diff(t)
    dt = dt[dt > 0]
    if len(dt) == 0:
        return 50.0
    return 1.0 / np.median(dt)


def prune_peaks(arr: np.ndarray, peaks: np.ndarray, fs: float, min_interval_s: float = 0.35, min_drop_ratio: float = 0.4) -> tuple[np.ndarray, np.ndarray]:
    if peaks.size == 0:
        return peaks, np.array([], dtype=int)

    arr = np.asarray(arr, dtype=float)
    min_samples = int(round(fs * min_interval_s)) if fs > 0 else 0
    groups = [[int(peaks[0])]]
    valleys: list[int] = []

    for idx in peaks[1:]:
        last = groups[-1][-1]
        if min_samples and idx - last < min_samples:
            groups[-1].append(int(idx))
            continue

        slice_start = last
        slice_end = idx + 1
        region = arr[slice_start:slice_end]
        valley_rel = int(np.argmin(region))
        valley_idx = slice_start + valley_rel
        valley = arr[valley_idx]
        last_val = arr[last]
        cur_val = arr[idx]

        drop_last = 1.0 - valley / max(last_val, 1e-9)
        drop_cur = 1.0 - valley / max(cur_val, 1e-9)
        rise = cur_val / max(valley, 1e-9)

        if drop_last < min_drop_ratio or drop_cur < min_drop_ratio or rise < 1.4:
            groups[-1].append(int(idx))
            continue

        valleys.append(valley_idx)
        groups.append([int(idx)])

    kept = []
    for group in groups:
        best = group[np.argmax(arr[group])]
        kept.append(int(best))
    return np.array(kept, dtype=int), np.array(valleys, dtype=int)


def find_reps(signal: np.ndarray, fs: float, order: int = 10, threshold: float | None = None, min_interval_s: float = 0.35, min_drop_ratio: float = 0.4) -> tuple[np.ndarray, np.ndarray]:
    if not SCIPY_AVAILABLE:
        raise RuntimeError("scipy.signal.argrelextrema required for find_reps")

    arr = np.asarray(signal, dtype=float)
    if arr.size < 3:
        return np.array([], dtype=int), np.array([], dtype=int)

    maxima = argrelextrema(arr, np.greater, order=order)[0]
    if threshold is not None:
        maxima = maxima[arr[maxima] >= threshold]
    peaks, valleys = prune_peaks(arr, maxima, fs, min_interval_s=min_interval_s, min_drop_ratio=min_drop_ratio)
    return peaks, valleys
