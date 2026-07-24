from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import os

from ..core.annotation import ImageAnnotations, AnnotationObject
from ..core.validators import LabelValidator, ValidationIssue

class LLMBackend(str, Enum):
    AUTO = "auto"
    LLAMA_CPP = "llama_cpp"
    TRANSFORMERS = "transformers"
    ONNX = "onnx"
    DUMMY = "dummy"

@dataclass
class Suggestion:
    type: str  # fix, merge, rename, delete, review
    message: str
    object_id: Optional[str] = None
    action: Optional[Dict[str,Any]] = None

@dataclass
class AnalysisResult:
    image_path: str = ""
    issues: List[ValidationIssue] = field(default_factory=list)
    suggestions: List[Suggestion] = field(default_factory=list)
    description: str = ""
    llm_raw: str = ""
    qa_score: float = 0.0  # 0-1, 1 perfect
    analyzed_at: float = field(default_factory=lambda: time.time())

    def to_dict(self):
        return {
            "image_path": self.image_path,
            "issues": [i.to_dict() if hasattr(i,'to_dict') else i.__dict__ for i in self.issues],
            "suggestions": [s.__dict__ for s in self.suggestions],
            "description": self.description,
            "qa_score": self.qa_score,
        }

@dataclass
class DatasetReport:
    total_images: int = 0
    total_objects: int = 0
    class_distribution: Dict[str,int] = field(default_factory=dict)
    issues_summary: Dict[str,int] = field(default_factory=dict)
    suggestions: List[Suggestion] = field(default_factory=list)
    description: str = ""
    llm_raw: str = ""
    stats: Dict[str,Any] = field(default_factory=dict)

