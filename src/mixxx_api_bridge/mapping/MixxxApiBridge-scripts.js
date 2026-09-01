/*
 * Generic MIDI SysEx mapping for mixxx-api-bridge.
 *
 * Frames are:
 *   F0 7D 'M' 'X' 'A' 01 OP <ASCII JSON> F7
 *
 * JSON is used so arbitrary Mixxx group/key pairs can be addressed without
 * regenerating this mapping. JSON.stringify emits escaped ASCII for ordinary
 * control names, and all bytes are valid MIDI SysEx data bytes.
 */
// eslint-disable-next-line no-var
var MixxxApiBridge = {};

MixxxApiBridge.VERSION = 1;
// Prefix includes F0, manufacturer ID, magic, and protocol version. The
// operation byte follows at index 6; JSON begins at index 7.
MixxxApiBridge.HEADER_LENGTH = 6;
MixxxApiBridge.OP_HELLO = 0x00;
MixxxApiBridge.OP_COMMAND = 0x01;
MixxxApiBridge.OP_FEEDBACK = 0x02;
MixxxApiBridge.OP_CAPABILITIES = 0x03;
MixxxApiBridge.OP_SUBSCRIBE = 0x04;
MixxxApiBridge.OP_GET = 0x05;
MixxxApiBridge.OP_ACTION = 0x06;
MixxxApiBridge.OP_SETTING_GET = 0x07;
MixxxApiBridge.OP_READY = 0x10;
MixxxApiBridge.OP_ACK = 0x11;
MixxxApiBridge.OP_SETTING_VALUE = 0x12;
MixxxApiBridge.OP_ERROR = 0x7F;

MixxxApiBridge._connections = {};

MixxxApiBridge._isFrame = function (data) {
    return data && data.length >= MixxxApiBridge.HEADER_LENGTH + 2 &&
        data[0] === 0xF0 && data[data.length - 1] === 0xF7 &&
        data[1] === 0x7D && data[2] === 0x4D && data[3] === 0x58 &&
        data[4] === 0x41 && data[5] === MixxxApiBridge.VERSION;
};

MixxxApiBridge._payload = function (data) {
    var text = "";
    for (var index = MixxxApiBridge.HEADER_LENGTH + 1; index < data.length - 1; index++) {
        text += String.fromCharCode(data[index]);
    }
    return text ? JSON.parse(text) : {};
};

MixxxApiBridge._frame = function (operation, payload) {
    // Keep frames deterministic across Python and JavaScript implementations.
    var keys = Object.keys(payload || {}).sort();
    var text = JSON.stringify(payload || {}, keys);
    var frame = [0xF0, 0x7D, 0x4D, 0x58, 0x41, MixxxApiBridge.VERSION, operation];
    for (var index = 0; index < text.length; index++) {
        var byte = text.charCodeAt(index);
        // JSON.stringify emits ASCII for the control metadata we use. Refuse
        // malformed data rather than sending an invalid MIDI SysEx byte.
        if (byte >= 0x80) {
            throw new Error("non-ASCII SysEx payload");
        }
        frame.push(byte);
    }
    frame.push(0xF7);
    return frame;
};

MixxxApiBridge._send = function (operation, payload) {
    var frame = MixxxApiBridge._frame(operation, payload);
    midi.sendSysexMsg(frame, frame.length);
};

MixxxApiBridge._sendFeedback = function (payload) {
    MixxxApiBridge._send(MixxxApiBridge.OP_FEEDBACK, payload);
};

MixxxApiBridge._read = function (group, key, scale) {
    if (scale === "raw") {
        return engine.getValue(group, key);
    }
    return engine.getParameter(group, key);
};

MixxxApiBridge._write = function (group, key, value, scale) {
    if (scale === "raw") {
        engine.setValue(group, key, Number(value));
    } else {
        engine.setParameter(group, key, Number(value));
    }
};

