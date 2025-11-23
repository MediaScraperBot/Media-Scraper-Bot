"""
Media Scraper Bot - Main Entry Point
A comprehensive media scraper for Reddit, Twitter, and websites with GUI
"""
import sys
import traceback

if __name__ == '__main__':
    try:
        from botfiles.gui import main
        main()
    except Exception as e:
        print("\n" + "="*60)
        print("ERROR: Failed to start Media Scraper Bot")
        print("="*60)
        print(f"\n{type(e).__name__}: {str(e)}\n")
        print("Full error details:")
        traceback.print_exc()
        print("\n" + "="*60)
        print("\nPress Enter to close...")
        input()
