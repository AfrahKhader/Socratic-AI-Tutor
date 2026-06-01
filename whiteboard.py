"""
Streamlit Notebook Whiteboard
A scrolling notebook where each conversation turn has its own canvas + text.
"""

from __future__ import annotations

import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from datetime import datetime

# Pillow 10+ compatibility shim for streamlit-drawable-canvas
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS


st.set_page_config(page_title="Notebook Whiteboard", page_icon="📓", layout="wide")

# ---------- Session state: the notebook ----------
# Each "page" is one turn: {id, question, sketch_png, tutor_reply, timestamp}
if "pages" not in st.session_state:
    st.session_state.pages = []
if "page_counter" not in st.session_state:
    st.session_state.page_counter = 0
if "canvas_key" not in st.session_state:
    # Bumping this resets the active canvas
    st.session_state.canvas_key = 0


# ---------- Sidebar: tools ----------
with st.sidebar:
    st.header(" Tools")
    drawing_mode = st.selectbox(
        "Tool", ("freedraw", "line", "rect", "circle", "polygon", "transform")
    )
    stroke_width = st.slider("Stroke width", 1, 30, 3)
    stroke_color = st.color_picker("Stroke color", "#000000")
    bg_color = st.color_picker("Background", "#FFFFFF")
    grid_spacing = st.slider("Grid spacing (px)", 20, 200, 50, step=10)

    st.divider()
    if st.button("Clear notebook"):
        st.session_state.pages = []
        st.session_state.canvas_key += 1
        st.rerun()


# ---------- Helper: burn a coordinate grid onto an exported image ----------
def add_coordinate_grid(img: Image.Image, spacing: int = 50) -> Image.Image:
    out = img.convert("RGBA").copy()
    draw = ImageDraw.Draw(out)
    w, h = out.size
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 10)
    except OSError:
        font = ImageFont.load_default()
    for x in range(0, w, spacing):
        draw.line([(x, 0), (x, h)], fill="#CCCCCC", width=1)
        if x > 0:
            draw.text((x + 2, 2), str(x), fill="#666666", font=font)
    for y in range(0, h, spacing):
        draw.line([(0, y), (w, y)], fill="#CCCCCC", width=1)
        if y > 0:
            draw.text((2, y + 2), str(y), fill="#666666", font=font)
    draw.text((2, 2), "0,0", fill="#666666", font=font)
    return out


def png_bytes_from_canvas(image_data) -> bytes | None:
    """Convert canvas RGBA array → flattened PNG with grid overlay."""
    if image_data is None:
        return None
    img = Image.fromarray(image_data.astype("uint8"), mode="RGBA")
    flat = Image.new("RGBA", img.size, bg_color)
    flat.alpha_composite(img)
    gridded = add_coordinate_grid(flat, spacing=grid_spacing)
    buf = io.BytesIO()
    gridded.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


# ========== MAIN LAYOUT ==========

st.title("Tutor Notebook")
st.caption("Each entry becomes a page. Scroll up to revisit earlier turns.")

# ---------- Scrollable history (the "notebook") ----------
# st.container(height=...) gives us a fixed-height, vertically scrollable area.
history_box = st.container(height=500, border=True)

with history_box:
    if not st.session_state.pages:
        st.info("Your notebook is empty. Ask your first question below.")
    else:
        for page in st.session_state.pages:
            with st.container(border=True):
                cols = st.columns([1, 2])
                with cols[0]:
                    st.caption(f"🕐 {page['timestamp']}  ·  Page {page['id']}")
                    if page["sketch_png"]:
                        st.image(page["sketch_png"], use_column_width=True)
                    else:
                        st.caption("_(no sketch)_")
                with cols[1]:
                    st.markdown(f"**You:** {page['question']}")
                    st.markdown(f"**Tutor:** {page['tutor_reply']}")
            st.write("")  # spacer


st.divider()

# ---------- Active input area: canvas + text ----------
st.subheader("New entry")

input_cols = st.columns([3, 2])

with input_cols[0]:
    canvas_result = st_canvas(
        fill_color="rgba(255, 165, 0, 0.3)",
        stroke_width=stroke_width,
        stroke_color=stroke_color,
        background_color=bg_color,
        update_streamlit=True,
        height=350,
        width=600,
        drawing_mode=drawing_mode,
        key=f"canvas_{st.session_state.canvas_key}",
    )

with input_cols[1]:
    question = st.text_area(
        "Your question:",
        placeholder="Type your question here…",
        height=200,
        key=f"question_{st.session_state.canvas_key}",
    )

    submit = st.button("Add to notebook", type="primary")


# ---------- Submit handler ----------
def fake_tutor_reply(question: str, has_sketch: bool) -> str:
    """Stand-in for your real backend call."""
    # Replace this with: requests.post(BACKEND_URL, json=payload).json()["reply"]
    parts = []
    if question:
        parts.append(f"You asked: *{question[:80]}*")
    if has_sketch:
        parts.append("Tutor reply .....")
    return " — ".join(parts) or "(no input received)"


if submit:
    sketch_png = png_bytes_from_canvas(canvas_result.image_data)
    has_sketch = sketch_png is not None and canvas_result.json_data and \
                 len(canvas_result.json_data.get("objects", [])) > 0

    if not question.strip() and not has_sketch:
        st.warning("Add a question, a sketch, or both before submitting.")
    else:
        st.session_state.page_counter += 1
        st.session_state.pages.append({
            "id": st.session_state.page_counter,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "question": question.strip() or "_(sketch only)_",
            "sketch_png": sketch_png if has_sketch else None,
            "tutor_reply": fake_tutor_reply(question, has_sketch),
        })
        # Bump canvas key → fresh blank canvas for the next entry
        st.session_state.canvas_key += 1
        st.rerun()