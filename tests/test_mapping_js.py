import json
import shutil
import subprocess
from pathlib import Path

import pytest

from mixxx_api_bridge.protocol import OP_COMMAND, encode_frame


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_mapping_js_frame_matches_python_protocol():
    script_path = Path(__file__).parents[1] / "src/mixxx_api_bridge/mapping/MixxxApiBridge-scripts.js"
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const context = { midi: { sendSysexMsg: () => {} }, engine: {} };
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
process.stdout.write(JSON.stringify(context.MixxxApiBridge._frame(1, {
  group: '[Channel1]', key: 'volume', value: 0.5, scale: 'normalized'
})));
"""
    result = subprocess.run(
        ["node", "-e", node_script, str(script_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == encode_frame(
        OP_COMMAND,
        {"group": "[Channel1]", "key": "volume", "value": 0.5, "scale": "normalized"},
    )
