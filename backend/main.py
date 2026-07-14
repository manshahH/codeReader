import sys
sys.stderr.write('--- LOADING MAIN.PY ---\n')
try:
    from app.main import app
    __all__ = ['app']
except Exception as e:
    import traceback
    sys.stderr.write(f'IMPORT FAILED: {e}\n')
    traceback.print_exc(file=sys.stderr)
    raise
