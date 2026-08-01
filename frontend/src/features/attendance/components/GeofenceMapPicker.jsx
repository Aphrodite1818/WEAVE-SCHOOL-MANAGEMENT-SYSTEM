import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Crosshair, Layers, LocateFixed, Minus, Plus, Search } from "lucide-react";

import Button from "../../../components/ui/Button";

const TILE_SIZE = 256;
const DEFAULT_CENTER = { latitude: 6.524379, longitude: 3.379206 };
const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
const TILE_LAYERS = {
  streets: {
    label: "Map",
    attribution: "OpenStreetMap",
    url: ({ zoom, x, y }) => `https://tile.openstreetmap.org/${zoom}/${x}/${y}.png`,
  },
  satellite: {
    label: "Satellite",
    attribution: "Esri World Imagery",
    url: ({ zoom, x, y }) =>
      `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${zoom}/${y}/${x}`,
  },
};

const longitudeToTileX = (longitude, zoom) =>
  ((longitude + 180) / 360) * 2 ** zoom;

const latitudeToTileY = (latitude, zoom) => {
  const rad = (latitude * Math.PI) / 180;
  return (
    ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) *
    2 ** zoom
  );
};

const tileXToLongitude = (x, zoom) => (x / 2 ** zoom) * 360 - 180;

