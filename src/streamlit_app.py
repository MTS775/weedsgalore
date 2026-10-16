# SPDX-FileCopyrightText: 2025 Helmholtz Centre Potsdam - GFZ German Research Centre for Geosciences
# SPDX-License-Identifier: Apache-2.0

import csv
import io
import os
import sys
from pathlib import Path

import numpy as np
import streamlit as st
import torch
import torch.nn as nn
import torch.nn.functional as functional
from packaging.version import parse as parse_version
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(__file__).resolve().parent
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from nets import deeplabv3plus_resnet50
from parcel_utils import (
    combine_parcels,
    index_directory,
    index_parcel_files,
    index_zip,
    prepare_tile,
    scores_from_confusion,
    update_confusion,
)
from project_paths import list_dataset_subdirectories, resolve_project_path
from connexion_streamlit import render_authentication
from gestion_authorisation import (
    USER_MANAGEMENT_PAGE,
    can_access_page,
    get_accessible_pages,
)
from gestion_utilisateurs import render_user_management


st.set_page_config(
    page_title="WeedsGalore | Analyse Intelligente de Parcelle",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

current_user = render_authentication()
if current_user is None:
    st.stop()
available_pages = get_accessible_pages(current_user["role"])
selected_page = st.sidebar.radio(
    "Navigation",
    available_pages,
    key="main-navigation",
)
if selected_page == USER_MANAGEMENT_PAGE:
    if not can_access_page(current_user["role"], USER_MANAGEMENT_PAGE):
        st.error("L’administration des comptes est réservée aux administrateurs.")
        st.stop()
    render_user_management(current_user)
    st.stop()

CLASS_COLORS = np.asarray(
    [
        (37, 48, 61),
        (57, 181, 74),
        (247, 190, 65),
        (239, 105, 80),
        (91, 155, 213),
        (172, 112, 205),
    ],
    dtype=np.uint8,
)

# Style CSS corrigé pour un affichage normal et lisible de tous les composants
st.markdown(
    """
    <style>
    .stApp { background: #f8fafc; color: #0f172a; }
    
    /* Onglets : texte noir stable, sans changement rouge au survol */
    [data-baseweb="tab"],
    [data-baseweb="tab"] p,
    [data-baseweb="tab"] span {
        color: #000000 !important;
        font-weight: 600;
    }
    [data-baseweb="tab"]:hover,
    [data-baseweb="tab"]:hover p,
    [data-baseweb="tab"]:hover span,
    [data-baseweb="tab"][aria-selected="true"],
    [data-baseweb="tab"][aria-selected="true"] p,
    [data-baseweb="tab"][aria-selected="true"] span {
        color: #000000 !important;
        background-color: #e8f5e9 !important;
    }
    [data-baseweb="tab-highlight"] {
        background-color: #16803c !important;
    }

    [data-testid="stSidebar"] { 
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%); 
        border-right: 1px solid #334155;
    }
    /* Restauration de la visibilité normale des textes de la sidebar */
    [data-testid="stSidebar"] *, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { 
        color: #f1f5f9 !important; 
    }
    
    /* Correction des métriques */
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"], [data-testid="stMetricDelta"] {
        color: #0f172a !important;
    }

    .hero {
        padding: 2rem 2.2rem; border-radius: 20px; margin-bottom: 1.5rem;
        color: #ffffff; background: linear-gradient(135deg, #065f46 0%, #047857 50%, #059669 100%);
        box-shadow: 0 10px 25px -5px rgba(5, 150, 105, 0.25), 0 8px 10px -6px rgba(5, 150, 105, 0.25);
    }
    .hero h1 { margin: 0; font-size: 2.2rem; font-weight: 800; letter-spacing: -0.025em; color: #ffffff !important; }
    .hero p { margin: 0.5rem 0 0; color: #a7f3d0 !important; font-size: 1.05rem; }
    
    .hint {
        padding: 1rem 1.25rem; border-radius: 12px; background: #ecfdf5;
        color: #065f46; border-left: 5px solid #10b981; font-size: 0.95rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        margin-bottom: 1rem;
    }
    
    /* Boutons principaux */
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #059669 0%, #047857 100%);
        color: white !important;
        border: none;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: all 0.2s ease;
    }
    div.stButton > button:first-child:hover {
        background: linear-gradient(135deg, #047857 0%, #065f46 100%);
        box-shadow: 0 6px 8px -1px rgba(0, 0, 0, 0.15);
        transform: translateY(-1px);
    }

    /* =========================================================
       Sliders : couleur verte cohérente avec le thème WeedsGalore
       ========================================================= */
    [data-testid="stSlider"] {
        --primary-color: #16803c !important;
    }

    [data-testid="stSlider"] [data-baseweb="slider"] > div > div {
        background-color: #16803c !important;
    }

    [data-testid="stSlider"] [role="slider"] {
        background-color: #16803c !important;
        border-color: #16803c !important;
        box-shadow: 0 0 0 1px #16803c !important;
    }

    [data-testid="stSlider"] [data-baseweb="slider"] div[role="presentation"] {
        background-color: #16803c !important;
    }

    [data-testid="stSlider"] label,
    [data-testid="stSlider"] label p {
        color: #0f172a !important;
    }

    /* Fond secondaire appliqué au libellé seulement, pas au slider. */
    .st-key-grid-columns [data-testid="stWidgetLabel"],
    .st-key-grid-columns [data-testid="stWidgetLabel"] p,
    .st-key-grid-columns [data-testid="stWidgetLabel"] span,
    .st-key-parcel-selector [data-testid="stWidgetLabel"],
    .st-key-parcel-selector [data-testid="stWidgetLabel"] p,
    .st-key-parcel-selector [data-testid="stWidgetLabel"] span {
        background-color: #ffffff !important;
        color: #0f172a !important;
    }
    .st-key-grid-columns [data-testid="stWidgetLabel"],
    .st-key-parcel-selector [data-testid="stWidgetLabel"] {
        display: inline-flex;
        width: fit-content;
        padding: 0.25rem 0.5rem;
        border-radius: 6px;
        margin-bottom: 0.35rem;
    }

    /* Boutons de téléchargement */
    [data-testid="stDownloadButton"] > button {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
    }
    [data-testid="stDownloadButton"] > button * {
        color: white !important;
    }

    /* Bouton de sélection des fichiers/dossiers dans le téléverseur. */
    [data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"] {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        color: #ffffff !important;
        border: none !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
    }
    [data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"]:hover {
        background: linear-gradient(135deg, #047857 0%, #065f46 100%) !important;
        color: #ffffff !important;
        border: none !important;
    }
    [data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"] * {
        color: #ffffff !important;
    }
    </style>
    <div class="hero">
        <h1>🌾 WeedsGalore · Plateforme d'Analyse IA</h1>
        <p>Segmentation multispectrale avancée, suivi de précision et cartographie intelligente des adventices.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

input_text_color = st.get_option("theme.textColor") or "#0f172a"
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] .st-key-checkpoint-path input,
    [data-testid="stSidebar"] .st-key-dataset-path input,
    [data-testid="stSidebar"] .st-key-dataset-subfolder input[role="combobox"] {
        color: __TEXT_COLOR__ !important;
        -webkit-text-fill-color: __TEXT_COLOR__ !important;
        caret-color: __TEXT_COLOR__ !important;
    }
    [data-testid="stSidebar"] .st-key-parcel-selector [data-testid="stSelectbox"] input[role="combobox"] {
        color: __TEXT_COLOR__ !important;
        -webkit-text-fill-color: __TEXT_COLOR__ !important;
        caret-color: __TEXT_COLOR__ !important;
    }
    </style>
    """.replace("__TEXT_COLOR__", input_text_color),
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def load_model(checkpoint_path, checkpoint_mtime, input_channels, num_classes):
    del checkpoint_mtime
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    state_dict = torch.load(checkpoint_path, map_location=device)
    first_conv_weight = state_dict.get("backbone.conv1.weight")
    if first_conv_weight is None or first_conv_weight.ndim != 4:
        raise ValueError(
            "Le checkpoint ne contient pas de poids valides pour la première convolution "
            "du modèle."
        )
    checkpoint_channels = first_conv_weight.shape[1]
    if checkpoint_channels != input_channels:
        checkpoint_mode = "MSI · 5 bandes" if checkpoint_channels == 5 else "RGB · 3 bandes"
        selected_mode = "MSI · 5 bandes" if input_channels == 5 else "RGB · 3 bandes"
        raise ValueError(
            "Le checkpoint sélectionné attend {} canaux ({}), mais l’entrée choisie est {}. "
            "Sélectionnez le modèle {} ou choisissez un checkpoint {} compatible.".format(
                checkpoint_channels,
                checkpoint_mode,
                selected_mode,
                checkpoint_mode,
                selected_mode,
            )
        )

    model = deeplabv3plus_resnet50(num_classes=num_classes)
    if input_channels != model.backbone.conv1.in_channels:
        model.backbone.conv1 = nn.Conv2d(
            input_channels,
            model.backbone.conv1.out_channels,
            kernel_size=7,
            stride=2,
            padding=3,
            bias=False,
        )
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model, device


def class_names(num_classes):
    if num_classes == 3:
        return ["Fond", "Culture", "Adventices"]
    return ["Fond", "Culture"] + ["Adventice {}".format(index) for index in range(1, num_classes - 1)]


def infer_parcel(model, device, parcel, band_names, num_classes, progress_bar, status_text):
    confusion = np.zeros((num_classes, num_classes), dtype=np.int64)
    results = []
    class_pixels = np.zeros(num_classes, dtype=np.int64)
    confidence_sum = 0.0
    confidence_pixels = 0
    annotated_tiles = 0
    skipped = []
    tiles = sorted(parcel.items())
    total_tiles = len(tiles)

    for index, (tile_name, tile) in enumerate(tiles):
        prepared, error = prepare_tile(tile, band_names, num_classes)
        pct = int(((index + 1) / total_tiles) * 100)
        
        if error:
            skipped.append("{} — {}".format(tile_name, error))
            progress_bar.progress((index + 1) / total_tiles)
            status_text.markdown(f"⚙️ Analyse en cours... **{pct}%** ({index + 1}/{total_tiles} tuiles)")
            continue

        features = prepared["features"]
        model_dtype = next(model.parameters()).dtype
        tensor = torch.from_numpy(features).unsqueeze(0).to(device=device, dtype=model_dtype)
        with torch.no_grad():
            logits = model(tensor)
            if logits.shape[-2:] != tensor.shape[-2:]:
                logits = functional.interpolate(
                    logits, size=tensor.shape[-2:], mode="bilinear", align_corners=False
                )
            probabilities = torch.softmax(logits, dim=1)
            confidence, prediction = probabilities.max(dim=1)

        prediction_array = prediction[0].cpu().numpy().astype(np.uint8)
        confidence_array = confidence[0].cpu().numpy()
        class_pixels += np.bincount(
            prediction_array.ravel(), minlength=num_classes
        )[:num_classes]
        confidence_sum += float(confidence_array.sum())
        confidence_pixels += confidence_array.size

        label = prepared["label"]
        if label is not None and update_confusion(confusion, prediction_array, label, num_classes):
            annotated_tiles += 1

        results.append(
            {
                "name": tile_name,
                "rgb": prepared["rgb"],
                "prediction": prediction_array,
                "label": label,
                "confidence": float(confidence_array.mean()),
                "counts": np.bincount(
                    prediction_array.ravel(), minlength=num_classes
                )[:num_classes],
            }
        )
        progress_bar.progress((index + 1) / total_tiles)
        status_text.markdown(f"Analyse IA en cours... **{pct}%** ({index + 1}/{total_tiles} tuiles traitées)")

    if not results:
        raise ValueError("Aucune tuile complète avec les bandes requises n’a été trouvée.")

    iou, mean_iou = scores_from_confusion(confusion)
    return {
        "tiles": results,
        "confusion": confusion,
        "iou": iou,
        "mean_iou": mean_iou,
        "class_pixels": class_pixels,
        "confidence": confidence_sum / confidence_pixels,
        "annotated_tiles": annotated_tiles,
        "skipped": skipped,
    }


def make_mosaics(results, columns, overlay_alpha):
    tiles = results["tiles"]
    max_height = max(tile["rgb"].shape[0] for tile in tiles)
    max_width = max(tile["rgb"].shape[1] for tile in tiles)
    header_height = 26
    gutter = 16  
    rows = (len(tiles) + columns - 1) // columns
    canvas_shape = (
        rows * (max_height + header_height + gutter) + gutter,
        columns * (max_width + gutter) + gutter,
    )
    rgb_mosaic = np.full(canvas_shape + (3,), 255, dtype=np.uint8)
    mask_mosaic = np.full(canvas_shape + (3,), 255, dtype=np.uint8)
    overlay_mosaic = np.full(canvas_shape + (3,), 255, dtype=np.uint8)

    for index, tile in enumerate(tiles):
        row, column = divmod(index, columns)
        top = gutter + row * (max_height + header_height + gutter)
        left = gutter + column * (max_width + gutter)
        height, width = tile["rgb"].shape[:2]
        for canvas in (rgb_mosaic, mask_mosaic, overlay_mosaic):
            canvas[top:top + header_height, left:left + width] = (22, 48, 39)
        rgb_mosaic[top + header_height:top + header_height + height, left:left + width] = tile["rgb"]

        colors = CLASS_COLORS[tile["prediction"]]
        mask_mosaic[
            top + header_height:top + header_height + height, left:left + width
        ] = colors
        overlay = (
            tile["rgb"].astype(np.float32) * (1.0 - overlay_alpha)
            + colors.astype(np.float32) * overlay_alpha
        )
        overlay_mosaic[
            top + header_height:top + header_height + height, left:left + width
        ] = np.clip(overlay, 0, 255).astype(np.uint8)

        for canvas in (rgb_mosaic, mask_mosaic, overlay_mosaic):
            header = Image.fromarray(canvas[top:top + header_height, left:left + width])
            ImageDraw.Draw(header).text((6, 5), tile["name"], fill=(255, 255, 255))
            canvas[top:top + header_height, left:left + width] = np.asarray(header)

    return rgb_mosaic, mask_mosaic, overlay_mosaic


def image_png_bytes(image):
    output = io.BytesIO()
    Image.fromarray(image).save(output, format="PNG")
    return output.getvalue()


def make_metrics_csv(results, names):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Classe", "Part des pixels (%)", "IoU (%)"])
    total = int(results["class_pixels"].sum())
    has_annotations = results["annotated_tiles"] > 0
    for index, name in enumerate(names):
        proportion = 100.0 * results["class_pixels"][index] / total
        iou = results["iou"][index]
        writer.writerow(
            [
                name,
                "{:.4f}".format(proportion),
                "{:.4f}".format(100.0 * iou) if has_annotations and np.isfinite(iou) else "",
            ]
        )
    return output.getvalue().encode("utf-8")


# --- BARRE LATÉRALE ---
st.sidebar.markdown("## ⚙️ Paramètres du Modèle")
input_option = st.sidebar.radio("🛰️ Entrée du modèle", ["MSI · 5 bandes", "RGB · 3 bandes"])
input_channels = 5 if input_option.startswith("MSI") else 3
band_names = ["R", "G", "B", "NIR", "RE"] if input_channels == 5 else ["R", "G", "B"]
class_option = st.sidebar.radio("🏷️ Classes prédites", ["Multi-classes · 6", "Adventices · 3"])
num_classes = 6 if class_option.endswith("6") else 3
checkpoint_variant = "msi" if input_channels == 5 else "rgb"
checkpoint_default = resolve_project_path(
    os.environ.get(
        "WEEDSGALORE_CHECKPOINT",
        PROJECT_ROOT / "ckpts" / "dlv3p_{}_{}.pth".format(checkpoint_variant, num_classes),
    ),
    PROJECT_ROOT,
)
previous_checkpoint_default = st.session_state.get("_checkpoint_default")
current_checkpoint_path = st.session_state.get("checkpoint-path")
if current_checkpoint_path is None or current_checkpoint_path == previous_checkpoint_default:
    st.session_state["checkpoint-path"] = str(checkpoint_default)
st.session_state["_checkpoint_default"] = str(checkpoint_default)
checkpoint_path = st.sidebar.text_input(
    "📁 Fichier du modèle (.pth)",
    help="Chemin absolu ou relatif à la racine du projet. Variable possible : WEEDSGALORE_CHECKPOINT.",
    key="checkpoint-path",
)
grid_columns = st.sidebar.slider(
    "📐 Tuiles par ligne (grille)", min_value=2, max_value=8, value=4,
    key="grid-columns",
)

st.sidebar.markdown("---")
source_mode = st.sidebar.radio("📂 Source des images", ["Dossier local", "Téléverser un dossier / ZIP"])
parcels = {}
ignored_files = []
source_identity = ""

if source_mode == "Dossier local":
    dataset_default = resolve_project_path(
        os.environ.get("WEEDSGALORE_DATASET", PROJECT_ROOT / "weedsgalore-dataset"),
        PROJECT_ROOT,
    )
    dataset_path = st.sidebar.text_input(
        "📂 Chemin du dossier dataset",
        value=str(dataset_default),
        help=(
            "Chemin absolu ou relatif à la racine du projet. Modifiable pour utiliser un autre "
            "dossier, par exemple C:\\baseTeste. Variable possible : WEEDSGALORE_DATASET."
        ),
        key="dataset-path",
    )
    dataset_root = resolve_project_path(dataset_path, PROJECT_ROOT)
    if dataset_root.is_dir():
        dataset_folders = [str(dataset_root)] + [
            str(path) for path in list_dataset_subdirectories(dataset_root)
        ]
        if st.session_state.get("dataset-subfolder") not in dataset_folders:
            st.session_state["dataset-subfolder"] = dataset_folders[0]
        selected_folder = st.sidebar.selectbox(
            "📁 Sélectionner le sous-dossier",
            options=dataset_folders,
            format_func=lambda path: (
                "Racine complète du dataset"
                if Path(path) == dataset_root
                else str(Path(path).relative_to(dataset_root))
            ),
            key="dataset-subfolder",
            help="Sélectionnez le dossier dont toutes les parcelles seront analysées.",
        )
        selected_dataset_root = Path(selected_folder)
        parcels, ignored_files = index_directory(str(selected_dataset_root))
        source_identity = str(selected_dataset_root.resolve())
    else:
        st.info(
            "Saisissez le chemin d’un dossier existant sur la machine qui exécute Streamlit. "
            "Les chemins relatifs partent de la racine du projet."
        )
else:
    supports_directory = parse_version(st.__version__) >= parse_version("1.46.0")
    if supports_directory:
        upload_type = st.sidebar.radio("📦 Type de téléversement", ["Dossier de PNG", "Archive ZIP"])
        if upload_type == "Dossier de PNG":
            uploaded = st.sidebar.file_uploader(
                "Sélectionner un dossier de tuiles",
                type=["png"],
                accept_multiple_files="directory",
                help="Déposez un dossier de date avec images/ et, si disponibles, semantics/.",
            )
        else:
            uploaded = st.sidebar.file_uploader("Sélectionner une archive ZIP", type=["zip"])
    else:
        uploaded = st.sidebar.file_uploader(
            "Importer un ZIP ou plusieurs PNG",
            type=["png", "zip"],
            accept_multiple_files=True,
        )
    if uploaded:
        if isinstance(uploaded, list) and len(uploaded) == 1 and uploaded[0].name.lower().endswith(".zip"):
            archive_bytes = uploaded[0].getvalue()
            parcels, ignored_files = index_zip(archive_bytes)
            source_identity = uploaded[0].name
        elif not isinstance(uploaded, list) and uploaded.name.lower().endswith(".zip"):
            archive_bytes = uploaded.getvalue()
            parcels, ignored_files = index_zip(archive_bytes)
            source_identity = uploaded.name
        else:
            entries = [(item.name, item) for item in uploaded] if isinstance(uploaded, list) else [(uploaded.name, uploaded)]
            parcels, ignored_files = index_parcel_files(entries)
            source_identity = "|".join(name for name, _ in entries)

if ignored_files:
    st.sidebar.caption("⚠️ {} fichier(s) ignoré(s) (nom de bande non reconnu).".format(len(ignored_files)))

if not parcels:
    st.markdown(
        '<div class="hint">🌱 Chargez un dossier WeedsGalore contenant des tuiles nommées '
        '<code>date_tuile_R.png</code>, <code>_G.png</code>, <code>_B.png</code>, '
        '<code>_NIR.png</code> et <code>_RE.png</code> pour MSI. '
        'Les masques facultatifs doivent être sous <code>semantics/</code>.</div>',
        unsafe_allow_html=True,
    )
    st.stop()

parcel = combine_parcels(parcels)
selected_folder_name = Path(source_identity).name or "dataset"

available_tiles = sum(
    all(band in tile["bands"] for band in band_names) for tile in parcel.values()
)
st.sidebar.caption(
    "📊 {} tuile(s) indexée(s), {} complète(s) pour {}.".format(
        len(parcel), available_tiles, input_option
    )
)

st.markdown(
    '<div class="hint"><strong>Assemblage visuel de la parcelle :</strong> Les tuiles sont rangées par identifiant '
    'dans une grille interactive. Le jeu fourni ne contient pas de coordonnées spatiales pour ces tuiles ; '
    'la grille n’est donc pas une mosaïque géoréférencée exacte.</div>',
    unsafe_allow_html=True,
)

checkpoint = resolve_project_path(checkpoint_path, PROJECT_ROOT)
checkpoint_exists = checkpoint.is_file()
if not checkpoint_exists:
    st.warning("⚠️ Modèle introuvable : vérifiez le chemin du checkpoint dans la barre latérale.")
    st.stop()
checkpoint_mtime = checkpoint.stat().st_mtime
signature = (
    source_identity,
    str(checkpoint.resolve()),
    checkpoint_mtime,
    input_channels,
    num_classes,
    tuple(sorted(parcel)),
)

if st.button("Lancer l’analyse de la parcelle", type="primary", width="stretch"):
    st.session_state.pop("parcel_result", None)
    try:
        with st.spinner(" ", show_time=False):
            model, device = load_model(
                str(checkpoint.resolve()), checkpoint_mtime, input_channels, num_classes
            )
        st.caption(f"⚡ Inférence matérielle active sur : **{device.type.upper()}**")
        
        status_text = st.empty()
        progress_bar = st.progress(0.0)
        
        result = infer_parcel(model, device, parcel, band_names, num_classes, progress_bar, status_text)
        result["signature"] = signature
        st.session_state["parcel_result"] = result
        progress_bar.empty()
        status_text.empty()
        st.success("✅ Analyse et segmentation terminées avec succès !")
    except Exception as error:
        if isinstance(error, ValueError):
            st.error(str(error))
        else:
            st.exception(error)
        st.stop()

result = st.session_state.get("parcel_result")
if result is None:
    st.info("💡 Choisissez vos paramètres dans la barre latérale puis lancez l’analyse pour afficher les prédictions, la progression et les scores.")
    st.stop()
if result["signature"] != signature:
    st.warning("⚠️ Les paramètres ou la source ont changé. Relancez l’analyse pour actualiser les résultats.")
    st.stop()

names = class_names(num_classes)
has_annotations = result["annotated_tiles"] > 0
mean_iou = result["mean_iou"]

# Affichage des métriques globales
col_a, col_b, col_c = st.columns(3)
col_a.metric("🛰️ Tuiles segmentées", len(result["tiles"]))
col_b.metric("🎯 Confiance moyenne", "{:.1f} %".format(result["confidence"] * 100))
col_c.metric(
    "📈 mIoU global",
    "{:.1f} %".format(mean_iou * 100) if has_annotations and np.isfinite(mean_iou) else "N/D",
    help="Calculée uniquement sur les pixels annotés disponibles.",
)

if has_annotations and result["annotated_tiles"] < len(result["tiles"]):
    st.warning(
        "⚠️ Annotations trouvées pour {} tuile(s) sur {} ; l’IoU est calculée sur ces seules tuiles.".format(
            result["annotated_tiles"], len(result["tiles"])
        )
    )
elif not has_annotations:
    st.info("ℹ️ Aucun masque d’annotation détecté : l’IoU n’est pas calculable pour cette parcelle.")
if result["skipped"]:
    with st.expander("⚠️ Tuiles ignorées ou incomplètes"):
        st.write("\n".join(result["skipped"]))

tab_parcel, tab_tile, tab_scores = st.tabs(["🗺️ Vue Parcelle", "🔎 Détail d’une tuile", "📊 Scores & Statistiques"])

with tab_parcel:
    parcel_opacity = st.slider("✨ Opacité de la prédiction sur la parcelle", 0.0, 1.0, 0.55, 0.05)
    rgb_mosaic, mask_mosaic, overlay_mosaic = make_mosaics(
        result, grid_columns, parcel_opacity
    )
    mosaic_a, mosaic_b, mosaic_c = st.columns(3)
    mosaic_a.image(rgb_mosaic, caption="Entrée RGB · Grille visuelle", width="stretch")
    mosaic_b.image(mask_mosaic, caption="Segmentation prédite par l'IA", width="stretch")
    mosaic_c.image(overlay_mosaic, caption="Superposition de la segmentation", width="stretch")
    
    st.download_button(
        "📥 Télécharger la segmentation complète de la parcelle (PNG)",
        data=image_png_bytes(mask_mosaic),
        file_name="segmentation_{}.png".format(selected_folder_name.replace(" ", "_")),
        mime="image/png",
    )

with tab_tile:
    selected_tile_name = st.selectbox("🔎 Sélectionner une tuile spécifique", [tile["name"] for tile in result["tiles"]])
    selected_tile = next(tile for tile in result["tiles"] if tile["name"] == selected_tile_name)
    opacity = st.slider("✨ Opacité de la segmentation (Tuile)", 0.0, 1.0, 0.55, 0.05)
    colors = CLASS_COLORS[selected_tile["prediction"]]
    overlay = (
        selected_tile["rgb"].astype(np.float32) * (1.0 - opacity)
        + colors.astype(np.float32) * opacity
    )
    detail_a, detail_b, detail_c = st.columns(3)
    detail_a.image(selected_tile["rgb"], caption="Image RGB de la tuile", width="stretch")
    detail_b.image(colors, caption="Masque prédit", width="stretch")
    detail_c.image(np.clip(overlay, 0, 255).astype(np.uint8), caption="Superposition", width="stretch")
    
    if selected_tile["label"] is not None:
        valid_labels = (selected_tile["label"] >= 0) & (selected_tile["label"] < num_classes)
        ground_truth = np.zeros(selected_tile["label"].shape + (3,), dtype=np.uint8)
        ground_truth[valid_labels] = CLASS_COLORS[selected_tile["label"][valid_labels]]
        st.image(ground_truth, caption="Annotation de référence (Ground Truth)", width="stretch")
        
    st.metric("Confiance moyenne de la tuile", "{:.1f} %".format(selected_tile["confidence"] * 100))
    
    st.markdown("#### Légende des classes sémantiques")
    legend_columns = st.columns(num_classes)
    for index, name in enumerate(names):
        color = "#{:02x}{:02x}{:02x}".format(*CLASS_COLORS[index])
        legend_columns[index].markdown(
            '<span style="display:inline-block;width:14px;height:14px;border-radius:4px;'
            'background:{};margin-right:6px;vertical-align:middle;"></span><strong style="font-size:0.9rem; color:#1e293b;">{}</strong>'.format(color, name),
            unsafe_allow_html=True,
        )

with tab_scores:
    total_pixels = int(result["class_pixels"].sum())
    score_rows = []
    for index, name in enumerate(names):
        row = {
            "Classe": name,
            "Part de la parcelle (%)": 100.0 * result["class_pixels"][index] / total_pixels,
        }
        if has_annotations:
            row["IoU (%)"] = (
                100.0 * result["iou"][index]
                if np.isfinite(result["iou"][index])
                else float("nan")
            )
        score_rows.append(row)
    st.dataframe(score_rows, hide_index=True, width="stretch")
    st.caption("ℹ️ Les proportions affichées sont calculées sur l’ensemble des pixels prédits de la parcelle.")

    tile_rows = []
    for tile in result["tiles"]:
        row = {
            "Tuile": tile["name"],
            "Confiance moyenne (%)": 100.0 * tile["confidence"],
        }
        for index, name in enumerate(names):
            row[name + " (%)"] = 100.0 * tile["counts"][index] / tile["counts"].sum()
        tile_rows.append(row)
        
    with st.expander("📋 Consulter les scores détaillés par tuile"):
        st.dataframe(tile_rows, hide_index=True, width="stretch")

    csv_data = make_metrics_csv(result, names)
    st.download_button(
        "📥 Télécharger les scores complets (CSV)",
        data=csv_data,
        file_name="scores_{}.csv".format(selected_folder_name.replace(" ", "_")),
        mime="text/csv",
    )