class LLMAnalyzer:
    """
    Professional offline LLM analyzer for label QA and management.
    
    Backends:
    - llama_cpp : GGUF models (TinyLlama 1.1B Chat, Phi-3-mini GGUF, Qwen2-0.5B) via llama-cpp-python, best for CPU offline
    - transformers : HuggingFace local folder (model + tokenizer) via transformers pipeline, offline with local_files_only=True
    - onnx : ONNX Runtime LLM via optimum, stub for now
    - dummy : always available, heuristic rules + templated descriptions, no AI model needed

    All 100% offline. No internet at runtime.
    Model path can be:
      - GGUF file: models/llm/tinyllama-1.1b-chat.gguf
      - HF folder: models/llm/TinyLlama-1.1B-Chat-v1.0/ (contains config.json, tokenizer.json etc)
      - ONNX folder: models/llm/phi-3-mini-onnx/
    """

    def __init__(self,
                 model_path: Optional[str] = None,
                 backend: str = "auto",
                 device: str = "cpu",
                 max_tokens: int = 512,
                 temperature: float = 0.2,
                 system_prompt: str = None):
        self.model_path = model_path
        self.backend = LLMBackend(backend) if isinstance(backend, str) else backend
        self.device = device
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.system_prompt = system_prompt or "You are a professional dataset QA assistant for object detection labeling. Analyze labels and give concise, actionable feedback in JSON."
        self.validator = LabelValidator()
        self._llama_model = None
        self._transformers_pipe = None
        self._onnx_session = None
        self.loaded = False
        self.backend_used = LLMBackend.DUMMY

    def load(self) -> bool:
        """
        Try to load LLM according to backend preference.
        If fails, fallback to DUMMY.
        """
        if not self.model_path:
            print("[LLM] No model path, using DUMMY heuristic")
            self.backend_used = LLMBackend.DUMMY
            self.loaded = True
            return True

        path = Path(self.model_path)
        if not path.exists():
            print(f"[LLM] Model not found {self.model_path}, using DUMMY")
            self.backend_used = LLMBackend.DUMMY
            self.loaded = True
            return True

        # AUTO detection
        requested = self.backend
        if requested == LLMBackend.AUTO:
            if path.suffix == ".gguf":
                requested = LLMBackend.LLAMA_CPP
            elif path.is_dir() and (path / "config.json").exists():
                # HF folder -> try transformers first, then onnx
                if (path / "model.onnx").exists() or (path / "decoder_model.onnx").exists():
                    requested = LLMBackend.ONNX
                else:
                    requested = LLMBackend.TRANSFORMERS
            elif path.suffix == ".onnx":
                requested = LLMBackend.ONNX
            else:
                requested = LLMBackend.DUMMY

        # Try each backend in order of preference if AUTO, else only requested
        backends_to_try = []
        if self.backend == LLMBackend.AUTO:
            if requested == LLMBackend.LLAMA_CPP:
                backends_to_try = [LLMBackend.LLAMA_CPP, LLMBackend.TRANSFORMERS, LLMBackend.ONNX, LLMBackend.DUMMY]
            elif requested == LLMBackend.TRANSFORMERS:
                backends_to_try = [LLMBackend.TRANSFORMERS, LLMBackend.LLAMA_CPP, LLMBackend.ONNX, LLMBackend.DUMMY]
            elif requested == LLMBackend.ONNX:
                backends_to_try = [LLMBackend.ONNX, LLMBackend.TRANSFORMERS, LLMBackend.LLAMA_CPP, LLMBackend.DUMMY]
            else:
                backends_to_try = [LLMBackend.DUMMY]
        else:
            backends_to_try = [requested, LLMBackend.DUMMY]

        for be in backends_to_try:
            try:
                if be == LLMBackend.LLAMA_CPP:
                    if self._load_llama_cpp():
                        self.backend_used = be
                        self.loaded = True
                        print(f"[LLM] Loaded llama_cpp backend {self.model_path}")
                        return True
                elif be == LLMBackend.TRANSFORMERS:
                    if self._load_transformers():
                        self.backend_used = be
                        self.loaded = True
                        print(f"[LLM] Loaded transformers backend {self.model_path}")
                        return True
                elif be == LLMBackend.ONNX:
                    if self._load_onnx():
                        self.backend_used = be
                        self.loaded = True
                        print(f"[LLM] Loaded ONNX backend {self.model_path}")
                        return True
                elif be == LLMBackend.DUMMY:
                    self.backend_used = LLMBackend.DUMMY
                    self.loaded = True
                    print("[LLM] Using DUMMY backend (heuristic rules)")
                    return True
            except Exception as e:
                print(f"[LLM] Backend {be} load failed: {e}")
                continue

        self.backend_used = LLMBackend.DUMMY
        self.loaded = True
        return True

    def _load_llama_cpp(self) -> bool:
        try:
            from llama_cpp import Llama
        except ImportError:
            print("[LLM] llama-cpp-python not installed. pip install llama-cpp-python")
            return False
        # Load GGUF
        self._llama_model = Llama(
            model_path=str(self.model_path),
            n_ctx=2048,
            n_threads=os.cpu_count() or 4,
            verbose=False,
        )
        return True

    def _load_transformers(self) -> bool:
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
            import torch
        except ImportError:
            print("[LLM] transformers not installed. pip install transformers accelerate torch")
            return False
        try:
            model_path = str(self.model_path)
            tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True, trust_remote_code=True, device_map="auto" if self.device.startswith("cuda") else "cpu", torch_dtype="auto")
            self._transformers_pipe = pipeline("text-generation", model=model, tokenizer=tokenizer, max_new_tokens=self.max_tokens, temperature=self.temperature, do_sample=self.temperature>0)
            return True
        except Exception as e:
            print(f"[LLM] transformers load failed local: {e}")
            return False

    def _load_onnx(self) -> bool:
        try:
            import onnxruntime as ort
        except ImportError:
            print("[LLM] onnxruntime not installed")
            return False
        # ONNX LLM loading is complex (needs tokenizer + decoder). For professional annotator we provide stub
        # Real implementation would use optimum.onnxruntime
        try:
            from optimum.onnxruntime import ORTModelForCausalLM
            from transformers import AutoTokenizer
            model_path = str(self.model_path)
            # if file is .onnx, folder is parent
            if Path(model_path).is_file():
                model_path = str(Path(model_path).parent)
            tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
            model = ORTModelForCausalLM.from_pretrained(model_path, local_files_only=True)
            # store
            self._onnx_tokenizer = tokenizer
            self._onnx_model = model
            return True
        except Exception as e:
            print(f"[LLM] ONNX load failed (need optimum): {e}")
            # fallback to dummy for now
            return False

    def _call_llm(self, prompt: str) -> str:
        """Call loaded LLM backend"""
        if self.backend_used == LLMBackend.LLAMA_CPP and self._llama_model:
            try:
                out = self._llama_model.create_chat_completion(
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
                return out["choices"][0]["message"]["content"]
            except Exception as e:
                # try completion mode
                try:
                    out = self._llama_model.create_completion(prompt=f"{self.system_prompt}\n\nUser: {prompt}\nAssistant:", max_tokens=self.max_tokens, temperature=self.temperature)
                    return out["choices"][0]["text"]
                except Exception as e2:
                    return f"[LLM llama_cpp error] {e} / {e2}"

        elif self.backend_used == LLMBackend.TRANSFORMERS and self._transformers_pipe:
            try:
                full_prompt = f"{self.system_prompt}\n\nUser: {prompt}\nAssistant:"
                out = self._transformers_pipe(full_prompt)
                text = out[0]["generated_text"]
                # remove prompt
                if full_prompt in text:
                    text = text[len(full_prompt):]
                return text.strip()
            except Exception as e:
                return f"[LLM transformers error] {e}"

        elif self.backend_used == LLMBackend.ONNX:
            try:
                # stub onnx generation
                return "[LLM ONNX stub] Dataset looks good. Issues: none."
            except Exception as e:
                return f"[LLM ONNX error] {e}"

        else:
            # DUMMY: return heuristic templated analysis, not real LLM
            return ""

    def analyze_image_labels(self, ann: ImageAnnotations, class_names: List[str] = None) -> AnalysisResult:
        """
        Analyze single image labels.
        Steps:
        1. Heuristic validator
        2. Build prompt for LLM (if backend not dummy)
        3. Combine into AnalysisResult
        """
        issues = self.validator.validate_image(ann)

        # Heuristic suggestions from issues
        suggestions: List[Suggestion] = []
        for iss in issues:
            if iss.type == "duplicate":
                suggestions.append(Suggestion(type="delete", message=f"Duplicate box detected: {iss.message}", object_id=iss.object_id, action={"delete_id": iss.details.get("other_id")} if iss.details else None))
            elif iss.type == "tiny":
                suggestions.append(Suggestion(type="review", message=f"Tiny box review: {iss.message}", object_id=iss.object_id))
            elif iss.type == "out_of_bounds":
                suggestions.append(Suggestion(type="fix", message=f"Clip box to image bounds: {iss.message}", object_id=iss.object_id, action={"clip": True}))
            elif iss.type == "low_conf":
                suggestions.append(Suggestion(type="review", message=f"Low conf AI box: {iss.message}", object_id=iss.object_id, action={"threshold": self.validator.min_conf}))

        # QA score
        qa_score = 1.0
        # penalize per issue
        for iss in issues:
            if iss.severity == "error":
                qa_score -= 0.2
            elif iss.severity == "warning":
                qa_score -= 0.1
            else:
                qa_score -= 0.05
        qa_score = max(0.0, min(1.0, qa_score))

        # Build LLM prompt
        llm_description = ""
        llm_raw = ""
        if self.backend_used != LLMBackend.DUMMY and self.loaded:
            # Build JSON context
            context = {
                "image": ann.image_path,
                "width": ann.width,
                "height": ann.height,
                "objects": [{"class": o.class_name, "class_id": o.class_id, "bbox": list(o.bbox_xyxy), "conf": o.confidence, "is_ai": o.is_ai, "area": o.area} for o in ann.objects if o.visible],
                "issues_found": [i.to_dict() for i in issues],
            }
            prompt = f"""
Analyze this object detection annotation:

Image: {ann.image_path} ({ann.width}x{ann.height})
Labels: {json.dumps(context['objects'], ensure_ascii=False)}
Heuristic issues: {json.dumps(context['issues_found'], ensure_ascii=False)}

Tasks:
1. Is there any obvious labeling error? (duplicate, tiny, wrong class likely?)
2. Suggest fixes in JSON format.
3. Give short description: "This image contains X persons and Y cars..."

Respond in JSON with keys: description, qa_score (0-1), suggestions (list of {{type, message}}), corrected_classes if any.

Keep response concise and in same language as user query (if user wrote Persian, answer Persian, else English).
"""
            llm_raw = self._call_llm(prompt)
            # Try parse JSON from LLM
            try:
                # extract json block if present
                import re
                json_match = re.search(r"\{.*\}", llm_raw, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0))
                    llm_description = parsed.get("description", llm_raw[:500])
                    # parse suggestions from LLM
                    for sug in parsed.get("suggestions", []):
                        if isinstance(sug, dict):
                            suggestions.append(Suggestion(type=sug.get("type","review"), message=sug.get("message",""), object_id=sug.get("object_id"), action=sug.get("action")))
                    if "qa_score" in parsed:
                        try:
                            qa_score = float(parsed["qa_score"])
                        except:
                            pass
                else:
                    llm_description = llm_raw[:500]
            except Exception:
                llm_description = llm_raw[:500]
        else:
            # DUMMY heuristic description
            counts = {}
            for o in ann.objects:
                if not o.visible:
                    continue
                counts[o.class_name] = counts.get(o.class_name, 0) + 1
            if counts:
                parts = [f"{v} {k}" for k,v in counts.items()]
                llm_description = f"This image contains {', '.join(parts)}. " + (f"Found {len(issues)} issue(s)." if issues else "No obvious issues found.")
            else:
                llm_description = "No objects labeled in this image."
            llm_raw = llm_description

        result = AnalysisResult(
            image_path=ann.image_path,
            issues=issues,
            suggestions=suggestions,
            description=llm_description,
            llm_raw=llm_raw,
            qa_score=qa_score
        )
        # store in annotation
        ann.llm_analysis = result.to_dict()
        return result

    def analyze_dataset(self, images: List[ImageInfo], class_names: List[str] = None) -> DatasetReport:
        """
        Dataset level analysis with LLM.
        """
        from collections import Counter
        total_images = len(images)
        total_objects = sum(len(img.annotations.objects) for img in images)
        class_counter = Counter()
        for img in images:
            class_counter.update([o.class_name for o in img.annotations.objects if o.visible])

        val_report = self.validator.validate_dataset([img.annotations for img in images], class_names or list(class_counter.keys()))

        issues_summary = Counter()
        for iss in val_report.get("issues", []):
            issues_summary[iss.get("type","unknown")] += 1

        suggestions: List[Suggestion] = []
        # imbalance suggestions
        for cname, warn in val_report.get("imbalance_warnings", {}).items():
            suggestions.append(Suggestion(type="review", message=f"Class imbalance: {cname} - {warn}"))

        # duplicate check from validator
        if issues_summary.get("duplicate",0) > 0:
            suggestions.append(Suggestion(type="fix", message=f"Found {issues_summary['duplicate']} duplicate boxes across dataset, consider deduplication"))

        llm_description = ""
        llm_raw = ""
        if self.backend_used != LLMBackend.DUMMY and self.loaded:
            prompt = f"""
You are dataset QA for object detection.

Dataset stats:
- Images: {total_images}
- Objects: {total_objects}
- Class distribution: {dict(class_counter)}
- Total issues: {val_report.get('total_issues',0)}
- Issues breakdown: {dict(issues_summary)}
- Size summary: {val_report.get('size_summary',{})}

Tasks:
1. Give short dataset health summary.
2. Suggest class merging or renaming if some classes have low samples or similar names.
3. Suggest next actions for improving dataset quality.
4. Respond JSON with keys: description, suggestions (list), qa_score, class_mapping (if renaming needed).

Be concise, professional.
"""
            llm_raw = self._call_llm(prompt)
            try:
                import re
                json_match = re.search(r"\{.*\}", llm_raw, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0))
                    llm_description = parsed.get("description", llm_raw[:800])
                    for sug in parsed.get("suggestions", []):
                        if isinstance(sug, dict):
                            suggestions.append(Suggestion(type=sug.get("type","review"), message=sug.get("message","")))
                else:
                    llm_description = llm_raw[:800]
            except Exception:
                llm_description = llm_raw[:800]
        else:
            # dummy
            if class_counter:
                most = class_counter.most_common(1)[0]
                least = class_counter.most_common()[-1]
                llm_description = f"Dataset has {total_images} images, {total_objects} objects. Most common class: {most[0]} ({most[1]}), least: {least[0]} ({least[1]}). {val_report.get('total_issues',0)} issues found."
            else:
                llm_description = f"Dataset empty? {total_images} images, {total_objects} objects."

        return DatasetReport(
            total_images=total_images,
            total_objects=total_objects,
            class_distribution=dict(class_counter),
            issues_summary=dict(issues_summary),
            suggestions=suggestions,
            description=llm_description,
            llm_raw=llm_raw,
            stats=val_report
        )

    def query_dataset(self, question: str, images: List[ImageInfo]) -> str:
        """
        Natural language query over dataset.
        Example: "عکس‌هایی که بیش از 3 ماشین دارند"
        For DUMMY backend, we parse simple patterns.
        For LLM backend, we feed stats + question to LLM.
        """
        if self.backend_used == LLMBackend.DUMMY:
            # simple heuristic query parser (Persian + English)
            q = question.lower()
            # examples: "more than 3 cars" etc
            import re
            # extract number and class
            # فارسی: "بیش از 3 ماشین" - we need mapping of Persian class names? For now support English
            # Try to find class name mentioned
            all_classes = set()
            for img in images:
                for o in img.annotations.objects:
                    all_classes.add(o.class_name.lower())

            # find class in question
            found_class = None
            for c in all_classes:
                if c in q:
                    found_class = c
                    break

            # find number
            m = re.search(r"(\d+)", q)
            num = int(m.group(1)) if m else None

            if "more than" in q or "بیش از" in q or "بیشتر از" in q:
                if found_class and num:
                    result = []
                    for img in images:
                        cnt = sum(1 for o in img.annotations.objects if o.class_name.lower() == found_class)
                        if cnt > num:
                            result.append(img.path)
                    return f"Found {len(result)} images with more than {num} {found_class}: {result[:10]}"
            if "without" in q or "بدون" in q:
                if found_class:
                    result = [img.path for img in images if not any(o.class_name.lower()==found_class for o in img.annotations.objects)]
                    return f"Found {len(result)} images without {found_class}: {result[:10]}"
            if "with" in q or "با" in q:
                if found_class:
                    result = [img.path for img in images if any(o.class_name.lower()==found_class for o in img.annotations.objects)]
                    return f"Found {len(result)} images with {found_class}: {result[:10]}"
            # fallback list all
            return f"Dataset has {len(images)} images. Classes: {all_classes}. Question: {question} - try 'images with more than 3 car' or 'images without person'"

        else:
            # LLM backend
            stats = self.analyze_dataset(images)
            prompt = f"""
Dataset: {stats.total_images} images, distribution {stats.class_distribution}
User question: {question}
Answer concisely, list image paths if relevant. If Persian question, answer Persian.
"""
            return self._call_llm(prompt)

    def suggest_class_mapping(self, current_classes: List[str], intent: str) -> Dict[str,str]:
        """
        Suggest class renaming/merging based on intent.
        Eg intent: "I want to merge car and truck into vehicle"
        """
        if self.backend_used == LLMBackend.DUMMY:
            # simple heuristic: if intent contains "merge" and lists classes, map them
            mapping = {}
            # naive: if intent says "merge X and Y into Z", parse
            import re
            m = re.search(r"merge (.+) into (.+)", intent, re.IGNORECASE)
            if m:
                sources = [s.strip() for s in re.split(r",|and", m.group(1))]
                target = m.group(2).strip()
                for s in sources:
                    if s in current_classes:
                        mapping[s] = target
            return mapping
        else:
            prompt = f"""
Current classes: {current_classes}
User intent: {intent}
Task: suggest mapping from old class names to new class names as JSON {{old: new}}.
Only include classes that need change.
"""
            raw = self._call_llm(prompt)
            try:
                import re, json
                jmatch = re.search(r"\{.*\}", raw, re.DOTALL)
                if jmatch:
                    return json.loads(jmatch.group(0))
            except Exception:
                pass
            return {}

# Helper function for easy usage
def create_analyzer(model_path: Optional[str] = None, backend: str = "auto", device: str = "cpu") -> LLMAnalyzer:
    analyzer = LLMAnalyzer(model_path=model_path, backend=backend, device=device)
    analyzer.load()
    return analyzer
