const MESSAGE_SOUND_STORAGE_KEY = "weave:message-sound-enabled";

let audioContext = null;

export function getMessageSoundEnabled(storage = globalThis.localStorage) {
  try {
    const stored = storage?.getItem?.(MESSAGE_SOUND_STORAGE_KEY);
    return stored === null || stored === undefined ? true : stored !== "false";
  } catch {
    return true;
  }
}

export function setMessageSoundEnabled(enabled, storage = globalThis.localStorage) {
  try {
    storage?.setItem?.(MESSAGE_SOUND_STORAGE_KEY, String(Boolean(enabled)));
  } catch {
    // Storage is optional. Sound still works for the current session.
  }
  return Boolean(enabled);
}

export async function primeMessageSound({
  AudioContextImpl = globalThis.AudioContext || globalThis.webkitAudioContext,
} = {}) {
  if (!AudioContextImpl) return false;
  try {
    audioContext ||= new AudioContextImpl();
    if (audioContext.state === "suspended") await audioContext.resume();
    return audioContext.state === "running";
  } catch {
    return false;
  }
}

export async function playIncomingMessageSound({
  enabled = getMessageSoundEnabled(),
  AudioContextImpl = globalThis.AudioContext || globalThis.webkitAudioContext,
} = {}) {
  if (!enabled || !AudioContextImpl) return false;
  try {
    const ready = await primeMessageSound({ AudioContextImpl });
    if (!ready || !audioContext) return false;

    const now = audioContext.currentTime;
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();

    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(620, now);
    oscillator.frequency.exponentialRampToValueAtTime(520, now + 0.085);

    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.028, now + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.105);

    oscillator.connect(gain);
    gain.connect(audioContext.destination);
    oscillator.start(now);
    oscillator.stop(now + 0.11);
    return true;
  } catch {
    return false;
  }
}

export { MESSAGE_SOUND_STORAGE_KEY };
