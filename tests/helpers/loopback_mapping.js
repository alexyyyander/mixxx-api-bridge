// Test-only engine stub. Echo every reply back into the shipped mapping.
const fs = require("fs");
const vm = require("vm");
const readline = require("readline");
const values = {};
const connections = {};
let output = [];
let pending = [];
const key = (group, name) => group + "/" + name;
const get = (group, name) => values[key(group, name)] ?? 0;
const set = (group, name, value) => {
  values[key(group, name)] = value;
  (connections[key(group, name)] || []).forEach(callback => callback(value, group, name));
};
const context = {
  midi: { sendSysexMsg: frame => { output.push(frame); pending.push(frame); } },
  engine: {
    getValue: get, getParameter: get, setValue: set, setParameter: set,
    getSetting: name => name === "triggerDelayMs" ? 200 : undefined,
    reset: (group, name) => set(group, name, 0),
    makeConnection: (group, name, callback) => {
      (connections[key(group, name)] ||= []).push(callback);
      return { trigger: () => callback(get(group, name), group, name), disconnect: () => {} };
    }
  },
  script: {
    toggleControl: (group, name) => set(group, name, get(group, name) ? 0 : 1),
    triggerControl: (group, name) => set(group, name, 1)
  }
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
readline.createInterface({ input: process.stdin }).on("line", line => {
  output = [];
  pending = [JSON.parse(line)];
  let processed = 0;
  while (pending.length && processed < 64) {
    const frame = pending.shift();
    context.MixxxApiBridge.incomingData(frame, frame.length);
    processed++;
  }
  process.stdout.write(JSON.stringify({output, processed, overflow: pending.length > 0}) + "\n");
});
