from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_runtime_prewarm_dockerfile_keeps_zip_as_source_of_truth():
    dockerfile = (REPO_ROOT / "runpod" / "prewarm" / "Dockerfile.runtime").read_text(encoding="utf-8")

    assert "ARG BASE_IMAGE=runpod/comfyui:1.4.1-cuda12.8" in dockerfile
    assert "DC_PREWARMED_IMAGE=runtime-v1" in dockerfile
    assert "model_weights_baked" in dockerfile
    assert "DreamCatcher.zip" in dockerfile
    assert "HF_TOKEN" not in dockerfile
    assert "huggingface.co/" not in dockerfile
    assert "Qwen3.6-35B-A3B-FP8" not in dockerfile


def test_prewarmed_image_build_script_points_at_runtime_dockerfile():
    script = (REPO_ROOT / "runpod" / "build_prewarmed_image.ps1").read_text(encoding="utf-8")

    assert "prewarm\\Dockerfile.runtime" in script
    assert "BASE_IMAGE=$BaseImage" in script
    assert "PREWARM_CUSTOM_NODES=$customNodeFlag" in script
    assert "docker push" in script
