"""Paired Stage B controls; serial browser processes, no concurrent regression.

Each profile has eight result saves. Pair order alternates to reduce ordering
bias; CPU x4 is a cloud control, never an Android hardware measurement.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from measure_durable_write import ROOT,summary

CASES=[('v2-empty',0,0,'ascii'),('v2-small',4,0,'ascii'),('v2-large',40,0,'ascii'),
       ('v2-small-archive4',4,4,'ascii'),('v2-large-archive4',40,4,'ascii'),('v2-archive16',4,16,'escaped')]

def rounded(value):
    if isinstance(value,float):return round(value,3)
    if isinstance(value,list):return [rounded(x) for x in value]
    if isinstance(value,dict):return {k:rounded(v) for k,v in value.items()}
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',default='4a74d1d');parser.add_argument('--after',default='working')
    parser.add_argument('--profiles',type=int,default=3);parser.add_argument('--writes',type=int,default=8)
    parser.add_argument('--cpu',type=float,default=4);parser.add_argument('--raw-directory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.profiles<1 or args.writes<1:parser.error('profiles/writes >=1')
    args.raw_directory.mkdir(parents=True,exist_ok=True);cases={}
    report={'method':{'beforeRef':args.before,'afterRef':args.after,'cpuThrottle':args.cpu,
      'profilesPerVariant':args.profiles,'writesPerProfile':args.writes,'syntheticOnly':True,
      'timing':'__ui.begin and actual submit click in the same page evaluation; end = strict history meta/state transaction complete. No transport roundtrip between clock start and event. DOM frames are proxies, not phone touch-to-photon.',
      'pairing':'Fresh browser process/profile per invocation. Alternating before-after / after-before pairs. Serial execution; PWA initialized and draft durable outside save timing; all measured writes offline.',
      'statistics':'Standard median, p95 nearest rank. 8 correlated writes/profile; three independent processes. Cloud CPU throttle is not Android emulation.',
      'preservation':'Within-profile before/after history/archive SHA proofs; generated IDs/timestamps may differ between profiles.'},'rawReportSha256':{},'cases':cases}
    for label,count,archive,shape in CASES:
        cases[label]={}
        for profile in range(args.profiles):
            order=['before','after'] if profile%2==0 else ['after','before']
            for side in order:
                output=args.raw_directory/f'{label}-{side}-{profile+1}.json'
                if output.exists():raise ValueError('Refusing to overwrite an existing measurement: '+str(output))
                ref=args.before if side=='before' else args.after
                print(f'BEGIN {label} {side} profile {profile+1}/{args.profiles}',flush=True)
                subprocess.run([sys.executable,str(ROOT/'scripts/measure_durable_write.py'),'--ref',ref,'--kind','v2','--count',str(count),
                    '--archive-mib',str(archive),'--archive-shape',shape,'--cpu',str(args.cpu),'--profiles','1','--writes',str(args.writes),'--output',str(output)],cwd=ROOT,check=True)
                result=json.loads(output.read_text());profiles=result['profiles']
                if len(profiles)!=1 or len(profiles[0]['samples'])!=args.writes or not profiles[0]['preserved']:raise ValueError('Incomplete result: '+str(output))
                if side not in cases[label]:cases[label][side]={**result,'profiles':[]}
                target=cases[label][side]
                if target['sourceRuntimeSha256']!=result['sourceRuntimeSha256']:raise ValueError('Runtime changed during benchmark')
                target['profiles'].append(profiles[0]);target['summary']=summary(target['profiles'])
                report['rawReportSha256'][output.name]=hashlib.sha256(output.read_bytes()).hexdigest()
                args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(rounded(report),ensure_ascii=False,indent=2)+'\n')
        for b,a in zip(cases[label]['before']['profiles'],cases[label]['after']['profiles']):
            if b['sizes']!=a['sizes']:raise ValueError('Fixture shape/size mismatch: '+label)
        print('COMPLETE '+label+' '+json.dumps({s:cases[label][s]['summary']['clickToStrictCompleteMs'] for s in ['before','after']}),flush=True)

if __name__=='__main__':main()
