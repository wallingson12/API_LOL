"""Treina reconhecimento do campeão a partir dos frames em data/memlol_videos/."""

from pathlib import Path
import re

import cv2
import numpy as np
import tensorflow as tf

ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "data" / "memlol_videos"
MODEL_PATH = ROOT / "data" / "ml_ability" / "mobilenet.keras"

IMAGE_SIZE = 224
FRAMES = 12
EPOCHS = 20
BATCH = 32
FILE_RE = re.compile(r"^(.+)_(Q|W|E|R)\.(webm|mp4)$", re.I)


def list_clips():
    items = []
    for path in sorted(VIDEO_DIR.iterdir()):
        m = FILE_RE.match(path.name)
        if m:
            items.append((path, m.group(1)))
    return items


def sample_frames(path, n=FRAMES):
    cap = cv2.VideoCapture(str(path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    frames = []
    if total <= 0:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame)
        cap.release()
        if not frames:
            return []
        idx = [round(i * (len(frames) - 1) / max(n - 1, 1)) for i in range(min(n, len(frames)))]
        return [frames[i] for i in idx]
    for i in [round(k * (total - 1) / max(n - 1, 1)) for k in range(n)]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if ok:
            frames.append(frame)
    cap.release()
    return frames


def _frame_array(frame):
    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return tf.image.resize(img, [IMAGE_SIZE, IMAGE_SIZE]).numpy() / 255.0


def load_xy():
    """Val = últimos 25% dos frames de CADA campeão (não o fim da lista A–Z)."""
    clips = list_clips()
    names = sorted({n for _, n in clips})
    lab = {n: i for i, n in enumerate(names)}
    by_champ = {n: [] for n in names}
    for i, (path, name) in enumerate(clips, 1):
        for frame in sample_frames(path):
            by_champ[name].append(_frame_array(frame))
        if i % 50 == 0 or i == len(clips):
            print(f"  [{i}/{len(clips)}] {path.name}")

    x_tr, y_tr, x_va, y_va = [], [], [], []
    for name, frames in by_champ.items():
        if not frames:
            continue
        cut = max(1, int(len(frames) * 0.75))
        if cut >= len(frames):
            cut = len(frames) - 1
        idx = lab[name]
        x_tr.extend(frames[:cut])
        y_tr.extend([idx] * cut)
        x_va.extend(frames[cut:])
        y_va.extend([idx] * (len(frames) - cut))

    n = len(names)
    return (
        np.asarray(x_tr, np.float32),
        tf.keras.utils.to_categorical(y_tr, n),
        np.asarray(x_va, np.float32),
        tf.keras.utils.to_categorical(y_va, n),
        names,
    )


def build_model(n_classes):
    base = tf.keras.applications.MobileNetV2(
        input_shape=(IMAGE_SIZE, IMAGE_SIZE, 3),
        include_top=False,
        weights="imagenet",
    )
    base.trainable = False
    model = tf.keras.Sequential([
        base,
        tf.keras.layers.GlobalAveragePooling2D(),
        tf.keras.layers.Dense(512, activation="relu"),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(n_classes, activation="softmax"),
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-4),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def train():
    x_tr, y_tr, x_va, y_va, names = load_xy()
    print(len(x_tr), "train", len(x_va), "val", len(names), "classes")
    model = build_model(len(names))
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.fit(
        x_tr, y_tr,
        validation_data=(x_va, y_va),
        epochs=EPOCHS,
        batch_size=BATCH,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(patience=4, restore_best_weights=True),
            tf.keras.callbacks.ReduceLROnPlateau(patience=2, factor=0.3),
            tf.keras.callbacks.ModelCheckpoint(str(MODEL_PATH), save_best_only=True),
        ],
    )
    np.save(MODEL_PATH.with_suffix(".labels.npy"), np.array(names))
    print("salvo", MODEL_PATH)


def predict(path):
    names = np.load(MODEL_PATH.with_suffix(".labels.npy"), allow_pickle=True)
    model = tf.keras.models.load_model(MODEL_PATH)
    frames = sample_frames(Path(path))
    batch = np.stack([
        tf.image.resize(cv2.cvtColor(f, cv2.COLOR_BGR2RGB), [IMAGE_SIZE, IMAGE_SIZE]).numpy() / 255.0
        for f in frames
    ])
    p = model.predict(batch, verbose=0).mean(0)
    for i in p.argsort()[::-1][:5]:
        print(f"  {names[i]:20s} {p[i]:.3f}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        predict(sys.argv[1])
    else:
        train()
