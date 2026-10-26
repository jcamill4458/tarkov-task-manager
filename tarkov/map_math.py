import math

# Math done by an AI, looked over by author
# World -> map conversions. "x" and "z" are the map plane in the API's positions;
# "y" is height and is ignored here.

DEFAULT_TILE_SIZE = 256
LABEL_FONT = 2.9
SUPPORTED_ROTATIONS = (0, 90, 180, 270)


def canProject(config):
    return config.hasSvg and config.rotation in SUPPORTED_ROTATIONS


def requireSupported(config):
    if config.rotation not in SUPPORTED_ROTATIONS:
        raise ValueError(f"map rotation {config.rotation} is not supported")


def screenVector(x, z, rotation):
    if rotation == 0:
        return (x, -z)
    if rotation == 90:
        return (-z, -x)
    if rotation == 180:
        return (-x, z)
    if rotation == 270:
        return (z, x)
    raise ValueError(f"map rotation {rotation} is not supported")


def boundsEdges(config):
    sideways0, down0 = screenVector(*config.bounds[0], config.rotation)
    sideways1, down1 = screenVector(*config.bounds[1], config.rotation)
    return (min(sideways0, sideways1), max(sideways0, sideways1),
            min(down0, down1), max(down0, down1))


def worldToSvg(x, z, config, width, height):
    requireSupported(config)
    left, right, top, bottom = boundsEdges(config)
    sideways, down = screenVector(x, z, config.rotation)
    return ((sideways - left) / (right - left) * width,
            (down - top) / (bottom - top) * height)


def worldToTile(x, z, config, zoom):
    requireSupported(config)
    a, b, c, d = config.transform
    sideways, down = screenVector(x, z, config.rotation)
    scale = 2 ** zoom
    return ((a * sideways + b) * scale,
            (c * down + d) * scale)


def clampZoom(config, zoom):
    return max(config.minZoom, min(config.maxZoom, zoom))


def tileSpan(config, zoom):
    u0, v0 = worldToTile(*config.bounds[0], config, zoom)
    u1, v1 = worldToTile(*config.bounds[1], config, zoom)
    return min(u0, u1), max(u0, u1), min(v0, v1), max(v0, v1)


def tileRange(config, zoom):
    left, right, top, bottom = tileSpan(config, zoom)
    last = 2 ** zoom - 1
    size = config.tileSize
    return (max(0, math.floor(left / size)),
            min(last, math.floor(right / size)),
            max(0, math.floor(top / size)),
            min(last, math.floor(bottom / size)))


def satelliteTransform(config, zoom, firstTileX, firstTileY, width, height):
    left, right, top, bottom = tileSpan(config, zoom)
    scaleX = width / (right - left)
    scaleY = height / (bottom - top)
    offsetX = (firstTileX * config.tileSize - left) * scaleX
    offsetY = (firstTileY * config.tileSize - top) * scaleY
    return scaleX, scaleY, offsetX, offsetY


def labelFontSize(config, label, svgWidth):
    left, right, _, _ = boundsEdges(config)
    svgPerWorldUnit = svgWidth / (right - left)
    return LABEL_FONT * label.size / 100 * svgPerWorldUnit / abs(config.transform[0])


def svgToWorld(sx, sy, config, width, height):
    requireSupported(config)
    left, right, top, bottom = boundsEdges(config)
    sideways = left + sx / width * (right - left)
    down = top + sy / height * (bottom - top)
    if config.rotation == 0:
        return sideways, -down
    if config.rotation == 90:
        return -down, -sideways
    if config.rotation == 180:
        return -sideways, down
    return down, sideways      # 270


def limitZoomOut(currentScale, factor, minScale):
    if factor >= 1:
        return factor
    target = min(max(currentScale * factor, minScale), currentScale)
    return target / currentScale
