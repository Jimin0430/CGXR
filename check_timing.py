import re

def get_timing(path):
    try:
        with open(path, 'rb') as f:
            data = f.read().decode('utf-8', errors='replace')
        lines = re.split(r'[\r\n]+', data)
        relevant = [l for l in lines if any(k in l for k in ['Training complete', 'DONE', 'Saving', 'Size =', 'All done', 'ITER', 'Stage', 'it/s', 'elapsed'])]
        # Also grab tqdm final line (100%)
        tqdm_finals = [l for l in lines if '100%' in l and 'it/s' in l]
        return (relevant[-6:] if len(relevant) > 6 else relevant) + (tqdm_finals[-2:] if tqdm_finals else [])
    except Exception as e:
        return [str(e)]

for name, path in [
    ('0_train (3DGS)', 'D:/JM/cgxr/CGXR/train_log.txt'),
    ('1_stage1 (Prune+Finetune)', 'D:/JM/cgxr/CGXR/stage1_log.txt'),
    ('2_stage2 (SH Distill)', 'D:/JM/cgxr/CGXR/stage2_log.txt'),
    ('3_stage3 (VecTree Quant)', 'D:/JM/cgxr/CGXR/stage3_log.txt'),
]:
    print(f'\n=== {name} ===')
    for l in get_timing(path):
        if l.strip():
            print(l)
