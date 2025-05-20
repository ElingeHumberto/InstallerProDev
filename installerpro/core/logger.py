import logging, pathlib

_logfile = pathlib.Path.cwd() / "logs" / "installerpro.log"
_logfile.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)8s | %(message)s",
    handlers=[
        logging.FileHandler(_logfile, encoding="utf-8"),
        logging.StreamHandler()
    ],
)

log = logging.getLogger("InstallerPro")
