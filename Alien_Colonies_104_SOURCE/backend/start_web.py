"""Start the existing Alien Colonies world with its browser website."""
import sys

import run
from website import install_website


if __name__ == "__main__":
    local = any(arg == "--local-data" or arg.startswith("--local-data=") for arg in sys.argv[1:])
    install_website(hosted=not local, origin="" if local else None)
    raise SystemExit(run.main())
