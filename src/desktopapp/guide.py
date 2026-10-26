"""Persistent conversational frontend for the existing Windows worker.

Status, planning and answers are local operations. Only start launches a worker;
poll consumes its terminal evidence after its process has returned. An abandoned
worker is never killed or replayed. Camera writes remain in the existing engine.
"""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import zipfile

from .paths import ROOT, data_root, write_json
from .reloadguide import STEPS

SCHEMA = 'a7c2-ai-guide/1'
DEFAULTS = ('Classic Neg.', 'Classic Chrome', 'Nostalgic Neg.', 'Velvia', 'GR Positive Film', 'GR Negative Film')
EXTRAS = ('fl23', 'sound', 'vertical', 'plugin')
SONY = 'https://www.sony.com/electronics/support/e-mount-body-ilce-7-series/ilce-7cm2/software/00301105'
SAFE_DIRECT = {'LOADED', 'COMPLETE', 'SUPERSEDED'}


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def lock(path):
    # This module does not import or enumerate a USB backend.
    sys.path.insert(0, str(ROOT / 'src/looks'))
    from looktool.devicelock import DeviceLock
    return DeviceLock(path)


def history(roots, exclude=None):
    """Inspect configured work locations only, never open backups or firmware."""
    from .lookbatch import read_only_failure
    rows, seen = [], set()
    for root in roots:
        root = Path(root).resolve()
        if not root.is_dir():
            continue
        accounted = set()
        # Completed setup parents retain failed children as evidence. A verified
        # descendant can account for its explicitly recorded resource checkpoint.
        for path in root.rglob('setup.private.json'):
            try:
                setup = read(path)
                if setup.get('phase') != 'COMPLETE' or setup.get('verify_result', {}).get('phase') not in {'LOADED', 'COMPLETE'}:
                    continue
                final = Path(setup['install_workspace']).resolve()
                if path.parent not in final.parents or Path(setup['verify_result']['workspace']).resolve() != final:
                    continue
                loaded = read(final / 'direct.private.json')
                if loaded.get('phase') not in {'LOADED', 'COMPLETE'}:
                    continue
                for item in [setup.get('resume_resource_from'), *setup.get('failed_install_workspaces', [])]:
                    if not item:
                        continue
                    prior = Path(item).resolve()
                    if path.parent not in prior.parents:
                        continue
                    old = read(prior / 'direct.private.json')
                    old_id, new_id = old.get('identity', {}), loaded.get('identity', {})
                    keys = [k for k in ('usb_serial_sha256', 'serial_sha256') if old_id.get(k) and new_id.get(k)]
                    same = bool(keys) and all(old_id[k] == new_id[k] for k in keys)
                    if same and old.get('mode') == loaded.get('mode') == 'install_all':
                        accounted.add(prior)
            except (OSError, ValueError, KeyError, TypeError):
                continue
        for filename in ('direct.private.json', 'setup.private.json', 'guide.private.json'):
            for path in root.rglob(filename):
                if path in seen or (exclude and Path(exclude).resolve() in path.parents):
                    continue
                seen.add(path)
                try:
                    value = read(path)
                    phase = value['phase']
                    known_prewrite = (value.get('schema') == 'a7c2-direct-job/1'
                                      and isinstance(value.get('journal'), list) and read_only_failure(value))
                    if filename.startswith('direct') and (path.parent in accounted or known_prewrite):
                        continue
                    if filename.startswith('guide') and phase not in {
                            'RUNNING', 'WAIT_RELOAD', 'WAIT_RESOURCE_RELOAD', 'READY_CONTINUE',
                            'NEEDS_REVIEW', 'PHYSICAL_CHECKS'}:
                        continue
                    finished = SAFE_DIRECT if filename.startswith('direct') else {'COMPLETE'}
                    if phase in finished:
                        continue
                    rows.append(dict(workspace=str(path.parent), kind=filename.split('.')[0],
                                     phase=phase, mode=value.get('mode')))
                except (OSError, ValueError, KeyError, TypeError):
                    rows.append(dict(workspace=str(path.parent), kind='unreadable', phase='UNKNOWN'))
    return rows


