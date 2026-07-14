from __future__ import annotations

from src.clean import clean
from src.targets import build_targets
from src.features import build_features
from src.train_severity import train as train_severity
from src.train_duration import train as train_duration
from src.after_action import run as after_action
from src.utils import log


def main() -> None:
    log("=== STAGE 1/6: clean ===")
    clean()
    log("=== STAGE 2/6: targets ===")
    build_targets()
    log("=== STAGE 3/6: features ===")
    build_features()
    log("=== STAGE 4/6: train severity classifier ===")
    train_severity()
    log("=== STAGE 5/6: train duration regressor ===")
    train_duration()
    log("=== STAGE 6/6: after-action review ===")
    after_action()
    log("=== DONE. Launch the demo with:  streamlit run app/demo.py ===")


if __name__ == "__main__":
    main()
