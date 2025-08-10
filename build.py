import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def ensure_pyinstaller_available() -> None:
    try:
        import PyInstaller  # noqa: F401
    except Exception:
        print("PyInstaller is not installed. Installing now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])  # raises on failure


def clean_artifacts(project_root: Path, remove_spec: bool) -> None:
    build_dir = project_root / "build"
    dist_dir = project_root / "dist"
    spec_file = project_root / "fsffb.spec"

    for path in (build_dir, dist_dir):
        if path.exists():
            print(f"Removing {path}...")
            shutil.rmtree(path, ignore_errors=True)

    if remove_spec and spec_file.exists():
        print(f"Removing {spec_file}...")
        spec_file.unlink(missing_ok=True)


def build_with_cli(
    project_root: Path,
    onefile: bool,
    console: bool,
    name: str,
    icon_path: Path | None,
) -> None:
    ensure_pyinstaller_available()

    main_script = project_root / "main.py"
    if not main_script.exists():
        raise FileNotFoundError(f"Entry point not found: {main_script}")

    # Windows uses ';' separator for --add-data/--add-binary, others use ':'
    sep = ";" if sys.platform.startswith("win") else ":"

    user_presets = project_root / "user_presets.json"
    hid_dll = project_root / "hidapi.dll"
    simconnect_dll = project_root / "SimConnect.dll"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--name",
        name,
    ]

    cmd.append("--onefile" if onefile else "--onedir")
    cmd.append("--console" if console else "--windowed")

    if icon_path and icon_path.exists():
        cmd += ["--icon", str(icon_path)]

    # Always include essential runtime data if present
    if user_presets.exists():
        cmd += ["--add-data", f"{user_presets}{sep}."]
    if hid_dll.exists():
        cmd += ["--add-binary", f"{hid_dll}{sep}."]
    if simconnect_dll.exists():
        cmd += ["--add-binary", f"{simconnect_dll}{sep}."]
    else:
        # Allow overriding location via env var SIMCONNECT_DLL
        env_path = os.environ.get("SIMCONNECT_DLL", "").strip()
        if env_path:
            p = Path(env_path)
            if p.exists():
                cmd += ["--add-binary", f"{p}{sep}."]
            else:
                print(f"Warning: SIMCONNECT_DLL set but file not found: {p}")

    # Hidden imports that PyInstaller sometimes misses for PyQt6/graph
    hidden_imports = [
        "PyQt6.sip",
        "pyqtgraph",
    ]
    for hi in hidden_imports:
        cmd += ["--hidden-import", hi]

    # Ensure SimConnect package data (e.g., scvars.json) is bundled
    # Prefer PyInstaller's collect options when available
    cmd += ["--collect-all", "SimConnect"]
    cmd += ["--collect-submodules", "SimConnect"]
    cmd += ["--collect-data", "SimConnect"]

    # Fallback: explicitly add scvars.json into SimConnect package
    try:
        import SimConnect  # type: ignore

        sim_pkg_dir = Path(SimConnect.__file__).parent
        scvars = sim_pkg_dir / "scvars.json"
        if scvars.exists():
            cmd += ["--add-data", f"{scvars}{sep}SimConnect"]
        datadef = sim_pkg_dir / "datadef.json"
        if datadef.exists():
            cmd += ["--add-data", f"{datadef}{sep}SimConnect"]
        # Some dists ship the DLL inside the package
        pkg_sim_dll = sim_pkg_dir / "SimConnect.dll"
        if pkg_sim_dll.exists() and not simconnect_dll.exists():
            cmd += ["--add-binary", f"{pkg_sim_dll}{sep}."]
    except Exception:
        # If import fails at build time, we still proceed; runtime will error if package is missing
        pass

    cmd.append(str(main_script))

    print("Running:")
    print(" ", " ".join(cmd))
    subprocess.check_call(cmd)


def build_with_spec(project_root: Path) -> None:
    ensure_pyinstaller_available()
    spec_file = project_root / "fsffb.spec"
    if not spec_file.exists():
        raise FileNotFoundError("fsffb.spec not found. Run without --use-spec to build directly.")

    # NOTE: The existing spec file may contain absolute paths. It currently points to this workspace
    # path. If you move the project, prefer building without --use-spec.
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec_file)]
    print("Running:")
    print(" ", " ".join(cmd))
    subprocess.check_call(cmd)


def main():
    project_root = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(description="Build FSFFB distribution with PyInstaller")
    parser.add_argument("--clean", action="store_true", help="Remove previous build/dist (and optionally spec)")
    parser.add_argument("--remove-spec", action="store_true", help="Also remove fsffb.spec on clean")
    parser.add_argument("--use-spec", action="store_true", help="Build using existing fsffb.spec")
    parser.add_argument("--onefile", action="store_true", help="Create a single-file executable")
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="Build without console window (default is console)",
    )
    parser.add_argument("--name", default="FSFFB", help="Executable/app name")
    parser.add_argument("--icon", type=str, default="", help="Path to .ico file")

    args = parser.parse_args()

    if args.clean:
        clean_artifacts(project_root, remove_spec=args.remove_spec)

    if args.use_spec:
        build_with_spec(project_root)
    else:
        build_with_cli(
            project_root=project_root,
            onefile=args.onefile,
            console=not args.windowed,
            name=args.name,
            icon_path=Path(args.icon) if args.icon else None,
        )

    dist_dir = project_root / "dist" / args.name
    exe_candidate = dist_dir / (f"{args.name}.exe" if sys.platform.startswith("win") else args.name)
    if dist_dir.exists():
        print(f"\nBuild complete. Distribution directory: {dist_dir}")
        if exe_candidate.exists():
            print(f"Executable: {exe_candidate}")
    else:
        print("\nBuild process finished, but dist directory was not found. Check output above for errors.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as err:
        print(f"Build failed with exit code {err.returncode}")
        sys.exit(err.returncode)
    except Exception as exc:
        print(f"Build failed: {exc}")
        sys.exit(1)

