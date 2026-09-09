"""New-run point estimates. Tiny smoke samples do not support quality claims."""
from collections import Counter
from .review_bundle import METRICS


def summarize(planned,accepted):
    means={}
    for candidate in planned['conditions']:
        scores=[r for r in accepted['score'].values() if r['candidate_id']==candidate and r['replicate']==1]
        means[candidate]={metric:sum(r['dimensions'][metric] for r in scores)/len(scores) for metric in METRICS}
    counts={}
    for candidate in planned['conditions']:
        ranks=[r for r in accepted['rank'].values() if r['candidate_id']==candidate and r['pass_id']=='primary']
        if not ranks:
            continue
        counter=Counter()
        for row in ranks:
            positions={role:i for i,group in enumerate(row['rank_groups']) for role in group}
            delta=positions['matching_compressed']-positions['raw']
            counter['above' if delta<0 else 'below' if delta>0 else 'tied']+=1
        counts[candidate]={'questions':len(ranks),**{k:counter[k] for k in ('below','tied','above')}}
    return {'kind':'hosted_replication','mode':planned['mode'],'questions':len(planned['rows']),
            'means':means,'compressed_vs_raw':counts,'repeats_averaged_into_primary':False,
            'quality_reproduction_established':False,'compression_recomputed':False}


def full_statistics(planned,accepted,protocol):
    from .statistics import _contrasts
    averaged={}; clusters={r['id']:r['cluster'] for r in planned['rows']}
    for row in accepted['score'].values():
        if row['replicate']==1:
            averaged[(row['row_id'],row['candidate_id'])]={**row['dimensions'],'overall_score':row['overall_score']}
    candidates=[c for c in planned['conditions'] if c not in ('raw','no_context','oracle_bgb_paragraph_ids')]
    return _contrasts(averaged=averaged,clusters=clusters,row_ids=sorted(clusters),candidates=candidates,
        bootstrap_replicates=protocol['statistics']['context_cluster_bootstrap_replicates'],
        randomizations=protocol['statistics']['context_cluster_sign_randomizations'],seed=protocol['seed'])
