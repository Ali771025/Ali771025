# Annotation Guide

## Python Annotator

### GUI

```bash
python -m yolo_annotator --project datasets/my_dataset --model models/yolov8n.onnx --offline
```

- Dark theme, thumbnail browser, object list
- Canvas: drag to create bbox, drag inside to move, wheel to zoom, handles to resize
- Classes: managed in project.yaml, auto-colored
- Shortcuts:
  - Delete: delete selected
  - Ctrl+Z / Ctrl+Y: undo/redo (if history enabled)
  - Mouse wheel: zoom
  - Drag: create/move
  - Right-click: context

### Project management

- Project folder contains:
  - `project.yaml`: classes, colors, config
  - `images/`: imported images
  - `labels/`: optional YOLO labels cache
  - `.backup/`: backups

- Recent projects remembered? Open via Open Project.

- Autosave: saves project.yaml periodically.

### Media import

- `Import Images`: folder recursively finds jpg/png etc
- `Import Video`: extracts frames at configurable FPS (default 1 FPS) into project
- For images, original path kept if not copied; option to copy into project

### Annotation tools

- Rectangle bbox: primary
- Polygon: future (currently bbox with segmentation fallback via SAM/GrabCut)
- Move/resize
- Copy/paste (Ctrl+C/V) - Qt implementation copies selected object
- Delete
- Undo/redo
- Zoom/pan
- Crosshair
- Class assignment via combo box
- Visibility toggle

### AI Assistance (offline)

- Auto-detect with local YOLO ONNX: toolbar -> Auto-Label All or per image
- Confidence threshold from config
- Class filter
- Accept/reject: AI boxes marked with AI flag, different alpha; user can delete or edit
- SAM assistance:
  - If `models/mobile_sam.onnx` or `mobile_sam.pt` present, box-to-mask via GrabCut fallback (SAM stub) - can be replaced with real MobileSAM ONNX inference
  - Click-to-segment optional: future
- Video tracking propagation: IoU tracker can propagate boxes between extracted frames (auto-label per frame + track ID)
- Human-in-the-loop review: mark image as reviewed/not-reviewed/rejected

### Export

- YOLO: `labels/*.txt` normalized cx cy w h + `dataset.yaml` with class names
- COCO: `coco.json` with info, images, annotations, categories
- VOC: `*.xml` Pascal VOC
- Import also supported: load existing YOLO/COCO/VOC datasets for editing

### Dataset tools

- Train/val/test split: not yet automated, but exporter can be extended
- Class manager: edit classes in project.yaml
- Statistics: count per class shown in thumbnail panel

### Performance

- Lazy loading: only current image in memory
- Thumbnail caching: small size (128) thumbnails for browser (future)
- Background AI inference: AutoLabeler uses thread pool, not blocking UI
- GPU/CPU selectable via --device

### Headless

```bash
python -m yolo_annotator --project datasets/my_dataset --model models/yolov8n.onnx --headless --images data/raw --export-format yolo --export-path datasets/my_dataset/export_yolo
```

Useful for batch auto-labeling on server.

## C++ Annotator

Similar workflow:

```bash
./build/yolo_annotator --project datasets/my_dataset --model models/yolov8n.onnx
./build/yolo_annotator --project datasets/my_dataset --model models/yolov8n.onnx --images data/images --export-format yolo --export-path out/ --headless
```

- Core reuses `yolo_core` detector for AI pre-labeling
- GUI uses Qt6, split panels, OpenCV for drawing
- Exporters same schema as Python

## Tips

- Start with small model `yolov8n.onnx` or `yolo11n.onnx` for fast auto-label on CPU
- Verify auto-labels before export - low confidence (<0.5) may include false positives
- Use class filter to only auto-label certain classes
- For precise masks, use SAM if available, otherwise box is sufficient for detection datasets
- Keep backup of project

## Security

- No cloud, no telemetry
- Models local in ./models
- No secrets in project files

## Future

- Polygon editing with Bezier
- Keypoint annotation
- Mask painting
- Active learning: export low-confidence samples for retraining
```
