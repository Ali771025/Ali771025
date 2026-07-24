#!/usr/bin/env python3
"""
One-time downloader for small offline LLM GGUF models for pro-annotator LLM QA.

Supported:
- tinyllama-1.1b-chat GGUF
- phi-2 GGUF
- qwen2-0.5b GGUF

All models are small and CPU-friendly (0.5B - 1.1B). 100% offline after download.

Sources: HuggingFace via huggingface_hub or direct URLs.

Usage:
  python scripts/download_llm.py --model tinyllama
  python scripts/download_llm.py --model phi-2
  python scripts/download_llm.py --model qwen2-0.5b
  python scripts/download_llm.py --list
"""
import argparse
from pathlib import Path
import urllib.request
import os

# Map of friendly name -> HF repo + filename for GGUF
# We use TheBloke GGUF repos as they are popular and quantized
LLM_MODELS = {
    "tinyllama": {
        "repo": "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
        "filename": "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        "url": "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        "size": "0.6GB",
        "desc": "TinyLlama 1.1B Chat Q4_K_M - best for CPU, fast, good QA"
    },
    "tinyllama-1.1b": {
        "repo": "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
        "filename": "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        "url": "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        "size": "0.6GB",
        "desc": "TinyLlama 1.1B"
    },
    "phi-2": {
        "repo": "TheBloke/phi-2-GGUF",
        "filename": "phi-2.Q4_K_M.gguf",
        "url": "https://huggingface.co/TheBloke/phi-2-GGUF/resolve/main/phi-2.Q4_K_M.gguf",
        "size": "1.6GB",
        "desc": "Microsoft Phi-2 2.7B Q4 - stronger reasoning"
    },
    "phi-3-mini": {
        "repo": "microsoft/Phi-3-mini-4k-instruct-gguf",
        "filename": "Phi-3-mini-4k-instruct-q4.gguf",
        "url": "https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf",
        "size": "2.2GB",
        "desc": "Phi-3-mini 3.8B Q4 - best quality small LLM"
    },
    "qwen2-0.5b": {
        "repo": "Qwen/Qwen2-0.5B-Instruct-GGUF",
        "filename": "qwen2-0_5b-instruct-q4_0.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2-0.5B-Instruct-GGUF/resolve/main/qwen2-0_5b-instruct-q4_0.gguf",
        "size": "0.4GB",
        "desc": "Qwen2 0.5B Instruct Q4 - smallest, fastest, multilingual incl Persian"
    },
    "qwen2-1.5b": {
        "repo": "Qwen/Qwen2-1.5B-Instruct-GGUF",
        "filename": "qwen2-1_5b-instruct-q4_0.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2-1.5B-Instruct-GGUF/resolve/main/qwen2-1_5b-instruct-q4_0.gguf",
        "size": "1.0GB",
        "desc": "Qwen2 1.5B Q4 - good balance, Persian support"
    },
}

def download_with_progress(url: str, dest: Path):
    print(f"Downloading {url}\n -> {dest} (this may take a while, size up to few GB)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # try with huggingface_hub if available for resume
    try:
        from huggingface_hub import hf_hub_download
        # parse repo and filename
        # url format https://huggingface.co/<repo>/resolve/main/<filename>
        # we can fallback to urllib if fails
        pass
    except ImportError:
        pass

    try:
        # Use urllib with progress
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp, open(dest, 'wb') as out:
            total = resp.getheader('Content-Length')
            total = int(total) if total else None
            dl = 0
            last_print = 0
            while True:
                chunk = resp.read(1024*1024)  # 1MB
                if not chunk:
                    break
                out.write(chunk)
                dl += len(chunk)
                if total:
                    pct = dl/total*100
                    if dl - last_print > 10*1024*1024 or pct>=100:
                        print(f"\r{dl//1024//1024}MB / {total//1024//1024}MB {pct:.1f}%", end="")
                        last_print = dl
            print(f"\nSaved {dest} ({dl//1024//1024}MB)")
    except Exception as e:
        print(f"Direct download failed {e}, trying huggingface_hub...")
        try:
            from huggingface_hub import hf_hub_download
            # find model config
            for name, info in LLM_MODELS.items():
                if info["url"] == url:
                    repo = info["repo"]
                    filename = info["filename"]
                    # download to cache then move?
                    cached = hf_hub_download(repo_id=repo, filename=filename, local_dir=str(dest.parent), local_dir_use_symlinks=False)
                    # hf_hub_download returns path, ensure rename to dest
                    if Path(cached) != dest:
                        import shutil
                        shutil.move(cached, dest)
                    print(f"Downloaded via hf_hub to {dest}")
                    return
            raise e
        except Exception as e2:
            print(f"Failed to download {url}: {e2}")
            if dest.exists():
                dest.unlink()
            raise

def main():
    parser = argparse.ArgumentParser(description="Download small offline LLM GGUF for pro-annotator")
    parser.add_argument("--model", type=str, default="tinyllama", help="Model name: tinyllama, phi-2, phi-3-mini, qwen2-0.5b, qwen2-1.5b or comma list")
    parser.add_argument("--dest", type=str, default="models/llm", help="Destination folder")
    parser.add_argument("--list", action="store_true", help="List available models")
    args = parser.parse_args()

    if args.list:
        print("Available small offline LLM models (GGUF, CPU-friendly, Persian + English):")
        for name, info in LLM_MODELS.items():
            print(f"  {name:15} {info['size']:8} {info['desc']}")
            print(f"    {info['url']}")
        return

    dest_dir = Path(args.dest)
    dest_dir.mkdir(parents=True, exist_ok=True)

    models = [m.strip() for m in args.model.split(",") if m.strip()]
    for m in models:
        if m not in LLM_MODELS:
            print(f"Unknown model {m}, available: {list(LLM_MODELS.keys())}")
            continue
        info = LLM_MODELS[m]
        dest = dest_dir / info["filename"]
        if dest.exists():
            print(f"Exists, skipping {dest}")
            continue
        try:
            download_with_progress(info["url"], dest)
            # Create info json
            import json
            (dest_dir / f"{dest.stem}.json").write_text(json.dumps(info, indent=2))
        except Exception as e:
            print(f"Error downloading {m}: {e}. You can manually download from {info['url']} and place at {dest}")

    print("\nDone. LLM models ready for offline use.")
    print("Usage:")
    print("  python -m pro_annotator --project datasets/my_dataset --model models/yolov8n.onnx --llm-model models/llm/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf --llm-backend llama_cpp")

if __name__ == "__main__":
    main()
