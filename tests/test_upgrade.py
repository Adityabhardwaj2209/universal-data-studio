import sys
from pathlib import Path
from io import BytesIO
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pytest
from src.studio_core import normalize_keys,transform,replay,aggregate,Store,schema_diff,suggest
from src.universal import profile,convert
from src.relationships import join_tables
from src.studio_exports import excel_report,pdf_report

@pytest.fixture
def sales():
    return pd.DataFrame({'id':['001','002','003'],'category':['A','A','B'],'amount':[10.,20.,0.],'cost':[5.,0.,0.],'date':pd.to_datetime(['2026-01-01','2026-01-02','2026-02-01'])})

def test_key_normalization():
    s=pd.Series([' 39.0 ','039','AB ',None,''])
    assert normalize_keys(s,numeric=True,casefold=True).iloc[:3].tolist()==['39','39','ab']
    assert normalize_keys(s).iloc[1]=='039'
    assert normalize_keys(s).iloc[3:].isna().all()

def test_join_missing_and_multiplication():
    left=pd.DataFrame({'id':['1','1','']});right=pd.DataFrame({'id':['1','1','']})
    stats,run=join_tables(left,right,['id'],['id'],'outer')
    assert stats['many_to_many'] and stats['estimated_rows']==6
    result=run();assert len(result)==6
    assert (result.join_status=='both').sum()==4

def test_normalized_join():
    l=pd.DataFrame({'id':normalize_keys(pd.Series(['39.0','43']),numeric=True)})
    r=pd.DataFrame({'id':normalize_keys(pd.Series(['39','43.0']),numeric=True)})
    info,run=join_tables(l,r,['id'],['id'],'left');assert info['unmatched_left']==0;assert len(run())==2

def test_calculated_zero_and_no_eval(sales):
    op={'kind':'calculate','name':'margin','method':'Divide','a':'amount','b':'cost'}
    result=transform(sales,op);assert result.margin.iloc[0]==2 and result.margin.iloc[1:].isna().all()
    assert 'margin' not in sales
    with pytest.raises(ValueError):transform(sales,{**op,'name':'amount'})

def test_dates(sales):
    out=transform(sales,{'kind':'calculate','name':'days','method':'Days between','a':'date','b':'date'})
    assert out.days.eq(0).all()

def test_duplicates_and_history(sales):
    op={'kind':'deduplicate','keys':['category'],'keep':'first'}
    assert len(replay(sales,[op]))==2
    assert len(replay(sales,[]))==3
    out=transform(sales,{'kind':'aggregate','keys':['category'],'measures':['amount'],'aggregation':'Sum'})
    assert out.amount.sum()==30

def test_missing_sum():
    result=aggregate(pd.DataFrame({'group':['A','A'],'value':[None,None]}),'group','value','Sum')
    assert pd.isna(result.Value.iloc[0])

def test_snapshot_isolation_and_reopen(tmp_path,sales):
    schema=pd.DataFrame({'Column':sales.columns})
    store=Store(tmp_path/'db.sqlite');key=store.save('alice','review',sales,schema,[],{'chart':{'kind':'Bar'}},[{'Field':'amount','Unit':'INR'}])
    assert not store.list('bob')
    with pytest.raises(ValueError):store.load('bob',key)
    store.delete('bob',key);restored=Store(tmp_path/'db.sqlite').load('alice',key)
    pd.testing.assert_frame_equal(restored['raw'],sales)
    assert restored['settings']['chart']['kind']=='Bar'
    store.delete('alice',key);assert not store.list('alice')

def test_refresh_and_suggestions(sales):
    raw=sales.astype(str);_,schema=profile(raw)
    missing,new=schema_diff(schema,raw.drop(columns='cost').assign(extra='x'))
    assert missing==['cost'] and new==['extra']
    typed,issues=convert(raw,schema);plans=suggest(typed,schema)
    assert plans and len(plans)<=4
    assert all(p['measure']!='id' for p in plans)

def test_exports(sales,tmp_path):
    from openpyxl import load_workbook
    _,schema=profile(sales.astype(str))
    special=sales.copy();special.loc[0,'category']='=1+1'
    xlsx=excel_report(special,schema,[],[],aggregate(sales,'category','amount','Sum'))
    wb=load_workbook(BytesIO(xlsx));assert wb['Data']['B2'].data_type=='s';assert wb['Data']['B2'].value.startswith("'")
    pdf=pdf_report(sales,'Sales review',[],aggregate(sales,'category','amount','Sum'))
    assert pdf.startswith(b'%PDF')
    (tmp_path/'report.pdf').write_bytes(pdf)

def test_real_football_files():
    folder=Path(__file__).resolve().parents[2]/'upload'
    if not (folder/'players_summary.csv').exists():pytest.skip('External football fixtures not bundled')
    for name,rows in [('players_summary.csv',1468),('matches.csv',156),('teams_summary.csv',54)]:
        raw=pd.read_csv(folder/name,dtype=str,keep_default_na=False);_,schema=profile(raw);typed,issues=convert(raw,schema)
        assert len(typed)==rows
        assert schema.set_index('Column').loc['player_id' if 'player_id' in raw else 'match_id' if 'match_id' in raw else 'team_id','Role']=='Identifier'
