import os

import uvicorn


def main() -> None:
    port = int(os.getenv("API_SERVER_PORT", "8010"))
    uvicorn.run("fin_compliance.app.api:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