MixxxApiBridge._ack = function (payload, value) {
    var response = {
        request_id: payload.request_id || "",
        group: payload.group || "",
        key: payload.key || "",
        value: value,
        scale: payload.scale || "normalized"
    };
    if (payload.action) {
        response.action = payload.action;
    }
    MixxxApiBridge._send(MixxxApiBridge.OP_ACK, response);
};

MixxxApiBridge._error = function (payload, message) {
    MixxxApiBridge._send(MixxxApiBridge.OP_ERROR, {
        request_id: payload && payload.request_id ? payload.request_id : "",
        error: String(message)
    });
};

MixxxApiBridge._handleHello = function (payload) {
    MixxxApiBridge._send(MixxxApiBridge.OP_READY, {
        request_id: payload.request_id || "",
        mapping: "MixxxApiBridge",
        mapping_version: "0.1.0",
        protocol: MixxxApiBridge.VERSION,
        mixxx_control_api: "engine.setParameter/engine.setValue/engine.trigger/script.toggleControl/engine.reset"
    });
};

MixxxApiBridge._handleCommand = function (payload) {
    if (typeof payload.group !== "string" || typeof payload.key !== "string") {
        MixxxApiBridge._error(payload, "group and key are required");
        return;
    }
    try {
        MixxxApiBridge._write(
            payload.group,
            payload.key,
            payload.value,
            payload.scale || "normalized"
        );
        var value = MixxxApiBridge._read(
            payload.group,
            payload.key,
            payload.scale || "normalized"
        );
        MixxxApiBridge._ack(payload, value);
        MixxxApiBridge._sendFeedback({
            request_id: payload.request_id || "",
            group: payload.group,
            key: payload.key,
            value: value,
            scale: payload.scale || "normalized"
        });
    } catch (error) {
        MixxxApiBridge._error(payload, error);
    }
};

MixxxApiBridge._handleGet = function (payload) {
    try {
        var value = MixxxApiBridge._read(payload.group, payload.key, payload.scale || "normalized");
        MixxxApiBridge._sendFeedback({
            request_id: payload.request_id || "",
            group: payload.group,
            key: payload.key,
            value: value,
            scale: payload.scale || "normalized"
        });
    } catch (error) {
        MixxxApiBridge._error(payload, error);
    }
};

MixxxApiBridge._handleSubscribe = function (payload) {
    var address = payload.group + "/" + payload.key;
    try {
        if (MixxxApiBridge._connections[address]) {
            MixxxApiBridge._connections[address].disconnect();
        }
        var scale = payload.scale || "normalized";
        MixxxApiBridge._connections[address] = engine.makeConnection(
            payload.group,
            payload.key,
            function (value, group, key) {
                MixxxApiBridge._sendFeedback({
                    request_id: payload.request_id || "",
                    group: group,
                    key: key,
                    value: scale === "raw" ? value : engine.getParameter(group, key),
                    scale: scale
                });
            }
        );
        MixxxApiBridge._connections[address].trigger();
        MixxxApiBridge._ack(payload, 1);
    } catch (error) {
        MixxxApiBridge._error(payload, error);
    }
};

MixxxApiBridge._handleAction = function (payload) {
    if (typeof payload.group !== "string" || typeof payload.key !== "string") {
        MixxxApiBridge._error(payload, "group and key are required");
        return;
    }
    if (["trigger", "toggle", "reset"].indexOf(payload.action) < 0) {
        MixxxApiBridge._error(payload, "action must be trigger, toggle, or reset");
        return;
    }
    try {
        if (payload.action === "trigger") {
            // triggerControl is the correct API for momentary controls such
            // as beatjump, eject, hotcue_activate, and pitch_up_small.
            if (typeof script !== "undefined" && script.triggerControl) {
                script.triggerControl(payload.group, payload.key);
            } else {
                engine.trigger(payload.group, payload.key);
            }
        } else if (payload.action === "toggle") {
            if (typeof script !== "undefined" && script.toggleControl) {
                script.toggleControl(payload.group, payload.key);
            } else {
                MixxxApiBridge._write(
                    payload.group,
                    payload.key,
                    MixxxApiBridge._read(payload.group, payload.key, payload.scale || "normalized") ? 0 : 1,
                    payload.scale || "normalized"
                );
            }
        } else {
            engine.reset(payload.group, payload.key);
        }
        var scale = payload.scale || "normalized";
        var value = MixxxApiBridge._read(payload.group, payload.key, scale);
        MixxxApiBridge._ack(payload, value);
        MixxxApiBridge._sendFeedback({
            request_id: payload.request_id || "",
            action: payload.action,
            group: payload.group,
            key: payload.key,
            value: value,
            scale: scale
        });
    } catch (error) {
        MixxxApiBridge._error(payload, error);
    }
};

