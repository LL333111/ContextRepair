from contextrepair.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["evaluate", *__import__("sys").argv[1:]]))

