"""Frozen preset-only distribution capabilities; checked before any device action."""
import hashlib
import json
from pathlib import Path
from .paths import ROOT

ALLOWED = {'setup_all', 'usb_prepare', 'usb_stability', 'connect', 'driver_install',
           'direct_install_all', 'direct_verify', 'direct_resume_looks',
           'direct_resume_settings', 'review_failed_names'}
DISABLED = ('fl23', 'sound', 'vertical', 'plugin', 'vertical_persistent', 'portrait_frames')


def enabled():
    path = ROOT / 'preset-only.json'
    return path.is_file() and json.loads(path.read_text(encoding='utf-8')).get('schema') == 'a7c2-preset-only/1'


def options(value):
    if any(value.get(name) for name in DISABLED) or value.get('reset_slots') or value.get('preset_pack'):
        raise ValueError('本精简包只安装配套预制滤镜，不支持附加功能、转换或恢复操作。')
    if not value.get('looks'):
        raise ValueError('请明确选择本次安装的预制滤镜槽位。')
    result = dict(value, **{name: False for name in DISABLED}, _preset_only=True)
    return result


def validate(action, arguments):
    if action not in ALLOWED:
        raise ValueError('本精简包不支持此功能：' + action)
    if action == 'setup_all':
        workspace = Path(arguments['workspace'])
        saved = workspace / 'setup.private.json'
        if saved.is_file() and not json.loads(saved.read_text(encoding='utf-8')).get('options', {}).get('_preset_only'):
            raise ValueError('不迁移其他版本的未完成安装；请保留原事务及原运行包。')
        chosen = (json.loads(saved.read_text(encoding='utf-8'))['options'] if saved.is_file()
                  else arguments.get('options', {}))
        chosen = options(chosen)
        selected_presets(chosen)
        arguments = dict(arguments)
        if not saved.exists():
            arguments['options'] = chosen
    if action == 'direct_install_all':
        arguments = dict(arguments, options=options(arguments['options']))
        selected_presets(arguments['options'])
    if action in {'direct_verify', 'direct_resume_looks', 'direct_resume_settings', 'review_failed_names'}:
        path = Path(arguments.get('failed_workspace') or arguments['workspace']) / 'direct.private.json'
        value = json.loads(path.read_text(encoding='utf-8'))
        if value.get('mode') != 'install_all' or not value.get('bundle_options', {}).get('_preset_only'):
            raise ValueError('本精简包只能续接自身的预制滤镜事务；其他旧事务保留，不自动迁移或重放。')
        selected_presets(options(value['bundle_options']))
        if arguments.get('accepted'):
            raise ValueError('精简版通过向导单独记录实机检查，不发布 RAW 配置映射。')
    return arguments


def selected_presets(chosen):
    import sys
    root = Path(sys.executable).resolve().parent / 'Profiles'
    catalog = json.loads((root / 'catalog.json').read_text(encoding='utf-8'))
    allowed = {hashlib.sha256((root / row['a7look']).read_bytes()).hexdigest() for row in catalog['profiles']}
    seen = set()
    for look in chosen['looks']:
        slot = look.get('slot')
        if type(slot) is not int or slot not in range(1, 7) or slot in seen:
            raise ValueError('目标槽位必须为不重复的 1–6。')
        seen.add(slot)
        if hashlib.sha256(Path(look['path']).read_bytes()).hexdigest() not in allowed:
            raise ValueError('只允许安装随包提供的预制滤镜文件。')
