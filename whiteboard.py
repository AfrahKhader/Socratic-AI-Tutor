"""
Streamlit Whiteboard with Grid-Overlay Export and Combined Text+Sketch Payload

Features added on top of the basic whiteboard:
- Drawings are exported as PNGs with a coordinate grid burned in.
- The user's written question + sketch are submitted together as one request
  to the backend pipeline (single turn).
"""

from __future__ import annotations  # enables `X | None` type syntax on Python 3.9

import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import io
import base64
import json

# ---------- Page config ----------
st.set_page_config(page_title="Socratic Tutor — Whiteboard", page_icon="🎨", layout="wide")
st.title("🎨 Ask with a Sketch")
st.caption("Type your question and draw a diagram. Both are sent together.")

# ---------- Sidebar: drawing controls ----------
with st.sidebar:
    st.header("🛠️ Drawing tools")
    drawing_mode = st.selectbox(
        "Tool", ("freedraw", "line", "rect", "circle", "polygon", "point", "transform")
    )
    stroke_width = st.slider("Stroke width", 1, 30, 3)
    stroke_color = st.color_picker("Stroke color", "#000000")
    bg_color = st.color_picker("Background", "#FFFFFF")

    st.divider()
    st.subheader("📐 Grid (on export)")
    grid_spacing = st.slider("Grid spacing (px)", 20, 200, 50, step=10)
    grid_color = st.color_picker("Grid color", "#CCCCCC")
    label_color = st.color_picker("Label color", "#666666")
    show_grid_preview = st.checkbox("Show grid in preview too", value=False)

    st.divider()
    canvas_width = st.slider("Canvas width", 400, 1200, 800, step=50)
    canvas_height = st.slider("Canvas height", 300, 900, 500, step=50)


# ---------- Helper: overlay coordinate grid on an RGBA image ----------
def add_coordinate_grid(
    img: Image.Image,
    spacing: int = 50,
    grid_color: str = "#CCCCCC",
    label_color: str = "#666666",
    label_every: int = 1,
) -> Image.Image:
    """Burn a coordinate grid onto an image so downstream consumers can
    reference positions like (120, 80) when discussing the sketch."""
    out = img.convert("RGBA").copy()
    draw = ImageDraw.Draw(out)
    w, h = out.size

    # Try a real font; fall back to PIL's default if unavailable.
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 10)
    except OSError:
        font = ImageFont.load_default()

    # Vertical lines + x-axis labels along the top
    for i, x in enumerate(range(0, w, spacing)):
        draw.line([(x, 0), (x, h)], fill=grid_color, width=1)
        if i % label_every == 0 and x > 0:
            draw.text((x + 2, 2), str(x), fill=label_color, font=font)

    # Horizontal lines + y-axis labels along the left
    for i, y in enumerate(range(0, h, spacing)):
        draw.line([(0, y), (w, y)], fill=grid_color, width=1)
        if i % label_every == 0 and y > 0:
            draw.text((2, y + 2), str(y), fill=label_color, font=font)

    # Origin marker
    draw.text((2, 2), "0,0", fill=label_color, font=font)
    return out


# ---------- Layout ----------
left, right = st.columns([3, 2])

with left:
    st.subheader("✏️ Sketch")
    canvas_result = st_canvas(
        fill_color="rgba(255, 165, 0, 0.3)",
        stroke_width=stroke_width,
        stroke_color=stroke_color,
        background_color=bg_color,
        update_streamlit=True,
        height=canvas_height,
        width=canvas_width,
        drawing_mode=drawing_mode,
        key="canvas",
    )

with right:
    st.subheader("💬 Your question")
    question = st.text_area(
        "Ask anything about your sketch:",
        placeholder="e.g. 'Why does the force at point (200, 150) push the block to the right?'",
        height=150,
    )

    submit = st.button("🚀 Submit to tutor", type="primary", use_container_width=True)


# ---------- Build the export image with grid ----------
exported_png_bytes = None
if canvas_result.image_data is not None:
    raw_img = Image.fromarray(canvas_result.image_data.astype("uint8"), mode="RGBA")
    # Flatten transparency onto the chosen background so the grid is visible.
    flat = Image.new("RGBA", raw_img.size, bg_color)
    flat.alpha_composite(raw_img)

    gridded = add_coordinate_grid(
        flat, spacing=grid_spacing, grid_color=grid_color, label_color=label_color
    )

    buf = io.BytesIO()
    gridded.convert("RGB").save(buf, format="PNG")
    exported_png_bytes = buf.getvalue()

    if show_grid_preview:
        st.subheader("🖼️ Export preview (with grid)")
        st.image(gridded, use_container_width=True)


# ---------- Build the combined payload ----------
def build_payload(text: str, png_bytes: bytes | None) -> dict:
    """Bundle the typed question + grid-overlaid sketch into a single
    request body for the backend pipeline."""
    payload = {
        "question": text,
        "sketch": None,
    }
    if png_bytes:
        payload["sketch"] = {
            "mime_type": "image/png",
            "encoding": "base64",
            "data": base64.b64encode(png_bytes).decode("ascii"),
            "width": canvas_width,
            "height": canvas_height,
            "grid_spacing_px": grid_spacing,
        }
    return payload


# ---------- Submit handler ----------
if submit:
    if not question.strip() and exported_png_bytes is None:
        st.warning("Add a question, a sketch, or both before submitting.")
    else:
        payload = build_payload(question, exported_png_bytes)

        # --- Replace this block with your real backend call ---
        # Example:
        #   import requests
        #   r = requests.post("https://your-backend/api/ask", json=payload, timeout=60)
        #   response = r.json()
        # ------------------------------------------------------
        st.success("Payload built and ready to send to the backend ✅")

        with st.expander("🔍 Payload preview (what gets sent)"):
            preview = {
                "question": payload["question"],
                "sketch": (
                    {
                        **{k: v for k, v in payload["sketch"].items() if k != "data"},
                        "data": payload["sketch"]["data"][:80] + "... (truncated)",
                    }
                    if payload["sketch"]
                    else None
                ),
            }
            st.json(preview)

        if exported_png_bytes:
            st.subheader("📤 What the backend sees")
            st.image(exported_png_bytes, caption="Sketch with coordinate grid")


# ---------- Always-available download ----------
if exported_png_bytes:
    st.sidebar.divider()
    st.sidebar.download_button(
        "⬇️ Download sketch (with grid)",
        data=exported_png_bytes,
        file_name="sketch_with_grid.png",
        mime="image/png",
        use_container_width=True,
    )