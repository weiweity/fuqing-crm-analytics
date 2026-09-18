export function utf8Bytes(text) {
  return new TextEncoder().encode(String(text ?? ''));
}

export function bytesFromBase64(value) {
  if (typeof value !== 'string') return null;
  if (value.length === 0) return new Uint8Array();
  try {
    const binary = atob(value);
    const out = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i);
    return out;
  } catch {
    return null;
  }
}

export function bytesToBase64(bytes) {
  const data = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < data.length; i += chunk) {
    binary += String.fromCharCode(...data.subarray(i, i + chunk));
  }
  return btoa(binary);
}

export async function sha256Hex(bytes) {
  const data = bytes instanceof Uint8Array ? bytes : utf8Bytes(bytes);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return [...new Uint8Array(digest)].map((n) => n.toString(16).padStart(2, '0')).join('');
}

export function byteLength(value) {
  if (typeof value === 'string') return utf8Bytes(value).byteLength;
  if (value instanceof Uint8Array) return value.byteLength;
  return 0;
}
