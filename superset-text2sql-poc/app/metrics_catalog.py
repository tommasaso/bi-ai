import yaml
from pathlib import Path


def load_metrics_catalog() -> dict:
    catalog_path = Path(__file__).parent.parent / "data" / "metrics_catalog.yaml"
    with open(catalog_path, "r") as f:
        data = yaml.safe_load(f)
    return data.get("metrics", {})


def build_metrics_context(metrics: dict) -> str:
    lines = ["## Certified Metrics\n"]
    for metric_name, info in metrics.items():
        lines.append(f"### `{metric_name}`")
        lines.append(f"Description: {info['description']}")
        lines.append(f"Formula: `{info['formula']}`")
        lines.append(f"Preferred dataset: `{info['preferred_dataset']}`")
        dims = ", ".join(f"`{d}`" for d in info.get("supported_dimensions", []))
        lines.append(f"Supported dimensions: {dims}")
        lines.append("")
    return "\n".join(lines)
