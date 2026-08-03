import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const outputDirectory = path.resolve(scriptDirectory, "../public/icons");

const crcTable = Array.from({ length: 256 }, (_, index) => {
  let value = index;
  for (let bit = 0; bit < 8; bit += 1) {
    value = (value & 1) !== 0 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  }
  return value >>> 0;
});

const crc32 = (buffer) => {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
};

const makeChunk = (type, data = Buffer.alloc(0)) => {
  const typeBuffer = Buffer.from(type, "ascii");
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length, 0);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])), 0);
  return Buffer.concat([length, typeBuffer, data, checksum]);
};

const distanceToSegment = (x, y, x1, y1, x2, y2) => {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const lengthSquared = dx * dx + dy * dy;
  const projection =
    lengthSquared === 0
      ? 0
      : Math.max(
          0,
          Math.min(1, ((x - x1) * dx + (y - y1) * dy) / lengthSquared),
        );
  const closestX = x1 + projection * dx;
  const closestY = y1 + projection * dy;
  return Math.hypot(x - closestX, y - closestY);
};

const insideRoundedRectangle = (x, y, size, inset, radius) => {
  const left = inset;
  const right = size - inset - 1;
  const top = inset;
  const bottom = size - inset - 1;

  if (
    x >= left + radius &&
    x <= right - radius &&
    y >= top &&
    y <= bottom
  ) {
    return true;
  }
  if (
    y >= top + radius &&
    y <= bottom - radius &&
    x >= left &&
    x <= right
  ) {
    return true;
  }

  const cornerX = x < left + radius ? left + radius : right - radius;
  const cornerY = y < top + radius ? top + radius : bottom - radius;
  return Math.hypot(x - cornerX, y - cornerY) <= radius;
};

const renderIcon = (size, { maskable = false } = {}) => {
  const pixels = Buffer.alloc(size * size * 3);
  const inset = Math.max(1, Math.round(size * 0.025));
  const radius = Math.round(size * 0.21);
  const borderWidth = Math.max(1, Math.round(size * 0.009));
  const strokeWidth = size * (maskable ? 0.064 : 0.072);
  const points = maskable
    ? [
        [0.29, 0.3],
        [0.39, 0.7],
        [0.5, 0.45],
        [0.61, 0.7],
        [0.71, 0.3],
      ]
    : [
        [0.24, 0.27],
        [0.37, 0.73],
        [0.5, 0.43],
        [0.63, 0.73],
        [0.76, 0.27],
      ];

  for (let y = 0; y < size; y += 1) {
    const gradient = y / Math.max(size - 1, 1);
    for (let x = 0; x < size; x += 1) {
      const offset = (y * size + x) * 3;
      const insideOuter = insideRoundedRectangle(x, y, size, inset, radius);
      const insideInner = insideRoundedRectangle(
        x,
        y,
        size,
        inset + borderWidth,
        Math.max(0, radius - borderWidth),
      );

      let red = Math.round(22 - gradient * 12);
      let green = Math.round(34 - gradient * 17);
      let blue = Math.round(62 - gradient * 28);

      if (!insideOuter) {
        red = 12;
        green = 20;
        blue = 40;
      } else if (!insideInner) {
        red = 58;
        green = 75;
        blue = 112;
      }

      const normalizedX = x / size;
      const normalizedY = y / size;
      const onLetter = points.slice(0, -1).some((point, index) => {
        const nextPoint = points[index + 1];
        return (
          distanceToSegment(
            normalizedX,
            normalizedY,
            point[0],
            point[1],
            nextPoint[0],
            nextPoint[1],
          ) <=
          strokeWidth / (2 * size)
        );
      });

      if (onLetter) {
        red = 255;
        green = 255;
        blue = 255;
      }

      pixels[offset] = red;
      pixels[offset + 1] = green;
      pixels[offset + 2] = blue;
    }
  }

  const scanlines = Buffer.alloc(size * (size * 3 + 1));
  for (let y = 0; y < size; y += 1) {
    const scanlineOffset = y * (size * 3 + 1);
    scanlines[scanlineOffset] = 0;
    pixels.copy(
      scanlines,
      scanlineOffset + 1,
      y * size * 3,
      (y + 1) * size * 3,
    );
  }

  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0);
  header.writeUInt32BE(size, 4);
  header[8] = 8;
  header[9] = 2;
  header[10] = 0;
  header[11] = 0;
  header[12] = 0;

  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    makeChunk("IHDR", header),
    makeChunk("IDAT", deflateSync(scanlines, { level: 9 })),
    makeChunk("IEND"),
  ]);
};

await mkdir(outputDirectory, { recursive: true });

const icons = [
  ["weave-180.png", 180, false],
  ["weave-192.png", 192, false],
  ["weave-512.png", 512, false],
  ["weave-maskable-512.png", 512, true],
];

await Promise.all(
  icons.map(([fileName, size, maskable]) =>
    writeFile(path.join(outputDirectory, fileName), renderIcon(size, { maskable })),
  ),
);

console.log(`Generated ${icons.length} valid Weave PWA icons.`);