def assets(library, selection):
    """Validate the entire chosen plan offline, before any worker is launched."""
    sys.path.insert(0, str(ROOT / 'src/looks'))
    from looktool import lookfile
    library = Path(library).resolve()
    catalog = read(library / 'catalog.json')
    if catalog.get('schema') != 'a7c2-profile-library/1':
        raise ValueError('请选择完整 Profiles 配对库，catalog.json 格式不支持。')
    index = {row['name']: row for row in catalog['profiles']}
    result, seen = [], set()
    for selected in selection:
        slot, name = selected['slot'], selected['profile']
        if type(slot) is not int or slot not in range(1, 7) or slot in seen:
            raise ValueError('目标槽位必须为不重复的 1–6。')
        seen.add(slot)
        if name not in index:
            raise ValueError('配对库中没有外观：' + str(name))
        entry = index[name]
        path = (library / entry['a7look']).resolve()
        if library not in path.parents:
            raise ValueError('外观路径超出配对库。')
        document = lookfile.read(path)
        lookfile.writer_document(document)
        if not document.get('native_photo'):
            raise ValueError('所选外观缺少原生照片阶段：' + name)
        result.append(dict(slot=slot, profile=name, name=document['name'], path=str(path),
                           sha256=digest(path.read_bytes())))
    if not result:
        raise ValueError('至少保留一个要安装的外观。')
    return result, [dict(name=r['name'], category=r['category']) for r in catalog['profiles']]


def backend_path(value=None):
    path = Path(value) if value else ROOT.parent / 'A7C2Tools-Windows-x64/A7C2Tools/A7C2Tools.exe'
    path = path.resolve()
    if path.name.lower() != 'a7c2tools.exe' or not path.is_file() or not (path.parent / '_internal').is_dir():
        raise ValueError('请选择整包解压后的 A7C2Tools.exe，旁边必须有 _internal。')
    return path


def initialize(folder, app=None, library=None, history_roots=()):
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'guide.private.json'
    if path.exists():
        raise ValueError('向导已经存在，请用 status 读取进度，不要重新初始化。')
    backend = backend_path(app)
    library = Path(library or backend.parent / 'Profiles').resolve()
    roots = list(dict.fromkeys(str(Path(p).resolve()) for p in
                              [data_root() / 'work', data_root() / 'runs', data_root() / 'ai-guide', *history_roots]))
    state = dict(schema=SCHEMA, phase='CAMERA_INFO', created_at=now(), workspace=str(folder),
                 backend=str(backend), library=str(library), history_roots=roots,
                 selection=[dict(slot=i, profile=n) for i, n in enumerate(DEFAULTS, 1)],
                 extras={k: False for k in EXTRAS}, events=[], physical_checks_accepted=False)
    # Missing/invalid profiles fail locally, before even creating an active guide.
    rows, choices = assets(library, state['selection'])
    state['plan'] = make_plan(rows, state['extras'])
    state['available_profiles'] = choices
    state['existing_transactions'] = history(roots, folder)
    save(state, path)
    return view(state)


def save(state, path):
    state['updated_at'] = now()
    write_json(path, state)


def make_plan(rows, extras):
    plan = dict(schema='a7c2-ai-plan/1', looks=rows, extras=extras.copy(),
                replaces_slots=[r['slot'] for r in rows],
                notice='将替换所列自订槽位现有内容；未选择的槽位及未启用的附加功能保留。')
    plan['id'] = digest(json.dumps(plan, sort_keys=True, ensure_ascii=False).encode())
    return plan


def load(folder):
    path = Path(folder).resolve() / 'guide.private.json'
    state = read(path)
    if state.get('schema') != SCHEMA or Path(state['workspace']).resolve() != path.parent:
        raise ValueError('向导状态或目录不匹配。')
    return state, path


