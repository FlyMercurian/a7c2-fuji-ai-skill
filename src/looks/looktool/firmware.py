"""Exact-source offline data replacement for the existing THREE-table layout.

The six-slot planner is deliberately not a six-table camera installer.
No USB access, file upload, settings write, WBI operation or camera execution.
"""
import hashlib
from .tablecodec import validate as decode

AP_SHA = "86f4ac7d255cf6ffac56425539b8180e4893c7d39e1d38fbfeb6a93e145b1ad9"
CP_SHA = "b307c7ffe5eab8a58138fd5d51157b15969c4f2963c1f58f5a9e5a2adbc8cac8"
TABLES = {1:0xb27590, 2:0xb27a4f, 3:0x1101ae0}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def transition(before, after, regions):
    files = {}
    for name, original in before.items():
        target = after[name]
        if len(original) != len(target):
            raise ValueError("Fixed-window transition cannot resize firmware")
        spans = sorted(regions[name])
        if any(at < 0 or n <= 0 or at+n > len(original) for at,n in spans) or any(a+n > b for (a,n),(b,_) in zip(spans,spans[1:])):
            raise ValueError("Invalid or overlapping transition windows")
        check, windows = bytearray(original), []
        for at,n in spans:
            old, new = original[at:at+n], target[at:at+n]
            if old != new:
                windows.append({"offset":hex(at),"bytes":n,"before_hex":old.hex(),"after_hex":new.hex()})
                check[at:at+n] = new
        if bytes(check) != target:
            raise ValueError("Change outside the declared windows")
        files[name] = {"bytes":len(original),"before_sha256":sha(original),"after_sha256":sha(target),"windows":windows}
    return {"schema":"a7c2-private-transition/1","status":"OFFLINE_REVIEW_REQUIRED_NOT_AN_INSTALLER","files":files,
            "camera_io":False,"settings_or_calibration_writes":False}


def apply(files, manifest,*,hash_checks=True):
    result = {}
    if set(files) != set(manifest["files"]):
        raise ValueError("Component set mismatch")
    for name, spec in manifest["files"].items():
        original = files[name]
        if len(original) != spec["bytes"] or (hash_checks and sha(original) != spec["before_sha256"]):
            raise ValueError("Whole-file source fingerprint mismatch")
        target, spans = bytearray(original), []
        for window in spec["windows"]:
            at,n = int(window["offset"],16),window["bytes"]
            old,new = bytes.fromhex(window["before_hex"]),bytes.fromhex(window["after_hex"])
            if at < 0 or n <= 0 or at+n > len(original) or len(old) != n or len(new) != n or original[at:at+n] != old:
                raise ValueError("Window precondition mismatch")
            spans.append((at,at+n))
            target[at:at+n] = new
        spans.sort()
        if any(a[1] > b[0] for a,b in zip(spans,spans[1:])) or (hash_checks and sha(target) != spec["after_sha256"]):
            raise ValueError("Overlap or target fingerprint mismatch")
        result[name] = bytes(target)
    return result


def replace_tables(ap, cp, replacements):
    if not replacements or any(type(slot) is not int or slot not in TABLES for slot in replacements):
        raise ValueError("Installed layout has only slots 1/2/3. Slots 4/5/6 require a separately verified storage/marker layout")
    if sha(ap) != AP_SHA or sha(cp) != CP_SHA:
        raise ValueError("This adapter requires the exact documented three-look AP/CP source, not stock or a later import")
    target = bytearray(cp)
    for slot,raw in replacements.items():
        decode(raw)
        at = TABLES[slot]
        target[at:at+1215] = raw
    before,after = {"appFw.so":ap,"cpapp-b.bin":cp},{"appFw.so":ap,"cpapp-b.bin":bytes(target)}
    spans = {"appFw.so":[],"cpapp-b.bin":[(TABLES[s],1215) for s in replacements]}
    forward,reverse = transition(before,after,spans),transition(after,before,spans)
    if apply(apply(before,forward),reverse) != before:
        raise ValueError("Inverse transition differs")
    return forward,reverse,after
