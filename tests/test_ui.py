import sys
from pathlib import Path
from streamlit.testing.v1 import AppTest
ROOT=Path(__file__).resolve().parents[1]
SCRIPT='''
import sys
sys.path.insert(0,ROOT)
import streamlit as st
import pandas as pd
from src.universal import profile
from src.studio_app import render
st.session_state['account_email']='ui_test@example.invalid'
if 'studio_v2_ui_test@example.invalid' not in st.session_state:
    raw=pd.DataFrame({'team_name':['A','B','A'],'goals':['2','3','4'],'date':['2026-01-01','2026-01-02','2026-02-01']})
    _,schema=profile(raw)
    st.session_state['studio_v2_ui_test@example.invalid']={'raw':raw,'schema':schema,'operations':[],'settings':{},'dictionary':[],'revision':'test','redo':[],'token':'uitest'}
render()
'''.replace('ROOT',repr(str(ROOT)))

def test_workspace_renders_and_calculates():
    at=AppTest.from_string(SCRIPT,default_timeout=30).run()
    assert not at.exception, str(at.exception)
    assert any(x.label=='Selected rows' and x.value=='3' for x in at.metric)
    suggestions=[b for b in at.button if b.label.startswith('Apply suggestion')]
    assert suggestions
    suggestions[0].click().run()
    assert not at.exception,str(at.exception)
    assert any(x.label=='Chart format' for x in at.selectbox)

def test_calculation_preview_apply_undo():
    at=AppTest.from_string(SCRIPT,default_timeout=30).run()
    next(x for x in at.radio if x.label=='Transformation').set_value('Calculated field').run()
    next(x for x in at.text_input if x.label=='New field name').set_value('net')
    next(x for x in at.button if x.label=='Preview transformation').click().run()
    assert not at.exception,str(at.exception)
    next(x for x in at.button if x.label=='Apply transformation').click().run()
    assert not at.exception,str(at.exception)
    next(x for x in at.button if x.label=='Undo').click().run()
    assert not at.exception,str(at.exception)

def test_all_chart_formats_and_exports():
    at=AppTest.from_string(SCRIPT,default_timeout=40).run()
    next(x for x in at.selectbox if x.label=='Measure').set_value('goals').run()
    for kind in ['Line','Area','Donut','Histogram','Scatter','Bar']:
        next(x for x in at.selectbox if x.label=='Chart format').set_value(kind).run()
        assert not at.exception,str(at.exception)
    next(x for x in at.button if x.label=='Prepare PDF and Excel exports').click().run()
    assert not at.exception,str(at.exception)
    state=at.session_state['studio_v2_ui_test@example.invalid']
    assert state['exports']['pdf'].startswith(b'%PDF')
    assert state['exports']['xlsx'].startswith(b'PK')

def test_snapshot_save_and_reopen_without_upload():
    at=AppTest.from_string(SCRIPT,default_timeout=30).run()
    next(x for x in at.button if x.label=='Save dataset snapshot').click().run()
    assert not at.exception,str(at.exception)
    next(x for x in at.button if x.label=='Open snapshot').click().run()
    assert not at.exception,str(at.exception)
    assert any(x.label=='Selected rows' and x.value=='3' for x in at.metric)
    next(x for x in at.checkbox if x.label=='Confirm deletion').set_value(True).run()
    next(x for x in at.button if x.label=='Delete snapshot').click().run()
    assert not at.exception,str(at.exception)
