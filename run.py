"""AI File Organizer 실행 스크립트"""

import uvicorn
from backend.config import load_config


def main():
    config = load_config()
    uvicorn.run(
        "backend.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
