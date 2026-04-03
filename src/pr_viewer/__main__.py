import uvicorn

from pr_viewer.factory import create_app

app = create_app()


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8001)


if __name__ == "__main__":
    main()
