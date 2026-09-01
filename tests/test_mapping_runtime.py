import json
import shutil
import subprocess
from pathlib import Path

import pytest

from mixxx_api_bridge.protocol import OP_ACK, OP_COMMAND, OP_FEEDBACK, OP_HELLO, decode_frame, encode_frame


NODE_HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const incoming = JSON.parse(process.argv[2]);
const output = [];
const values = {};
const key = (group, name) => group + '/' + name;
const context = {
  midi: { sendSysexMsg: (frame) => output.push(frame) },
  engine: {
    getParameter: (group, name) => values[key(group, name)] ?? 0,
    setParameter: (group, name, value) => { values[key(group, name)] = Number(value); },
    getValue: (group, name) => values[key(group, name)] ?? 0,
    setValue: (group, name, value) => { values[key(group, name)] = Number(value); },
    makeConnection: () => ({ disconnect: () => {}, trigger: () => {} })
  }
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
context.MixxxApiBridge.incomingData(incoming, incoming.length);
process.stdout.write(JSON.stringify({ output, values }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_mapping_replies_to_hello_and_applies_command():
    script_path = Path(__file__).parents[1] / "src/mixxx_api_bridge/mapping/MixxxApiBridge-scripts.js"
    hello_frame = encode_frame(OP_HELLO, {"request_id": "hello-1", "client": "test", "protocol": 1})
    command_frame = encode_frame(
        OP_COMMAND,
        {
            "request_id": "command-1",
            "group": "[Channel1]",
            "key": "volume",
            "value": 0.75,
            "scale": "normalized",
        },
    )

    def run(frame):
        result = subprocess.run(
            ["node", "-e", NODE_HARNESS, str(script_path), json.dumps(frame)],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    hello_result = run(hello_frame)
    assert decode_frame(hello_result["output"][0])[0] == 0x10

    command_result = run(command_frame)
    operations = [decode_frame(frame)[0] for frame in command_result["output"]]
    assert operations == [OP_ACK, OP_FEEDBACK]
    assert command_result["values"]["[Channel1]/volume"] == 0.75
