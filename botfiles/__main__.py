"""Entry point for running the Media Scraper Bot package."""

import traceback

from .gui import main as run_gui


def _launch():
    try:
        run_gui()
    except Exception as exc:
        print("\n" + "=" * 60)
        print("ERROR: Failed to start Media Scraper Bot")
        print("=" * 60)
        print(f"\n{type(exc).__name__}: {exc}\n")
        print("Full error details:")
        traceback.print_exc()
        print("\n" + "=" * 60)
        print("\nPress Enter to close...")
        try:
            input()
        except EOFError:
            pass


if __name__ == "__main__":
    _launch()