const tileYToLatitude = (y, zoom) => {
  const n = Math.PI - (2 * Math.PI * y) / 2 ** zoom;
  return (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
};

const normalizeCoordinate = (value, fallback) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

function GeofenceMapPicker({
  latitude,
  longitude,
  radiusM,
  onChange,
}) {
  const containerRef = useRef(null);
  const dragRef = useRef(null);
  const [zoom, setZoom] = useState(16);
  const [layer, setLayer] = useState("streets");
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [mapMessage, setMapMessage] = useState("");
  const [size, setSize] = useState({ width: 640, height: 360 });
  const [center, setCenter] = useState({
    latitude: normalizeCoordinate(latitude, DEFAULT_CENTER.latitude),
    longitude: normalizeCoordinate(longitude, DEFAULT_CENTER.longitude),
  });
  const selected = useMemo(
    () => ({
      latitude: normalizeCoordinate(latitude, center.latitude),
      longitude: normalizeCoordinate(longitude, center.longitude),
    }),
    [center.latitude, center.longitude, latitude, longitude],
  );

  useEffect(() => {
    const nextLatitude = normalizeCoordinate(latitude, DEFAULT_CENTER.latitude);
    const nextLongitude = normalizeCoordinate(longitude, DEFAULT_CENTER.longitude);
    setCenter((current) => {
      if (
        Math.abs(current.latitude - nextLatitude) < 0.000001 &&
        Math.abs(current.longitude - nextLongitude) < 0.000001
      ) {
        return current;
      }
      return { latitude: nextLatitude, longitude: nextLongitude };
    });
  }, [latitude, longitude]);

  useEffect(() => {
    const node = containerRef.current;
    if (!node || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect;
      if (rect) {
        setSize({
          width: Math.max(320, Math.round(rect.width)),
          height: Math.max(300, Math.round(rect.height)),
        });
      }
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const centerTile = useMemo(
    () => ({
      x: longitudeToTileX(center.longitude, zoom),
      y: latitudeToTileY(center.latitude, zoom),
    }),
    [center.latitude, center.longitude, zoom],
  );

  const project = useCallback(
    (point) => {
      const pointTile = {
        x: longitudeToTileX(point.longitude, zoom),
        y: latitudeToTileY(point.latitude, zoom),
      };
      return {
        x: size.width / 2 + (pointTile.x - centerTile.x) * TILE_SIZE,
        y: size.height / 2 + (pointTile.y - centerTile.y) * TILE_SIZE,
      };
    },
    [centerTile.x, centerTile.y, size.height, size.width, zoom],
  );

  const unproject = useCallback(
    (x, y) => {
      const tileX = centerTile.x + (x - size.width / 2) / TILE_SIZE;
      const tileY = centerTile.y + (y - size.height / 2) / TILE_SIZE;
      return {
        latitude: clamp(tileYToLatitude(tileY, zoom), -85.05112878, 85.05112878),
        longitude: clamp(tileXToLongitude(tileX, zoom), -180, 180),
      };
    },
    [centerTile.x, centerTile.y, size.height, size.width, zoom],
  );

  const tiles = useMemo(() => {
    const minTileX = Math.floor(centerTile.x - size.width / (2 * TILE_SIZE)) - 1;
    const maxTileX = Math.floor(centerTile.x + size.width / (2 * TILE_SIZE)) + 1;
    const minTileY = Math.floor(centerTile.y - size.height / (2 * TILE_SIZE)) - 1;
    const maxTileY = Math.floor(centerTile.y + size.height / (2 * TILE_SIZE)) + 1;
    const maxIndex = 2 ** zoom;
    const nextTiles = [];
    for (let x = minTileX; x <= maxTileX; x += 1) {
      for (let y = minTileY; y <= maxTileY; y += 1) {
        if (y < 0 || y >= maxIndex) continue;
        const wrappedX = ((x % maxIndex) + maxIndex) % maxIndex;
        nextTiles.push({
          key: `${zoom}-${x}-${y}`,
          x,
          y,
          wrappedX,
          left: size.width / 2 + (x - centerTile.x) * TILE_SIZE,
          top: size.height / 2 + (y - centerTile.y) * TILE_SIZE,
        });
      }
    }
    return nextTiles;
  }, [centerTile.x, centerTile.y, size.height, size.width, zoom]);

  const selectedPosition = project(selected);
  const activeLayer = TILE_LAYERS[layer] || TILE_LAYERS.streets;
  const radiusPixels = useMemo(() => {
    const metresPerPixel =
      (156543.03392 * Math.cos((selected.latitude * Math.PI) / 180)) / 2 ** zoom;
    return clamp((Number(radiusM) || 0) / metresPerPixel, 8, 180);
  }, [radiusM, selected.latitude, zoom]);

  const updateSelected = (point) => {
    const next = {
      latitude: Number(point.latitude.toFixed(6)),
      longitude: Number(point.longitude.toFixed(6)),
    };
    onChange?.(next);
  };

  const searchLocation = async (event) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    setSearching(true);
    setMapMessage("");
    try {
      const params = new URLSearchParams({
        format: "json",
        limit: "1",
        q: trimmed,
      });
      const response = await fetch(`https://nominatim.openstreetmap.org/search?${params}`);
      const results = await response.json();
      const first = Array.isArray(results) ? results[0] : null;
      if (!first) {
        setMapMessage("No matching location found.");
        return;
      }
      const next = {
        latitude: Number(Number(first.lat).toFixed(6)),
        longitude: Number(Number(first.lon).toFixed(6)),
      };
      setCenter(next);
      onChange?.(next);
    } catch {
      setMapMessage("Location search is unavailable.");
    } finally {
      setSearching(false);
    }
  };

  const handlePointerDown = (event) => {
    const rect = event.currentTarget.getBoundingClientRect();
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      startCenter: center,
      moved: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = unproject(event.clientX - rect.left, event.clientY - rect.top);
    updateSelected(point);
  };

  const handlePointerMove = (event) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const deltaX = event.clientX - drag.startX;
    const deltaY = event.clientY - drag.startY;
    if (Math.abs(deltaX) + Math.abs(deltaY) < 4) return;
    drag.moved = true;
    const startTile = {
      x: longitudeToTileX(drag.startCenter.longitude, zoom),
      y: latitudeToTileY(drag.startCenter.latitude, zoom),
    };
    setCenter({
      latitude: clamp(tileYToLatitude(startTile.y - deltaY / TILE_SIZE, zoom), -85.05112878, 85.05112878),
      longitude: clamp(tileXToLongitude(startTile.x - deltaX / TILE_SIZE, zoom), -180, 180),
    });
  };

  const handlePointerUp = (event) => {
    if (dragRef.current?.pointerId === event.pointerId) {
      dragRef.current = null;
    }
  };

  const useCurrentLocation = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((position) => {
      const next = {
        latitude: Number(position.coords.latitude.toFixed(6)),
        longitude: Number(position.coords.longitude.toFixed(6)),
      };
      setCenter(next);
      onChange?.(next);
    });
  };

  return (
    <div className="space-y-3">
      <div
        ref={containerRef}
        className="relative h-[420px] overflow-hidden rounded-lg border border-border/80 bg-surface-muted shadow-sm"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        role="application"
        aria-label="Geofence coordinate picker"
      >
        {tiles.map((tile) => (
          <img
            key={tile.key}
            alt=""
            draggable="false"
            src={activeLayer.url({ zoom, x: tile.wrappedX, y: tile.y })}
            className="absolute h-64 w-64 select-none"
            style={{ left: tile.left, top: tile.top }}
          />
        ))}
        <form
          className="absolute left-3 right-3 top-3 z-10 flex max-w-xl gap-2 rounded-lg border border-border/80 bg-surface/95 p-2 shadow-lg backdrop-blur"
          onSubmit={searchLocation}
          onPointerDown={(event) => event.stopPropagation()}
        >
          <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-border/70 bg-surface px-3">
            <Search size={16} className="shrink-0 text-text-muted" />
            <input
              className="h-10 min-w-0 flex-1 bg-transparent text-sm font-medium text-text outline-none"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search school address or landmark"
            />
          </div>
          <Button size="sm" type="submit" disabled={searching}>
            {searching ? "Searching" : "Search"}
          </Button>
        </form>
        <div
          className="pointer-events-none absolute rounded-full border-2 border-primary/70 bg-primary/10"
          style={{
            width: radiusPixels * 2,
            height: radiusPixels * 2,
            left: selectedPosition.x - radiusPixels,
            top: selectedPosition.y - radiusPixels,
          }}
        />
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.16)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.16)_1px,transparent_1px)] bg-[size:80px_80px] opacity-30" />
        <div
          className="pointer-events-none absolute flex h-11 w-11 -translate-x-1/2 -translate-y-full items-center justify-center rounded-full border border-primary/30 bg-primary text-text-inverse shadow-xl ring-4 ring-primary/20"
          style={{ left: selectedPosition.x, top: selectedPosition.y }}
        >
          <MapMarkerIcon />
        </div>
        <div
          className="absolute bottom-16 right-3 z-10 flex flex-col overflow-hidden rounded-lg border border-border/80 bg-surface/95 shadow-lg backdrop-blur"
          onPointerDown={(event) => event.stopPropagation()}
        >
          <Button size="icon" variant="outline" onClick={() => setZoom((value) => clamp(value + 1, 3, 19))}>
            <Plus size={18} />
          </Button>
          <Button size="icon" variant="outline" onClick={() => setZoom((value) => clamp(value - 1, 3, 19))}>
            <Minus size={18} />
          </Button>
        </div>
        <div
          className="absolute right-3 top-3 z-10 flex flex-col gap-2"
          onPointerDown={(event) => event.stopPropagation()}
        >
          <Button size="sm" variant="outline" onClick={() => setLayer((value) => (value === "streets" ? "satellite" : "streets"))}>
            <Layers size={16} />
            {activeLayer.label}
          </Button>
          <Button size="sm" variant="outline" onClick={() => setCenter(selected)}>
            <Crosshair size={18} />
            Center
          </Button>
          <Button size="sm" variant="outline" onClick={useCurrentLocation}>
            <LocateFixed size={18} />
            My location
          </Button>
        </div>
        <div className="absolute bottom-3 left-3 z-10 rounded-lg border border-border/80 bg-surface/95 px-3 py-2 text-xs font-medium text-text shadow-lg backdrop-blur">
          <div>Selected: {Number(selected.latitude).toFixed(6)}, {Number(selected.longitude).toFixed(6)}</div>
          <div className="text-text-muted">Radius preview: {Number(radiusM) || 0} m</div>
        </div>
        <div className="absolute bottom-3 right-3 z-10 rounded-md bg-surface/90 px-2 py-1 text-[11px] font-medium text-text-muted shadow">
          Tiles: {activeLayer.attribution}
        </div>
      </div>
      {mapMessage ? (
        <p className="text-xs font-medium text-error">{mapMessage}</p>
      ) : null}
      <div className="grid gap-2 text-xs text-text-muted sm:grid-cols-3">
        <span>Latitude: {Number(selected.latitude).toFixed(6)}</span>
        <span>Longitude: {Number(selected.longitude).toFixed(6)}</span>
        <span>Zoom: {zoom}</span>
      </div>
    </div>
  );
}

function MapMarkerIcon() {
  return <span className="h-3 w-3 rounded-full bg-current" aria-hidden="true" />;
}

export default GeofenceMapPicker;
