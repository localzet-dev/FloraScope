import test from "node:test";
import assert from "node:assert/strict";
import { readStored, writeStored } from "../src/lib/storage.ts";
test("selection survives reload; corrupt or unavailable storage falls back", () => {
  const data = new Map();
  globalThis.localStorage = {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, value),
  };
  writeStored("field", "field-example");
  assert.equal(readStored("field", ""), "field-example");
  data.set("florascope:field", "broken JSON");
  assert.equal(readStored("field", ""), "");
  data.set("florascope:field", "123");
  assert.equal(readStored("field", ""), "");
  globalThis.localStorage = {
    getItem: () => {
      throw Error("denied");
    },
    setItem: () => {
      throw Error("denied");
    },
  };
  assert.equal(readStored("field", "fallback"), "fallback");
  assert.doesNotThrow(() => writeStored("field", "x"));
  delete globalThis.localStorage;
});
