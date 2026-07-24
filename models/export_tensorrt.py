#!/usr/bin/env python3
"""
Export ONNX to TensorRT engine via TensorRT or Ultralytics
"""
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Export ONNX/PT to TensorRT engine")
    parser.add_argument("--model", type=str, required=True, help="Path to .onnx or .pt")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--half", action="store_true", help="FP16")
    parser.add_argument("--device", type=int, default=0, help="CUDA device")
    args = parser.parse_args()

    p = Path(args.model)
    if not p.exists():
        print(f"Model not found: {p}")
        return

    try:
        from ultralytics import YOLO
        model = YOLO(str(p))
        print(f"Exporting {p} to TensorRT engine")
        out = model.export(format="engine", imgsz=args.imgsz, half=args.half, device=args.device)
        print(f"Exported: {out}")
        return
    except Exception as e:
        print(f"Ultralytics export failed: {e}, trying manual TensorRT build")

    # manual TensorRT build if ultralytics not available
    try:
        import tensorrt as trt
        import onnx
        # Implement minimal TRT engine builder
        TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
        builder = trt.Builder(TRT_LOGGER)
        network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
        parser_trt = trt.OnnxParser(network, TRT_LOGGER)
        config = builder.create_builder_config()
        config.max_workspace_size = 1 << 30
        if args.half:
            config.set_flag(trt.BuilderFlag.FP16)
        with open(args.model, "rb") as f:
            if not parser_trt.parse(f.read()):
                print("ONNX parse failed")
                for i in range(parser_trt.num_errors):
                    print(parser_trt.get_error(i))
                return
        engine = builder.build_engine(network, config)
        if engine is None:
            print("Failed to build engine")
            return
        out_path = p.with_suffix(".engine")
        with open(out_path, "wb") as f:
            f.write(engine.serialize())
        print(f"Saved engine to {out_path}")
    except ImportError:
        print("tensorrt not installed, cannot build engine manually")
    except Exception as ex:
        print(f"TensorRT build failed: {ex}")

if __name__ == "__main__":
    main()
