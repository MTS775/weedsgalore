# SPDX-FileCopyrightText: 2025 Helmholtz Centre Potsdam - GFZ German Research Centre for Geosciences
# SPDX-License-Identifier: Apache-2.0

import io
import os
import re
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image


DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BAND_PATTERN = re.compile(r"_(R|G|B|NIR|RE)$", re.IGNORECASE)


def index_parcel_files(entries):
    """Index named image files by date, tile, and spectral band."""
    parcels = {}
    ignored = []

    for name, reference in entries:
        normalized = name.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        filename = parts[-1]
        stem, extension = os.path.splitext(filename)
        if extension.lower() != ".png":
            continue

        folder = None
        for part in reversed(parts[:-1]):
            if part.lower() in ("instances", "logs"):
                folder = "ignored"
                break
            if part.lower() in ("images", "semantics"):
                folder = part.lower()
                break
        if folder == "ignored":
            continue
        if folder is None:
            folder = "images"

        date = next((part for part in parts if DATE_PATTERN.match(part)), None)
        if folder == "semantics":
            tile_name = stem
            field = "label"
        else:
            band_match = BAND_PATTERN.search(stem)
            if band_match is None:
                ignored.append(name)
                continue
            tile_name = stem[:band_match.start()]
            field = band_match.group(1).upper()

        if date is None:
            date_match = re.match(r"^(\d{4}-\d{2}-\d{2})_", tile_name)
            date = date_match.group(1) if date_match else "Parcelle importée"
        if not tile_name:
            ignored.append(name)
            continue

        parcel = parcels.setdefault(date, {})
        tile = parcel.setdefault(tile_name, {"bands": {}, "label": None})
        if field == "label":
            tile["label"] = reference
        else:
            tile["bands"][field] = reference

    return parcels, ignored


def read_reference(reference):
    """Read a local path, uploaded file, byte string, or zip member."""
    if isinstance(reference, tuple) and reference and reference[0] == "zip":
        _, archive_bytes, member_name = reference
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            return archive.read(member_name)
    if isinstance(reference, (str, bytes, os.PathLike)):
        if isinstance(reference, bytes):
            return reference
        with open(reference, "rb") as source:
            return source.read()
    return reference.getvalue()


def read_band(reference):
    with Image.open(io.BytesIO(read_reference(reference))) as image:
        image_mode = image.mode
        array = np.asarray(image)
    if array.ndim != 2:
        raise ValueError("Les bandes spectrales doivent être des images PNG en niveaux de gris.")
    if image_mode in ("I", "I;16", "I;16B", "I;16L"):
        array = array.astype(np.float32) / np.float32(65535.0)
    elif np.issubdtype(array.dtype, np.integer):
        array = array.astype(np.float32) / np.float32(np.iinfo(array.dtype).max)
    else:
        array = array.astype(np.float32)
    return array.astype(np.float32, copy=False)


def read_label(reference):
    with Image.open(io.BytesIO(read_reference(reference))) as image:
        label = np.asarray(image)
    if label.ndim != 2:
        raise ValueError("Les annotations doivent être des masques PNG en niveaux de gris.")
    return label.astype(np.int64, copy=False)


def prepare_tile(tile, band_names, num_classes):
    missing = [band for band in band_names if band not in tile["bands"]]
    if missing:
        return None, "bandes manquantes : " + ", ".join(missing)

    bands = [read_band(tile["bands"][band]) for band in band_names]
    if any(band.shape != bands[0].shape for band in bands[1:]):
        return None, "les dimensions des bandes ne correspondent pas"

    features = np.stack(bands, axis=0)
    rgb = np.stack([read_band(tile["bands"][band]) for band in ("R", "G", "B")], axis=-1)
    rgb = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)

    label = None
    if tile["label"] is not None:
        label = read_label(tile["label"])
        if label.shape != bands[0].shape:
            return None, "les dimensions de l’annotation ne correspondent pas"
        if num_classes == 3:
            label = label.copy()
            label[label > 1] = 2

    return {"features": features, "rgb": rgb, "label": label}, None


