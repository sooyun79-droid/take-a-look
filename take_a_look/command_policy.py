"""Classification is not authorization: repository scripts remain untrusted."""
import re

KNOWN={'node --test':'node-test','tsc --noEmit':'ts-typecheck','eslint src':'node-lint','next build':'node-build','vitest run':'node-vitest','jest --runInBand':'node-jest'}


def classify(name, script, all_scripts):
    result={'name':name,'classification':'blocked','reason_code':'UNKNOWN_COMMAND','runner':None}
    if not isinstance(script,str): return result
    if re.search(r'[;&|`$<>\r\n]|\b(deploy|publish|push|migrate|migration|prisma|rm|del|curl|wget|ssh|token|login|install|npx)\b',script,re.I):
        result['reason_code']='DANGEROUS_OR_CHAINED_COMMAND';return result
    if name in {'deploy','publish','preinstall','postinstall','prepare'}:
        result['reason_code']='SIDE_EFFECT_SCRIPT';return result
    if 'pre'+name in all_scripts or 'post'+name in all_scripts:
        result['reason_code']='LIFECYCLE_HOOK_PRESENT';return result
    if script.strip() in KNOWN:
        result.update(classification='sandbox_required',reason_code='PROJECT_CODE_OR_CONFIG_CAN_HAVE_SIDE_EFFECTS',runner=KNOWN[script.strip()])
        result['runner_implemented']=result['runner'] in {'node-test','ts-typecheck','node-lint'}
    return result
