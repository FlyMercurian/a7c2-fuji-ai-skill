"""Compose selected imports and ST resets without unrelated feature toggles."""
from .transactionevidence import read_only_failure


def options(rows):
    from looktool import bundle
    if not rows:
        raise ValueError('请至少添加一个操作项；未添加的槽位保持原样。')
    writes,resets,operations,seen=[],[],[],set()
    for row in rows:
        slot=row.get('slot');action=row.get('action','write')
        if type(slot) is not int or slot not in range(1,7) or slot in seen:
            raise ValueError('每个目标槽位只能有一个操作，范围为 1–6。')
        seen.add(slot)
        if action=='restore':
            resets.append(slot);operations.append(dict(slot=slot,action=action))
        elif action=='write':
            path=row.get('path') or row.get('file')
            if not path:raise ValueError('请为自订 %s 选择 A7Look 文件。'%slot)
            name=row.get('name') or ''
            if not isinstance(name,str):raise ValueError('外观名称必须是文字。')
            value=dict(slot=slot,path=path,name=name.strip())
            writes.append(value);operations.append(dict(value,action=action))
        else:raise ValueError('Unknown slot operation: '+str(action))
    result, _ = bundle.documents(dict(looks=writes,reset_slots=resets,slot_operations=operations,
        fl23=False,sound=False,vertical_persistent=False))
    resolved={r['slot']:r for r in result['looks']}
    result['slot_operations']=[dict(resolved[r['slot']],action='write') if r['action']=='write' else r for r in operations]
    return result