def configure(state, config):
    if state['phase'] not in {'CAMERA_INFO', 'FIRMWARE_UPDATE', 'CONNECT_CAMERA', 'READY_DRIVERS',
                              'READY_STABILITY', 'READY_INSTALL', 'READY_RESTORE', 'HISTORY_QUESTION'}:
        raise ValueError('当前阶段不能更改方案；安装后的方案不能被新选择覆盖。')
    if set(config) - {'looks', 'extras'}:
        raise ValueError('配置只接受 looks 和 extras。')
    selection = config.get('looks', state['selection'])
    extras = dict(state['extras'], **config.get('extras', {}))
    if set(extras) != set(EXTRAS) or any(type(v) is not bool for v in extras.values()):
        raise ValueError('extras 只接受 fl23/sound/vertical/plugin 的布尔值。')
    rows, choices = assets(state['library'], selection)
    state.update(selection=selection, extras=extras, plan=make_plan(rows, extras), available_profiles=choices)


def answer(state, kind, values):
    phase = state['phase']
    if kind == 'camera' and phase in {'CAMERA_INFO', 'FIRMWARE_UPDATE', 'UNSUPPORTED_FIRMWARE', 'UNSUPPORTED_MODEL'}:
        model, version, modified = values.get('model'), values.get('firmware'), values.get('modified')
        if modified not in {'yes', 'no', 'unknown'} or not isinstance(version, str):
            raise ValueError('请从用户取得机型、机身版本和是否改装过的信息。')
        state['camera_confirmation'] = dict(model=model, firmware=version, modified=modified,
                                            source='user_camera_menu', confirmed_at=now())
        if model != 'ILCE-7CM2':
            state['phase'] = 'UNSUPPORTED_MODEL'
        elif version != '2.01':
            try:
                parts = version.split('.')
                old = len(parts) == 2 and all(n.isdigit() for n in parts) and tuple(int(n) for n in parts) < (2, 1)
            except ValueError:
                old = False
            state['phase'] = 'FIRMWARE_UPDATE' if old else 'UNSUPPORTED_FIRMWARE'
        else:
            state['phase'] = 'CONNECT_CAMERA'
    elif kind == 'connected' and phase == 'CONNECT_CAMERA' and values.get('confirmed'):
        state['existing_transactions'] = history(state['history_roots'], state['workspace'])
        state['phase'] = 'EXISTING_TRANSACTION' if state['existing_transactions'] else 'READY_DRIVERS'
    elif kind == 'history' and phase == 'HISTORY_QUESTION' and values.get('modified') in {'yes', 'no'}:
        state['camera_confirmation']['modified'] = values['modified']
        state['phase'] = 'READY_RESTORE' if values['modified'] == 'yes' else 'READY_INSTALL'
    elif kind == 'reboot' and phase in {'WAIT_RELOAD', 'WAIT_RESOURCE_RELOAD'} and values.get('confirmed'):
        state['reboot_report'] = dict(at=now(), user_reported=True)
        state['phase'] = 'READY_CONTINUE'
    elif kind == 'checks' and phase == 'PHYSICAL_CHECKS':
        keys = ['preview', 'capture_playback', 'original_looks']
        keys += [k for k, enabled in state['extras'].items() if enabled]
        checks = {k: values.get(k) for k in keys}
        if any(type(v) is not bool for v in checks.values()):
            raise ValueError('请分别提供预览、拍摄回放、原有外观的检查结果。')
        state['physical_checks'] = dict(checks, at=now())
        state['physical_checks_accepted'] = all(checks.values())
        state['phase'] = 'COMPLETE' if all(checks.values()) else 'NEEDS_REVIEW'
    else:
        raise ValueError('这条反馈不适用于当前阶段，或尚未获得用户明确反馈。')
    state['events'].append(dict(event='user_feedback', kind=kind, phase=state['phase'], at=now()))