def index_rgb_image(reference, name):
    """Create a one-tile parcel from a standalone RGB image."""
    if os.path.splitext(name)[1].lower() not in (".png", ".jpg", ".jpeg"):
        raise ValueError("L’image doit être au format PNG ou JPEG.")
    return index_rgb_images([(name, reference)])


def index_rgb_images(entries):
    """Create one composite parcel from multiple standalone RGB images."""
    tiles = {}
    for name, reference in entries:
        normalized = name.replace("\\", "/")
        stem, extension = os.path.splitext(normalized)
        if extension.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        if Path(stem).name.casefold().startswith(("band_", "bande_")):
            continue

        base_name = stem.strip("/")
        if not base_name:
            raise ValueError("Le nom d’une image est invalide.")
        tile_name = base_name
        if tile_name in tiles:
            tile_name = "{} ({})".format(base_name, extension[1:].lower())
            duplicate_index = 2
            while tile_name in tiles:
                tile_name = "{} ({})".format(
                    base_name, duplicate_index
                )
                duplicate_index += 1
        tiles[tile_name] = {"bands": {}, "label": None, "image": reference}

    return {"Composite": tiles} if tiles else {}


def index_rgb_directory(root):
    """Index RGB images recursively, excluding individual spectral-band files."""
    entries = []
    for directory, _, filenames in os.walk(root):
        for filename in filenames:
            if Path(filename).suffix.lower() not in (".png", ".jpg", ".jpeg"):
                continue
            if Path(filename).stem.casefold().startswith(("band_", "bande_")):
                continue
            path = os.path.join(directory, filename)
            entries.append((os.path.relpath(path, root), path))
    return index_rgb_images(sorted(entries))


def prepare_rgb_image(reference):
    """Decode a standalone RGB image into model features and a display image."""
    with Image.open(io.BytesIO(read_reference(reference))) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    features = np.transpose(rgb.astype(np.float32) / np.float32(255.0), (2, 0, 1))
    return {"features": features, "rgb": rgb, "label": None}


def update_confusion(confusion, prediction, label, num_classes):
    valid = (label >= 0) & (label < num_classes)
    if not np.any(valid):
        return False
    encoded = num_classes * label[valid].astype(np.int64) + prediction[valid].astype(np.int64)
    confusion += np.bincount(encoded, minlength=num_classes * num_classes).reshape(
        num_classes, num_classes
    )
    return True


def scores_from_confusion(confusion):
    true_positive = np.diag(confusion).astype(np.float64)
    union = confusion.sum(axis=0) + confusion.sum(axis=1) - true_positive
    iou = np.full(true_positive.shape, np.nan, dtype=np.float64)
    present = union > 0
    iou[present] = true_positive[present] / union[present]
    mean_iou = float(np.mean(iou[present])) if np.any(present) else float("nan")
    return iou, mean_iou


def index_directory(root):
    entries = []
    for directory, _, filenames in os.walk(root):
        for filename in filenames:
            if filename.lower().endswith(".png"):
                path = os.path.join(directory, filename)
                entries.append((os.path.relpath(path, root), path))
    return index_parcel_files(entries)


def index_zip(archive_bytes):
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        entries = [
            (name, ("zip", archive_bytes, name))
            for name in archive.namelist()
            if not name.endswith("/") and name.lower().endswith(".png")
        ]
    return index_parcel_files(entries)


def combine_parcels(parcels):
    """Combine every date in a selected folder into one uniquely named tile map."""
    combined = {}
    for date, tiles in sorted(parcels.items()):
        for tile_name, tile in sorted(tiles.items()):
            combined_name = "{}/{}".format(date, tile_name) if len(parcels) > 1 else tile_name
            combined[combined_name] = tile
    return combined