MixxxApiBridge._handleSettingGet = function (payload) {
    if (typeof payload.name !== "string" || !payload.name) {
        MixxxApiBridge._error(payload, "setting name is required");
        return;
    }
    try {
        if (typeof engine.getSetting !== "function") {
            throw new Error("engine.getSetting is unavailable");
        }
        var value = engine.getSetting(payload.name);
        MixxxApiBridge._send(MixxxApiBridge.OP_SETTING_VALUE, {
            request_id: payload.request_id || "",
            name: payload.name,
            value: value === undefined ? null : value,
            found: value !== undefined
        });
    } catch (error) {
        MixxxApiBridge._error(payload, error);
    }
};

MixxxApiBridge._handleCapabilities = function (payload) {
    MixxxApiBridge._send(MixxxApiBridge.OP_CAPABILITIES, {
        request_id: payload.request_id || "",
        mapping: "MixxxApiBridge",
        mapping_version: "0.1.0",
        protocol: MixxxApiBridge.VERSION,
        supports: [
            "hello", "set", "get", "subscribe", "feedback", "capabilities",
            "trigger", "toggle", "reset", "setting_get"
        ]
    });
};

// Mixxx's MIDI script binding calls the conventional incomingData method.
// Keep handleSysEx as an alias for direct callers and older bridge tests.
MixxxApiBridge.incomingData = function (data, _length) {
    if (!MixxxApiBridge._isFrame(data)) {
        return;
    }
    try {
        var operation = data[6];
        var payload = MixxxApiBridge._payload(data);
        if (operation === MixxxApiBridge.OP_HELLO) {
            MixxxApiBridge._handleHello(payload);
        } else if (operation === MixxxApiBridge.OP_COMMAND) {
            MixxxApiBridge._handleCommand(payload);
        } else if (operation === MixxxApiBridge.OP_GET) {
            MixxxApiBridge._handleGet(payload);
        } else if (operation === MixxxApiBridge.OP_SUBSCRIBE) {
            MixxxApiBridge._handleSubscribe(payload);
        } else if (operation === MixxxApiBridge.OP_ACTION) {
            MixxxApiBridge._handleAction(payload);
        } else if (operation === MixxxApiBridge.OP_SETTING_GET) {
            MixxxApiBridge._handleSettingGet(payload);
        } else if (operation === MixxxApiBridge.OP_CAPABILITIES) {
            MixxxApiBridge._handleCapabilities(payload);
        } else {
            MixxxApiBridge._error(payload, "unsupported operation " + operation);
        }
    } catch (error) {
        MixxxApiBridge._error({}, error);
    }
};

MixxxApiBridge.handleSysEx = MixxxApiBridge.incomingData;

MixxxApiBridge.init = function (_id, _debugging) {
    MixxxApiBridge._send(MixxxApiBridge.OP_READY, {
        mapping: "MixxxApiBridge",
        mapping_version: "0.1.0",
        protocol: MixxxApiBridge.VERSION,
        mixxx_control_api: "engine.setParameter/engine.setValue/engine.trigger/script.toggleControl/engine.reset"
    });
};

MixxxApiBridge.shutdown = function () {
    Object.keys(MixxxApiBridge._connections).forEach(function (address) {
        MixxxApiBridge._connections[address].disconnect();
    });
    MixxxApiBridge._connections = {};
};