def alive(pid):
    if not pid:
        return False
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5  # access denied is not proof of exit
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def worker(request_path, backend):
    """Wait without a timeout. Never terminate an active camera writer."""
    request_path = Path(request_path).resolve()
    folder = request_path.parent
    execution = folder / 'execution.private.json'
    started = False
    # A duplicate launcher must not replace another launcher's execution proof.
    try:
        with (folder / 'launcher.claim').open('x', encoding='utf-8') as claim:
            claim.write(str(os.getpid()))
    except FileExistsError:
        return 2
    try:
        # Across guide sessions, while the backend retains its own camera lock.
        with lock(data_root() / 'ai-guide' / 'worker.lock'):
            request = read(request_path)
            state, _ = load(request['guide_session'])
            if (state['phase'] != 'RUNNING' or Path(state['active']['job']) != folder
                    or state['active']['action'] != request['action']
                    or state['active']['request_sha256'] != digest(request_path.read_bytes())
                    or str(backend_path(backend)) != state['backend']):
                raise ValueError('后台请求与当前向导执行意图不匹配，尚未启动。')
            guard = request.get('guide_guard', {})
            if guard and history(guard['roots'], guard['workspace']):
                raise ValueError('另一向导或旧任务仍未完成，后台尚未启动；先审查其记录。')
            write_json(execution, dict(phase='RUNNING', worker_started=False))
            with (folder / 'process.log').open('a', encoding='utf-8') as stream:
                child = subprocess.Popen([str(backend), '--worker', str(request_path)],
                                         stdout=stream, stderr=stream, cwd=str(Path(backend).parent))
                started = True
                write_json(execution, dict(phase='RUNNING', worker_started=True, child_pid=child.pid))
                code = child.wait()
            write_json(execution, dict(phase='ENDED', worker_started=True, returncode=code, ended_at=now()))
    except BaseException as exc:
        # If the child was launched, an exception does not prove its I/O ended.
        write_json(execution, dict(phase='UNKNOWN' if started else 'ENDED', worker_started=started,
                                   error=str(exc), ended_at=now() if not started else None))
        return 2
    return code


def battery_confirmation(values):
    value = values.get('battery')
    if not values.get('confirmed') or type(value) is not int or not 50 <= value <= 100:
        raise ValueError('开始或继续写入前，需用户确认执行及当前电量至少 50%；不可由 AI 猜测。')


