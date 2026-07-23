import os
import sys
import zipfile

# Add repository root to sys.path to allow importing from scripts
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.build_retirement_admission_lambda import build


def test_zip_contains_correct_files_and_structure() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    zip_path = os.path.join(repo_root, "dist", "retirement_admission_lambda.zip")
    
    build()
    
    assert os.path.exists(zip_path)
    
    with zipfile.ZipFile(zip_path, "r") as z:
        namelist = z.namelist()
        
        assert "latch/__init__.py" in namelist
        assert "latch/infrastructure/retirement_admission_lambda_entrypoint.py" in namelist
        assert any(name.startswith("pydantic/") for name in namelist)
        assert not any(name.startswith("src/") for name in namelist)
        assert not any("test" in name for name in namelist if name.startswith("latch/"))
        assert not any("__pycache__" in name for name in namelist)
