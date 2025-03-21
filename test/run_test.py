#!/usr/bin/env python3
import sys
import os
import subprocess

def run_test():
    """Run the docs_crawler test script."""
    test_script = os.path.join(os.path.dirname(__file__), "test_docs_crawler.py")
    
    print("Running docs_crawler test...")
    result = subprocess.run([sys.executable, test_script], capture_output=True, text=True)
    
    # Print output
    print("\nTest output:")
    print(result.stdout)
    
    if result.stderr:
        print("\nErrors:")
        print(result.stderr)
    
    print(f"\nTest {'passed' if result.returncode == 0 else 'failed'} with exit code {result.returncode}")
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_test()) 