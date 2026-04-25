import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "files" / "config.yaml.j2"
RENDER = ROOT / "files" / "render-config.py"


def render_config(tmp_path, **extra_env):
    output = tmp_path / "config.yaml"
    env = os.environ.copy()
    env.update({
        "TERMINAL_SSH_KEY": "/tmp/test-key",
        "HERMES_DEFAULT_MODEL": "test/model",
    })
    env.update(extra_env)
    subprocess.run(
        [os.sys.executable, str(RENDER), str(TEMPLATE), str(output)],
        check=True,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    return output.read_text()


def test_image_gen_section_omitted_without_env(tmp_path):
    rendered = render_config(tmp_path)

    assert "\nimage_gen:" not in rendered


def test_image_gen_renders_model_and_gateway_flag(tmp_path):
    rendered = render_config(
        tmp_path,
        HERMES_IMAGE_GEN_MODEL="fal-ai/gpt-image-2",
        HERMES_IMAGE_GEN_USE_GATEWAY="true",
    )

    assert "image_gen:" in rendered
    assert 'model: "fal-ai/gpt-image-2"' in rendered
    assert "use_gateway: true" in rendered


def test_image_gen_yaml_override_wins(tmp_path):
    rendered = render_config(
        tmp_path,
        HERMES_IMAGE_GEN_YAML='{"use_gateway":false,"model":"fal-ai/flux-2-pro"}',
        HERMES_IMAGE_GEN_MODEL="fal-ai/gpt-image-2",
        HERMES_IMAGE_GEN_USE_GATEWAY="true",
    )

    assert 'image_gen: {"use_gateway":false,"model":"fal-ai/flux-2-pro"}' in rendered
    assert 'model: "fal-ai/gpt-image-2"' not in rendered
