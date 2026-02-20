import os
import sys

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "win-x64"
    filename = "pict.exe" if "win" in target else "pict"
    path = os.path.join("vendor", "pict", target, filename)
    if not os.path.exists(path):
        print(f"Vendor binary missing: {path}")
        sys.exit(1)
    print(f"Vendor binary ok: {path}")
    sys.exit(0)

if __name__ == "__main__":
    main()
