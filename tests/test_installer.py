from pathlib import Path
import importlib.resources as resources

from scripts.install_mapping import FILES, install


def test_install_mapping_to_explicit_destination(tmp_path: Path):
    destination = tmp_path / "controllers"
    install(destination)
    assert sorted(path.name for path in destination.iterdir()) == sorted(FILES)


def test_dry_run_does_not_create_destination(tmp_path: Path):
    destination = tmp_path / "not-created"
    install(destination, dry_run=True)
    assert not destination.exists()


def test_mapping_resources_are_packaged():
    root = resources.files("mixxx_api_bridge.mapping")
    assert all(root.joinpath(filename).is_file() for filename in FILES)
