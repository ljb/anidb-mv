from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
BUILD_LIB = ROOT / 'build' / 'lib'

sys.path[:] = [path for path in sys.path if Path(path).resolve() != BUILD_LIB]
sys.path.insert(0, str(SRC))
