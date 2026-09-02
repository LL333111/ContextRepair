from contextrepair.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["analyze", *__import__("sys").argv[1:]]))

