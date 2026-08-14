import os

import uvicorn

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8000"))


def main() -> None:
    print(f"Starting tournament dashboard at http://{HOST}:{PORT}")
    uvicorn.run("tournament.webapp.app:app", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