def start(state, state_path, operation, values, spawn=None):
    phase = state['phase']
    expected = {'drivers': {'READY_DRIVERS'}, 'stability': {'READY_STABILITY'},
                'restore': {'READY_RESTORE'}, 'install': {'READY_INSTALL'}, 'continue': {'READY_CONTINUE'}}
    if phase not in expected.get(operation, set()):
        raise ValueError('当前阶段不允许执行 ' + operation + '，请先读取 status。')
    if sys.platform != 'win32':
        raise ValueError('当前 AI 向导的执行端仅支持 Windows；不会在其他平台启动相机操作。')
    confirmation = state.get('camera_confirmation', {})
    if confirmation.get('model') != 'ILCE-7CM2' or confirmation.get('firmware') != '2.01':
        raise ValueError('机型与用户确认的机身版本必须为 ILCE-7CM2／2.01。')
    backend_path(state['backend'])
    if operation in {'install', 'restore'}:
        pending = history(state['history_roots'], state['workspace'])
        if pending:
            state.update(phase='EXISTING_TRANSACTION', existing_transactions=pending)
            save(state, state_path)
            raise ValueError('发现新的未完成事务，先检查记录，不能开始新的写入。')
    folder = Path(state['workspace'])
    arguments = {}
    if operation == 'drivers':
        action = 'usb_prepare'
    elif operation == 'stability':
        action = 'usb_stability'
    elif operation == 'restore':
        battery_confirmation(values)
        if not values.get('replace_slots'):
            raise ValueError('原厂功能恢复会清空自订 1–6，旧配方不找回，需用户知情确认。')
        action = 'direct_factory_reset'
        arguments = dict(workspace=str(folder / 'work' / ('factory-' + uuid.uuid4().hex[:8])),
                         firmware='2.01', power_confirmed=True)
        state['purpose'] = 'restore'
    elif operation == 'install':
        battery_confirmation(values)
        if not values.get('replace_slots'):
            raise ValueError('需用户确认将替换计划列出的自订槽位。')
        rows, _ = assets(state['library'], state['selection'])
        plan = make_plan(rows, state['extras'])
        if plan['id'] != state['plan']['id']:
            raise ValueError('外观文件已改变，请重新 configure 并展示方案后再确认。')
        frozen = []
        inputs = folder / 'inputs'
        inputs.mkdir(exist_ok=True)
        for row in rows:
            raw = Path(row['path']).read_bytes()
            if digest(raw) != row['sha256']:
                raise ValueError('外观在准备过程中发生变化，尚未连接相机。')
            target = inputs / ('slot%d.a7look' % row['slot'])
            target.write_bytes(raw)
            frozen.append(dict(slot=row['slot'], path=str(target), name=row['name']))
        action = 'setup_all'
        arguments = dict(workspace=str(folder / 'work' / 'setup'), firmware='2.01', power_confirmed=True,
                         options=dict(state['extras'], looks=frozen))
        state.update(purpose='install', install_arguments=arguments,
                     approved_plan=dict(id=plan['id'], at=now(), battery=values['battery']))
    else:
        if state['purpose'] == 'restore':
            action = 'direct_verify'
            arguments = dict(workspace=state['backend_workspace'], accepted=False)
        else:
            battery_confirmation(values)
            action = 'setup_all'
            arguments = state['install_arguments']
    job = folder / 'jobs' / uuid.uuid4().hex
    job.mkdir(parents=True)
    request = job / 'request.private.json'
    from . import VERSION
    request_value = dict(schema='a7c2-desktop-job/1', action=action, arguments=arguments,
                         job_dir=str(job), version=VERSION, guide_session=state['workspace'])
    if operation in {'install', 'restore'}:
        request_value['guide_guard'] = dict(roots=state['history_roots'], workspace=state['workspace'])
    write_json(request, request_value)
    write_json(job / 'status.private.json', dict(phase='QUEUED', action=action))
    prior = phase
    state.update(phase='RUNNING', active=dict(operation=operation, action=action, job=str(job),
                                           request_sha256=digest(request.read_bytes()),
                                           previous_phase=prior, launched_at=now()))
    # Persist intent before launch. A crash here is reviewable, never replayable.
    save(state, state_path)
    try:
        with (job / 'launcher.log').open('a', encoding='utf-8') as output:
            flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            child = (spawn or subprocess.Popen)([sys.executable, str(ROOT / 'ai_guide.py'), '_worker',
                                                  '--request', str(request), '--backend', state['backend']],
                                                 stdout=output, stderr=output, stdin=subprocess.DEVNULL,
                                                 creationflags=flags, start_new_session=os.name != 'nt')
    except OSError as exc:
        state.update(phase=prior, error=str(exc))  # Popen did not start a process.
        state.pop('active', None)
        save(state, state_path)
        raise
    # If this save fails, the already-persisted RUNNING intent must remain.
    # A launched child is never relabeled as a retryable launch failure.
    state['active']['pid'] = child.pid
    save(state, state_path)


