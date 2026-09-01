import json
import shutil
import subprocess
from pathlib import Path

import pytest

from mixxx_api_bridge.protocol import (
    OP_ACK,
    OP_ACTION,
    OP_COMMAND,
    OP_FEEDBACK,
    OP_HELLO,
    OP_SETTING_GET,
    OP_SETTING_VALUE,
    decode_frame,
    encode_frame,
)


NODE_HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const incoming = JSON.parse(process.argv[2]);
const output = [];
const values = {};
const triggerCalls = [];
const key = (group, name) => group + '/' + name;
const context = {
  midi: { sendSysexMsg: (frame) => output.push(frame) },
  engine: {
    getParameter: (group, name) => values[key(group, name)] ?? 0,
    setParameter: (group, name, value) => { values[key(group, name)] = Number(value); },
    getValue: (group, name) => values[key(group, name)] ?? 0,
    setValue: (group, name, value) => { values[key(group, name)] = Number(value); },
    trigger: (group, name) => { values[key(group, name)] = 1; },
    reset: (group, name) => { values[key(group, name)] = 0; },
    getSetting: (name) => name === 'test_setting' ? 'enabled' :
      (name === 'triggerDelayMs' ? 350 : undefined),
    makeConnection: () => ({ disconnect: () => {}, trigger: () => {} })
  },
  script: {
    triggerControl: (group, name, delay) => {
      triggerCalls.push([group, name, delay]);
      values[key(group, name)] = 1;
    },
    toggleControl: (group, name) => { values[key(group, name)] = values[key(group, name)] ? 0 : 1; }
  }
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
context.MixxxApiBridge.incomingData(incoming, incoming.length);
process.stdout.write(JSON.stringify({ output, values, triggerCalls }));
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


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_mapping_supports_actions_and_mapping_settings():
    script_path = Path(__file__).parents[1] / "src/mixxx_api_bridge/mapping/MixxxApiBridge-scripts.js"

    def run(frame):
        result = subprocess.run(
            ["node", "-e", NODE_HARNESS, str(script_path), json.dumps(frame)],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    action_result = run(
        encode_frame(
            OP_ACTION,
            {
                "request_id": "action-1",
                "action": "toggle",
                "group": "[Channel1]",
                "key": "play",
                "scale": "normalized",
            },
        )
    )
    assert [decode_frame(frame)[0] for frame in action_result["output"]] == [OP_ACK, OP_FEEDBACK]
    assert action_result["values"]["[Channel1]/play"] == 1

    trigger_result = run(
        encode_frame(
            OP_ACTION,
            {
                "request_id": "trigger-1",
                "action": "trigger",
                "group": "[Channel1]",
                "key": "beatjump_forward",
                "scale": "normalized",
            },
        )
    )
    assert trigger_result["triggerCalls"] == [["[Channel1]", "beatjump_forward", 350]]

    setting_result = run(
        encode_frame(OP_SETTING_GET, {"request_id": "setting-1", "name": "test_setting"})
    )
    operation, payload = decode_frame(setting_result["output"][0])
    assert operation == OP_SETTING_VALUE
    assert payload == {
        "found": True,
        "name": "test_setting",
        "request_id": "setting-1",
        "value": "enabled",
    }
