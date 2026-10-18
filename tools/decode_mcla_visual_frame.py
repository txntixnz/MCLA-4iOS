#!/usr/bin/env python3
"""Decode an exported VisualFrame directory without needing the game files."""
import argparse,collections,csv,json,pathlib,struct

def decode(root,output):
    m=json.loads((root/'manifest.json').read_text())
    if m.get('schema')!=1 or not m.get('gpu_completed') or m.get('draw_record_bytes')!=936:
        raise ValueError('Unsupported or incomplete capture')
    raw=(root/'draws.bin').read_bytes();banks=(root/'constants.bin').read_bytes()
    if len(raw)!=m['draw_count']*936 or len(raw)>8192*936 or len(banks)!=m['constant_banks']*4096 or len(banks)>256*4096:
        raise ValueError('Invalid trace size')
    output.mkdir(parents=True,exist_ok=True)
    pairs=collections.Counter()
    with (output/'draws.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['draw','vs','ps','primitive','count','surface','width','height','format','color_info','native_format','base','sample_type','logical_width','logical_height','vs_bank','ps_bank']+[f'state_{o}' for o in m['state_offsets']])
        for at in range(0,len(raw),936):
            draw,vs,ps=struct.unpack_from('<QQQ',raw,at)
            fields=struct.unpack_from('<12I',raw,at+24)
            state=struct.unpack_from('<32I',raw,at+72)
            bank_ids=struct.unpack_from('<2I',raw,at+928)
            for b in bank_ids:
                if b!=0xFFFFFFFF and b>=m['constant_banks']: raise ValueError('Invalid constant-bank reference')
            pairs[(vs,ps)]+=1
            w.writerow([draw,f'{vs:016X}',f'{ps:016X}',*fields,*bank_ids,*[f'{v:08X}' for v in state]])
    if len(m['images'])>8:raise ValueError('Too many snapshots')
    import numpy as np
    from PIL import Image
    for item in m['images']:
        name=item['file']
        if pathlib.PurePath(name).name!=name or name not in [f'image-{i:02d}.bin' for i in range(8)]: raise ValueError('Unsafe snapshot name')
        data=(root/name).read_bytes()
        if len(data)!=item['bytes'] or len(data)>16*1024*1024:raise ValueError('Invalid snapshot size')
        half=item['format']=='rgba16f-le';pixel_bytes=8 if half else 4
        rows=np.frombuffer(data,dtype=np.uint8).reshape(item['height'],item['row_bytes'])
        tight=rows[:,:item['width']*pixel_bytes].copy()
        if half:
            pixels=np.nan_to_num(tight.view('<f2').astype(np.float32),nan=0,posinf=1,neginf=0)
            tight=(np.clip(pixels,0,1)*255).astype('uint8')
        image=tight.reshape(item['height'],item['width'],4)
        Image.fromarray(image,'RGBA').save(output/(pathlib.Path(name).stem+'.png'))
    summary={'build':m['build'],'frame':m['frame'],'draws':m['draw_count'],
        'truncated':m['truncated'],'images':m['images'],
        'shader_pairs':[{'vs':f'{v:016X}','ps':f'{p:016X}','draws':n} for (v,p),n in pairs.most_common()]}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ['build','frame','draws','truncated']}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('capture',type=pathlib.Path);p.add_argument('output',type=pathlib.Path)
    a=p.parse_args();decode(a.capture,a.output)
