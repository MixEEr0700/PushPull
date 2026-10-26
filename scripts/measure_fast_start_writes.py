"""Serial hot-write/start regression on exact existing C fixtures; no reseeding work.
CPU throttling is not Android emulation. Never opens an existing user profile.
Generate synthetic fixtures with measure_incremental_write.py; C captures with
measure_startup.py. Inputs are retained locally, not shipped as real backups.
"""
import argparse,hashlib,json,platform,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
from measure_incremental_write import artifact,one_profile,statistics,ROOT

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ref',required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--v2-fixtures',type=Path,required=True);p.add_argument('--v2-suffix',default='-C-captured.json');p.add_argument('--cases',nargs='+',required=True);p.add_argument('--profiles',type=int,default=3);p.add_argument('--writes',type=int,default=8);p.add_argument('--cpu',type=float,default=4);p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
 server,thread,hashes,release=artifact(args.ref,args.output/'runtime');report={'syntheticOnly':True,'ref':args.ref,'runtimeSha256':hashes,'instrumentedRelease':release,'cpuThrottle':args.cpu,'platform':platform.platform(),'cases':{}};url='http://127.0.0.1:'+str(server.server_port)+'/'
 try:
  with sync_playwright() as pw:
   for label in args.cases:
    path=args.v2_fixtures/(label+args.v2_suffix);seed=json.loads(path.read_text());original=json.loads((args.fixtures/(label+'-fixture.json')).read_text());seed['sourceHash']=original['sourceHash'];case=report['cases'][label]={'fixtureSHA256':hashlib.sha256(path.read_bytes()).hexdigest(),'sourceHash':seed['sourceHash'],'profiles':[]}
    for n in range(args.profiles):
     print('BEGIN',label,n,flush=True);case['profiles'].append(one_profile(pw,url,args.output/(label+'-'+str(n)),seed,args.cpu,args.writes));case['statistics']=statistics(case['profiles']);(args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('COMPLETE',label,case['statistics']['all']['clickToStrictCompleteMs'],flush=True)
 finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':main()
