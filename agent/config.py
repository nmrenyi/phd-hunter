from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
CV_PATH = ROOT_DIR / "cv" / "cv.md"
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "checkpoint.db"
REPORT_PATH = DATA_DIR / "report.md"

LLM_MODEL = "qwen3.5:9b"
LLM_TEMPERATURE = 0.0
LLM_NUM_CTX = 32768
LLM_NUM_PREDICT = 4096  # must cover thinking tokens + response; 1024 was too small for Qwen3
MATCH_THRESHOLD = 4  # out of 5

REQUEST_DELAY = 1.0  # seconds between requests to the same domain
MAX_HTML_CHARS = 20000  # truncate cleaned HTML before sending to LLM