def poll(state):
    if state['phase'] != 'RUNNING':
        return
    active = state['active']
    job = Path(active['job'])
    terminal_path = job / 'execution.private.json'
    execution = read(terminal_path) if terminal_path.exists() else {}
    if execution.get('phase') != 'ENDED':
        if alive(active.get('pid')):
            return
        state.update(phase='NEEDS_REVIEW', error='执行进程已退出，但没有完整结束凭据；不重复执行。')
        return
    status = read(job / 'status.private.json')
    state['last_job'] = dict(active, status=status, execution=execution)
    state.pop('active')
    if not execution.get('worker_started'):
        state.update(phase=active['previous_phase'], error=execution.get('error', '后台尚未启动。'))
        return
    if status.get('phase') != 'SUCCEEDED' or execution.get('returncode') != 0:
        # Read-only operations are retryable. Writes retain the exact failed job.
        phase = active['previous_phase'] if active['operation'] in {'drivers', 'stability'} else 'NEEDS_REVIEW'
        state.update(phase=phase, error=status.get('error', '任务没有已确认的成功结果。'))
        return
    result = status.get('result', {})
    operation = active['operation']
    state.pop('error', None)
    state['events'].append(dict(event='worker_finished', operation=operation, result_phase=result.get('phase'), at=now()))
    if operation == 'drivers':
        state['phase'] = 'READY_STABILITY'
    elif operation == 'stability':
        if result.get('phase') != 'PASSED' or result.get('camera_io_ended') is not True:
            state.update(phase='READY_STABILITY', error='稳定性检测没有返回完整通过凭据。')
            return
        modified = state['camera_confirmation']['modified']
        state['phase'] = {'yes': 'READY_RESTORE', 'no': 'READY_INSTALL', 'unknown': 'HISTORY_QUESTION'}[modified]
    else:
        result_phase = result.get('phase')
        state['backend_workspace'] = result.get('workspace', state.get('backend_workspace'))
        if result_phase in {'WAIT_RESOURCE_RELOAD', 'AWAITING_RESOURCE_RELOAD'}:
            state['phase'] = 'WAIT_RESOURCE_RELOAD'
        elif result_phase in {'WAIT_RELOAD', 'AWAITING_RELOAD'}:
            state['phase'] = 'WAIT_RELOAD'
        elif result_phase in {'LOADED', 'COMPLETE'}:
            state['phase'] = 'READY_INSTALL' if state['purpose'] == 'restore' else 'PHYSICAL_CHECKS'
        else:
            state.update(phase='NEEDS_REVIEW', error='后台返回了需人工审查的阶段：' + str(result_phase))


def adopt(state, workspace):
    """Resume only a known, completed write boundary, never an ambiguous write."""
    if state['phase'] != 'EXISTING_TRANSACTION':
        raise ValueError('只能在发现历史事务后续接。')
    workspace = Path(workspace).resolve()
    row = next((r for r in state['existing_transactions'] if Path(r['workspace']) == workspace), None)
    if row is None:
        raise ValueError('请选择向导已列出的事务。')
    if row['kind'] != 'setup' or row['phase'] not in {'WAIT_RELOAD', 'WAIT_RESOURCE_RELOAD'}:
        raise ValueError('该历史事务不能自动续接。保留诊断，在原软件中审查；不要删除状态或重试写入。')
    old = read(workspace / 'setup.private.json')
    if old.get('phase') != row['phase']:
        raise ValueError('旧事务已变化，请重新检查状态，不能用过时的记录续接。')
    sys.path.insert(0, str(ROOT / 'src/looks'))
    from looktool import lookfile
    rows = []
    for row in old['options'].get('looks', []):
        source = Path(row['path'])
        document = lookfile.read(source)
        lookfile.writer_document(document)
        rows.append(dict(slot=row['slot'], profile=document['name'], name=row.get('name') or document['name'],
                         path=str(source), sha256=digest(source.read_bytes())))
    extras = {k: bool(old['options'].get(k, k != 'plugin')) for k in EXTRAS}
    # Resumption uses the historical plan, not the new default.
    state.update(purpose='install', phase=old['phase'], adopted_workspace=str(workspace),
                 plan=make_plan(rows, extras), extras=extras,
                 backend_workspace=str(workspace),
                 install_arguments=dict(workspace=str(workspace), firmware='2.01', power_confirmed=True),
                 adopted_plan_notice='续接原事务的已保存配置，默认六款不覆盖历史安装计划。')


