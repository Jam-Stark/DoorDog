#!/usr/bin/env python3
"""Static v1.5.0 audit. This does NOT prove Codex effective config or hook loading."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import tomllib
from workflow_state import POLICY, role_config

MAIN_KEYS = ('model', 'model_reasoning_effort')

def forbidden_extensions(data, path='') -> list[str]:
    issues = []
    if isinstance(data, dict):
        for k, v in data.items():
            full = f'{path}.{k}' if path else k
            if k == 'use_history_notes_extension': issues.append('Pinned extension: ' + full)
            issues.extend(forbidden_extensions(v, full))
    elif isinstance(data, list):
        for i, v in enumerate(data): issues.extend(forbidden_extensions(v, f'{path}[{i}]'))
    return issues

def audit(root: Path, schema: Path | None = None) -> dict:
    issues: list[str] = []; roles = []
    try:
        cfg = tomllib.loads((root / '.codex/config.toml').read_text())
        for k in MAIN_KEYS:
            if k in cfg: issues.append('Main project override: ' + k)
        for name, profile in cfg.get('profiles', {}).items():
            for k in MAIN_KEYS:
                if k in profile: issues.append(f'Main profile override: {name}.{k}')
        for key, expected in (('model_context_window', 516000), ('model_auto_compact_token_limit', 464400), ('model_auto_compact_token_limit_scope', 'total')):
            if cfg.get(key) != expected: issues.append('Owner Main context setting changed: ' + key)
        issues.extend(forbidden_extensions(cfg))
        if cfg.get('agents', {}).get('default_subagent_model') != 'gpt-6-sol': issues.append('Default child is not GPT-6 Sol.')
        if cfg.get('agents', {}).get('default_subagent_reasoning_effort') != 'medium': issues.append('Wrong default child effort.')
        if cfg.get('agents', {}).get('max_concurrent_threads_per_session') != 5: issues.append('Child concurrency must remain 5 (Owner override).')
        if cfg.get('features', {}).get('hooks') is not True: issues.append('Native hooks feature not requested.')
        if cfg.get('features', {}).get('context_management', {}).get('experimental_mode') is not True: issues.append('Main experimental context capability gate missing.')
        if 'token_budget' in cfg.get('features', {}): issues.append('Main token_budget must remain model-owned, not project-pinned.')
        if cfg.get('background_terminal_max_timeout', 0) < 36000000: issues.append('Ten-hour native wait upper bound not configured.')
        astra_roles = []
        for p in sorted((root / '.codex/agents').glob('*.toml')):
            d = tomllib.loads(p.read_text()); name = d.get('name')
            try: role_config(root, name)
            except ValueError as exc: issues.append(f'{p.name}: {exc}')
            issues.extend(forbidden_extensions(d, p.name))
            if d.get('model') == 'gpt-6-astra': astra_roles.append(name)
            roles.append({k: d.get(k) for k in ('name', 'model', 'model_reasoning_effort', 'model_context_window', 'model_auto_compact_token_limit')})
            expected_ref = 'agents/' + p.name
            if cfg.get('agents', {}).get(name, {}).get('config_file') != expected_ref:
                issues.append('Role is not explicitly registered: ' + str(name))
        if astra_roles != ['deep_researcher']: issues.append('Only deep_researcher may configure Astra, exactly once.')
        names = {r['name'] for r in roles}
        for name in ('default', 'worker', 'explorer', 'deep_researcher'):
            if name not in names: issues.append('Missing role: ' + name)
        hooks = json.loads((root / '.codex/hooks.json').read_text())
        for event in ('PreToolUse', 'PostToolUse', 'SessionStart', 'PostCompact'):
            groups = hooks.get('hooks', {}).get(event, [])
            if not any('codex_v150_hook.py' in str(h.get('command', '')) for g in groups for h in g.get('hooks', [])):
                issues.append('Missing v1.5.0 hook: ' + event)
        for f in ('.ai/ROLE_VERSION', '.codex/MODEL_TEAM_VERSION'):
            if (root/f).read_text().strip() != '1.5.0': issues.append('Wrong version: ' + f)
        if schema:
            declared = json.loads(schema.read_text()).get('properties', {})
            for key in ('background_terminal_max_timeout', 'agents', 'features'):
                if key not in declared: issues.append('Provided schema lacks: ' + key)
    except (OSError, ValueError, TypeError) as exc:
        issues.append(str(exc))
    return {'project_config': 'STATIC_PASS' if not issues else 'FAIL', 'issues': issues, 'roles': roles,
            'native_hook_interception': 'UNVERIFIED', 'effective_child_config': 'UNVERIFIED',
            'native_turn_delivery': 'UNVERIFIED', 'queue_cross_machine': 'DISABLED_UNVERIFIED',
            'model_switching_notes_compact': 'UNVERIFIED', 'billing_hard_cap': 'NOT_PROVIDED',
            'process_cleanup': 'OPT_IN_LINUX_OWNED_TOOLS_ONLY'}

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path('.')); p.add_argument('--schema', type=Path)
    p.add_argument('--probe-version', action='store_true'); a = p.parse_args()
    result = audit(a.root.resolve(), a.schema)
    if a.probe_version:
        try:
            v = subprocess.run(['codex', '--version'], capture_output=True, text=True, timeout=5)
            result['codex_version'] = {'exit': v.returncode, 'stdout': v.stdout.strip(), 'stderr': v.stderr.strip()}
        except (OSError, subprocess.SubprocessError) as exc:
            result['codex_version'] = {'error': str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['project_config'] == 'STATIC_PASS' else 2
if __name__ == '__main__':
    raise SystemExit(main())
