"""Legacy setuptools entry point for Python 3.9 environments.

The project also contains PEP 621 metadata in ``pyproject.toml``. This small
shim keeps editable installs and wheel builds working with the older setuptools
bundled with some macOS Python installations.
"""

from setuptools import find_packages, setup


setup(
    name="mixxx-api-bridge",
    version="0.1.0",
    description="HTTP-to-MIDI sidecar bridge for controlling Mixxx",
    url="https://github.com/alexyyyander/mixxx-api-bridge",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.9",
    package_dir={"": "src"},
    packages=find_packages("src"),
    include_package_data=True,
    package_data={"mixxx_api_bridge": ["mapping/*.xml", "mapping/*.js"]},
    extras_require={
        "midi": ["mido>=1.3.0", "python-rtmidi>=1.5.8"],
        "dev": ["pytest>=8.0"],
    },
    entry_points={
        "console_scripts": [
            "mixxx-api-bridge=mixxx_api_bridge.cli:main",
            "mixxx-api-bridge-install-mapping=mixxx_api_bridge.mapping_installer:main",
        ]
    },
)
