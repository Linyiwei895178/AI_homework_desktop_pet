from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _extract_speaker_embedding(converter, path: Path):
    try:
        return converter.extract_se(str(path))
    except TypeError:
        return converter.extract_se([str(path)])


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert TTS audio tone color with OpenVoice.")
    parser.add_argument("--repo-dir", required=True)
    parser.add_argument("--checkpoint-dir", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--tau", default="0.3")
    args = parser.parse_args()

    repo_dir = Path(args.repo_dir)
    checkpoint_dir = Path(args.checkpoint_dir)
    source = Path(args.source)
    reference = Path(args.reference)
    output = Path(args.output)
    sys.path.insert(0, str(repo_dir))

    import torch
    from openvoice.api import ToneColorConverter

    device = str(args.device or "auto").strip().lower()
    if device == "auto":
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    try:
        tau = float(args.tau)
    except ValueError:
        tau = 0.3

    config_path = checkpoint_dir / "converter" / "config.json"
    checkpoint_path = checkpoint_dir / "converter" / "checkpoint.pth"
    converter = ToneColorConverter(str(config_path), device=device, enable_watermark=False)
    converter.load_ckpt(str(checkpoint_path))

    source_se = _extract_speaker_embedding(converter, source)
    target_se = _extract_speaker_embedding(converter, reference)

    output.parent.mkdir(parents=True, exist_ok=True)
    converter.convert(
        audio_src_path=str(source),
        src_se=source_se,
        tgt_se=target_se,
        output_path=str(output),
        tau=tau,
        message="@AI_Desktop_Pet",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
