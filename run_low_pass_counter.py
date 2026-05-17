import os
import subprocess
import sys
from pathlib import Path

from low_pass_counter import low_pass_counter


def find_accelerometer_csv_in_folder(folder_path: Path) -> Path:
    folder_path = Path(folder_path)
    if not folder_path.exists() or not folder_path.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    for entry in sorted(folder_path.iterdir()):
        if entry.is_file() and entry.name.lower().startswith("accelerometer") and entry.suffix.lower() == ".csv":
            return entry

    raise FileNotFoundError(f"No accelerometer CSV found in {folder_path}")


def open_file(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(path))
        return

    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.run([opener, str(path)], check=False)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    data_folder = project_root / "actual_data" / "8_siadow_05"

    csv_path = find_accelerometer_csv_in_folder(data_folder)
    output_path, repetitions = low_pass_counter(csv_path)

    print(f"CSV: {csv_path}")
    print(f"Plot saved: {output_path}")
    print(f"Estimated repetitions: {repetitions}")

    if output_path.exists():
        open_file(output_path)


if __name__ == "__main__":
    main()
