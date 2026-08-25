from __future__ import annotations
import argparse, json, platform, re, shutil, subprocess, tarfile, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(); p.add_argument('--version',required=True); p.add_argument('--output-dir',type=Path,required=True); p.add_argument('--pyinstaller',type=Path,required=True); a=p.parse_args()
    if platform.system()!='Linux' or platform.machine().lower() not in {'x86_64','amd64'}: raise SystemExit('only linux-x86_64 supported')
    addon=json.loads((ROOT/'addon.json').read_text()); pkg=(ROOT/'backend/sonicforge/__init__.py').read_text(); packaged=re.search(r'__version__ = "([^"]+)"',pkg).group(1)
    if a.version!=addon['version'] or a.version!=packaged: raise SystemExit('version mismatch')
    a.output_dir.mkdir(parents=True,exist_ok=True); name=f'control-deck-sonic-forge-{a.version}-linux-x86_64'
    with tempfile.TemporaryDirectory(prefix='sonicforge-bundle-') as td:
        work=Path(td); dist=work/'dist'; py=a.pyinstaller.parent/'python'; argv=[str(py),'-m','PyInstaller'] if py.exists() else [str(a.pyinstaller)]
        subprocess.run([*argv,'--noconfirm','--clean','--onefile','--name','sonicforge-core','--paths',str(ROOT/'backend'),'--distpath',str(dist),'--workpath',str(work/'build'),'--specpath',str(work),'--add-data',str(ROOT/'frontend')+':frontend','--add-data',str(ROOT/'schemas')+':schemas','--add-data',str(ROOT/'worker_packs')+':worker_packs',str(ROOT/'scripts/bundle_entrypoint.py')],check=True,cwd=ROOT)
        bundle=work/name; (bundle/'bin').mkdir(parents=True); shutil.copy2(dist/'sonicforge-core',bundle/'bin/sonicforge-core'); (bundle/'bin/sonicforge-core').chmod(0o755)
        (bundle/'control-deck-addon.json').write_text(json.dumps(addon,ensure_ascii=False,indent=2)+'\n')
        feature={"schema_version":1,"feature_id":"sonic-forge","version":a.version,"platform":"linux","architecture":"x86_64","entrypoint":"bin/sonicforge-core","addon_manifest":"control-deck-addon.json","provision_args":["doctor"],"smoke_args":["doctor"],"service_args":["serve"],"health_url":"http://127.0.0.1:9140/health"}
        (bundle/'control-deck-feature.json').write_text(json.dumps(feature,ensure_ascii=False,indent=2)+'\n')
        artifact=a.output_dir/f'{name}.tar.gz'
        with tarfile.open(artifact,'w:gz',compresslevel=9) as ar: ar.add(bundle,arcname=name)
        print(artifact)
if __name__=='__main__': main()
