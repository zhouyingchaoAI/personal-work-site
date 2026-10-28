"""Compatibility boundary for the joint-command subproject."""
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1] / 'ai-office-assistant-web' / 'packages' / 'joint-command'


def load_module(name, namespace):
    if Path(name).name != name or not name.startswith('crm') or not name.endswith('.py'):
        raise ValueError('Invalid joint-command module')
    source = PROJECT_ROOT / 'backend' / name
    exec(compile(source.read_text(encoding='utf-8'), str(source), 'exec'), namespace)
