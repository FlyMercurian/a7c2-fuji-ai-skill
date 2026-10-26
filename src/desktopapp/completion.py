"""Human-readable completed setup; detailed evidence stays in private files."""


def archive_error(state):
    error=state.pop('error',None)
    if error:
        state.setdefault('previous_errors',[]).append(dict(phase=state.get('phase'),error=error))
        return True
    return False


def text(state):
    if state.get('phase')!='COMPLETE':raise ValueError('上次安装尚未结束，请使用“继续安装”。')
    options=state.get('options',{})
    lines=['本次所选操作已完成，程序与设置核对通过。','请在机身检查预览、拍摄和回放。','']
    if not options.get('_preset_only'):
        lines.append('FL2／FL3：'+('已启用' if options.get('fl23',True) else '本次未改动'))
    looks=options.get('looks',[])
    if looks:
        lines.append('自定义外观：已写入')
        lines.extend('  自订 %s：%s'%(row['slot'],row.get('name') or '沿用文件名称') for row in looks)
    else:lines.append('自定义外观：本次未改动')
    if options.get('_preset_only'):
        lines.append('本次预制滤镜安装已结束，无需为了查看结果再次刷写。')
        return '\n'.join(lines)
    lines.append('电子快门声：'+('已启用支持，请检查机身音频信号设置' if options.get('sound',True) else '本次未选择'))
    if options.get('plugin'):lines.append('Lightroom 插件：已安装，请在插件管理器中启用')
    if options.get('vertical',True):
        if state.get('vertical_result',{}).get('persistent') and state['vertical_result'].get('loaded_verified'):
            lines.append('竖屏拍摄信息：已保存开启，并已核对重开后的运行状态；无需每次连接电脑开启。')
        else:
            lines.extend(['竖屏拍摄信息：旧版仅开启本次运行。',
                '旧任务未保存为开机默认；可在新版“竖屏显示”页保存开启。'])
    else:lines.append('竖屏拍摄信息：本次未改动')
    lines.extend(['','本次安装已结束，无需为了查看结果再次刷写。'])
    return '\n'.join(lines)


def console_summary(state):
    return {key:state[key] for key in ('schema','phase','workspace','message') if key in state} | {
        'looks':[dict(slot=r['slot'],name=r.get('name')) for r in state.get('options',{}).get('looks',[])],
        'completed_steps':state.get('completed_steps',[]),
        'physical_checks_accepted':state.get('physical_checks_accepted',False),
        'previous_error_count':len(state.get('previous_errors',[]))}