def view(state):
    phase = state['phase']
    prompts = {
        'CAMERA_INFO': '先确认机型、机身版本及以前是否安装过本项目。版本请在相机 MENU → 设置 → 设置选项 → 版本 → 机身中查看。',
        'FIRMWARE_UPDATE': '先按 Sony 官方说明升级到兼容的 2.01；核对当前版本对应的升级要求。更新期间不要取电池或存储卡，完成后重新查看机身版本。',
        'UNSUPPORTED_MODEL': '该工具只支持 ILCE-7CM2，停止安装。',
        'UNSUPPORTED_FIRMWARE': '版本尚未确认或不受支持。不要安装、盲目升级最新版或尝试降级；先核对机身版本。',
        'CONNECT_CAMERA': '请关闭原软件，确保只有一台相机；用数据线直接连接电脑，在相机 USB 连接方式界面选择“影像传输（MSC）”（即海量存储模式），完成后反馈。',
        'EXISTING_TRANSACTION': '发现未完成历史事务，先检查记录和诊断；可对已结束写入且等待重开的旧一键安装使用 adopt，不能新开写入覆盖它。',
        'READY_DRIVERS': '连接反馈已记录。下一步准备相机的两阶段驱动；Windows 管理员弹窗需用户在本机允许。',
        'READY_STABILITY': '驱动准备完成。下一步运行至少两分钟的 USB 只读稳定性检查。',
        'HISTORY_QUESTION': 'USB 检查通过；尚不确定以前是否改装，请先确认，不能默认清空自订槽位。',
        'READY_RESTORE': '以前安装过本项目。需先恢复原厂功能，会将自订 1–6 设为 ST，旧配方不能找回；这不是固件升级或降级。确认此影响和当前电量后再执行。',
        'READY_INSTALL': '当前方案已准备好，以 plan 中的实际槽位和外观为准（最多六个）。说明所列槽位会被替换；用户接受此方案并报告当前电量后即可安装，无需逐款选择。',
        'RUNNING': '后台正在执行。保持相机供电和连接，不要拔线、关机、关闭进程或启动其他相机工具；用 status/poll 查看进度。',
        'WAIT_RELOAD': '后台进程已返回，本次读写已结束。请按断电步骤重开，确认能正常取景，接回 USB 并选择“影像传输（MSC）”（即海量存储模式）后反馈。',
        'WAIT_RESOURCE_RELOAD': '后台进程已返回，名称阶段读写已结束，剩余安装尚未完成。请按断电步骤重开，接回 USB 并选择“影像传输（MSC）”（即海量存储模式）后反馈。',
        'READY_CONTINUE': '用户已报告断电重开；程序还须核验新启动证据。继续原事务，不新建安装；安装续接可能包含剩余写入，需确认供电。',
        'PHYSICAL_CHECKS': '程序核验已通过，后台读写已结束。可拔下 USB 并保持相机开机；请检查每个已装槽位的名称和预览、拍照及回放、原有 ST/FL 等外观，分别反馈结果。若加装其他功能，也需检查其实际效果。',
        'COMPLETE': '程序核验及用户机身检查均已通过，本次安装完成。',
        'NEEDS_REVIEW': '停止自动操作并保留当前事务。读取日志或导出诊断，不删除状态、不重复写入、不把结果未知解释为未写入。',
    }
    allowed = {'READY_DRIVERS': ['drivers'], 'READY_STABILITY': ['stability'],
               'READY_RESTORE': ['restore'], 'READY_INSTALL': ['install'], 'READY_CONTINUE': ['continue']}
    result = dict(schema=SCHEMA, session=state['workspace'], phase=phase, prompt=prompts[phase],
                  allowed_operations=allowed.get(phase, []), plan=state['plan'],
                  alternatives=dict(profiles=state['available_profiles'], extras=list(EXTRAS),
                                    partial_slots=True, default_requires_no_selection=True),
                  physical_checks_accepted=state['physical_checks_accepted'],
                  offline_status=True)
    for key in ('camera_confirmation', 'error', 'existing_transactions', 'adopted_plan_notice', 'last_job'):
        if key in state:
            result[key] = state[key]
    if phase in {'WAIT_RELOAD', 'WAIT_RESOURCE_RELOAD'}:
        result['cold_reload_steps'] = STEPS
    if phase in {'FIRMWARE_UPDATE', 'CAMERA_INFO'}:
        result['official_update_url'] = SONY
    if phase == 'RUNNING':
        active = state['active']
        result['active_job'] = active
        status = Path(active['job']) / 'status.private.json'
        if status.exists():
            try:
                result['worker_status'] = read(status)
            except (OSError, ValueError):
                result['worker_status'] = dict(phase='UNREADABLE')
        result['log_path'] = str(Path(active['job']) / 'worker.log')
    return result


