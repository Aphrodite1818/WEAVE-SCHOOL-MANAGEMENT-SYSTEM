import assert from "node:assert/strict";
import test from "node:test";

import {
  MESSAGE_SOUND_STORAGE_KEY,
  getMessageSoundEnabled,
  setMessageSoundEnabled,
} from "../../src/utils/messageSound.js";

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) {
      return values.has(key) ? values.get(key) : null;
    },
    setItem(key, value) {
      values.set(key, String(value));
    },
  };
}

test("incoming message sound defaults to enabled", () => {
  assert.equal(getMessageSoundEnabled(memoryStorage()), true);
});

test("incoming message sound preference persists explicitly", () => {
  const storage = memoryStorage();
  assert.equal(setMessageSoundEnabled(false, storage), false);
  assert.equal(storage.getItem(MESSAGE_SOUND_STORAGE_KEY), "false");
  assert.equal(getMessageSoundEnabled(storage), false);

  assert.equal(setMessageSoundEnabled(true, storage), true);
  assert.equal(storage.getItem(MESSAGE_SOUND_STORAGE_KEY), "true");
  assert.equal(getMessageSoundEnabled(storage), true);
});
