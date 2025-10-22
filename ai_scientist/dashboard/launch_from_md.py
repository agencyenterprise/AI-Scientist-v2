import argparse
import sys
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workshop-file", required=True, help="Path to workshop description file (.md) or research paper (.pdf)")
    p.add_argument("--writeup-type", default="icbinb")
    p.add_argument("--attempt_id", type=int, default=0)
    p.add_argument("--model_writeup", default="o1-preview-2024-09-12")
    p.add_argument("--model_citation", default="gpt-4o-2024-11-20")
    p.add_argument("--model_review", default="gpt-4o-2024-11-20")
    p.add_argument("--model_agg_plots", default="o3-mini-2025-01-31")
    p.add_argument("--num_cite_rounds", type=int, default=20)
    p.add_argument("--add_dataset_ref", action="store_true")
    p.add_argument("--load_code", action="store_true")
    args = p.parse_args()

    workshop_path = Path(args.workshop_file).resolve()
    if not workshop_path.exists():
        print(f"Workshop file not found: {workshop_path}")
        sys.exit(1)

    # Run ideation to produce .json if not present
    json_path = workshop_path.with_suffix(".json")
    if not json_path.exists():
        cmd_ideation = [
            sys.executable,
            str(ROOT / "ai_scientist" / "perform_ideation_temp_free.py"),
            "--workshop-file",
            str(workshop_path),
            "--model",
            "gpt-4o-2024-05-13",
            "--max-num-generations",
            "1",
            "--num-reflections",
            "2",
        ]
        subprocess.run(cmd_ideation, cwd=str(ROOT), check=False)

    # Launch the main pipeline
    cmd_launch = [
        sys.executable,
        str(ROOT / "launch_scientist_bfts.py"),
        "--load_ideas",
        str(json_path),
        "--writeup-type",
        args.writeup_type,
        "--attempt_id",
        str(args.attempt_id),
        "--model_writeup",
        args.model_writeup,
        "--model_citation",
        args.model_citation,
        "--model_review",
        args.model_review,
        "--model_agg_plots",
        args.model_agg_plots,
        "--num_cite_rounds",
        str(args.num_cite_rounds),
    ]
    if args.add_dataset_ref:
        cmd_launch.append("--add_dataset_ref")
    if args.load_code:
        cmd_launch.append("--load_code")

    subprocess.Popen(cmd_launch, cwd=str(ROOT))


if __name__ == "__main__":
    main()