def diagnostics(state, output):
    """Public summary only. Private logs/firmware/serials stay on the computer."""
    summary = dict(schema=SCHEMA, phase=state['phase'], events=state['events'],
                   physical_checks_accepted=state['physical_checks_accepted'],
                   profiles=[dict(slot=r['slot'], profile=r['profile']) for r in state['plan']['looks']])
    last = state.get('last_job', {})
    summary['last_worker'] = dict(action=last.get('action'), phase=last.get('status', {}).get('phase'),
                                  error_type=last.get('status', {}).get('error_type'))
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('guide-summary.json', json.dumps(summary, ensure_ascii=False, indent=2))
    return dict(path=str(output), firmware_included=False, uploaded=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, help='Local guide workspace; required except for init/_worker')
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--directory', type=Path)
    init.add_argument('--backend', type=Path)
    init.add_argument('--library', type=Path)
    init.add_argument('--history-root', action='append', default=[])
    for command in ('status', 'poll', 'plan'):
        sub.add_parser(command)
    config = sub.add_parser('configure')
    config.add_argument('--file', required=True, type=Path)
    feedback = sub.add_parser('answer')
    feedback.add_argument('--kind', required=True, choices=('camera', 'connected', 'history', 'reboot', 'checks'))
    feedback.add_argument('--file', required=True, type=Path, help='JSON values reported by the human')
    run = sub.add_parser('start')
    run.add_argument('--operation', required=True, choices=('drivers', 'stability', 'restore', 'install', 'continue'))
    run.add_argument('--confirmed', action='store_true')
    run.add_argument('--battery', type=int)
    run.add_argument('--replace-slots', action='store_true')
    resume = sub.add_parser('adopt')
    resume.add_argument('--workspace', type=Path, required=True)
    bundle = sub.add_parser('diagnostics')
    bundle.add_argument('--output', type=Path, required=True)
    internal = sub.add_parser('_worker')
    internal.add_argument('--request', required=True, type=Path)
    internal.add_argument('--backend', required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == '_worker':
        return worker(args.request, args.backend)
    try:
        # Keep stdout a single JSON document, including validation library output.
        with redirect_stdout(io.StringIO()):
            if args.command == 'init':
                folder = args.directory or data_root() / 'ai-guide' / uuid.uuid4().hex[:12]
                with lock(Path(folder).resolve().parent / ('.' + Path(folder).name + '.lock')):
                    result = initialize(folder, args.backend, args.library, args.history_root)
            else:
                if not args.session:
                    raise ValueError('请提供 init 返回的 --session 目录。')
                with lock(args.session.resolve().parent / ('.' + args.session.name + '.lock')):
                    state, path = load(args.session)
                    if args.command == 'answer':
                        answer(state, args.kind, read(args.file))
                    elif args.command == 'configure':
                        configure(state, read(args.file))
                    elif args.command == 'start':
                        start(state, path, args.operation, vars(args))
                    elif args.command == 'poll':
                        poll(state)
                    elif args.command == 'adopt':
                        adopt(state, args.workspace)
                    elif args.command == 'plan':
                        if state['phase'] in {'CAMERA_INFO', 'CONNECT_CAMERA', 'READY_INSTALL', 'READY_RESTORE'}:
                            configure(state, {})
                    result = diagnostics(state, args.output) if args.command == 'diagnostics' else view(state)
                    if args.command == 'start':
                        result['offline_status'] = False
                        result['background_worker_launched'] = True
                    if args.command not in {'status', 'diagnostics'}:
                        save(state, path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ImportError) as exc:
        print(json.dumps(dict(ok=False, error=str(exc), error_type=type(exc).__name__,
                              next_action='读取现有 status 和日志；不要跳过前置条件或重试结果未知的写入。'), ensure_ascii=False))
        return 2
