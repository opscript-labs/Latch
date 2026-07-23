import os
import shutil
import subprocess
import sys
import zipfile


def build() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    staging_dir = os.path.join(repo_root, ".build_staging_retirement_admission")
    dist_dir = os.path.join(repo_root, "dist")
    zip_path = os.path.join(dist_dir, "retirement_admission_lambda.zip")

    if os.path.exists(staging_dir):
        shutil.rmtree(staging_dir)
    os.makedirs(staging_dir)

    if not os.path.exists(dist_dir):
        os.makedirs(dist_dir)

    try:
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--target",
                staging_dir,
                "pydantic>=2.11.0",
                "boto3>=1.40.0",
            ],
            check=True,
        )

        src_latch = os.path.join(repo_root, "src", "latch")
        dest_latch = os.path.join(staging_dir, "latch")
        shutil.copytree(src_latch, dest_latch)

        for root, dirs, _files in os.walk(staging_dir):
            for d in list(dirs):
                if d in ("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"):
                    shutil.rmtree(os.path.join(root, d))
                    dirs.remove(d)

        if os.path.exists(zip_path):
            os.remove(zip_path)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(staging_dir):
                for f in files:
                    filepath = os.path.join(root, f)
                    arcname = os.path.relpath(filepath, staging_dir)
                    z.write(filepath, arcname)

        print(f"Successfully packaged Lambda ZIP to: {zip_path}")

    except Exception as e:
        print(f"Failed to build Lambda package: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if os.path.exists(staging_dir):
            shutil.rmtree(staging_dir)


if __name__ == "__main__":
    build()
