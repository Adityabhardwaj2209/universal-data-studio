"""Integrated Universal Studio: explicit schema, reproducible transformations."""
from io import BytesIO
from pathlib import Path
import hashlib
import json
import uuid
import pandas as pd
import streamlit as st
import altair as alt
from .studio_core import Store,transform,replay,aggregate,suggest,schema_diff,safe_excel


def read_upload(upload,key):
    if upload.size>20*1024*1024:raise ValueError('File limit: 20 MB.')
    if upload.name.lower().endswith('.xlsx'):
        with pd.ExcelFile(BytesIO(upload.getvalue())) as book:
            sheet=st.selectbox('Worksheet',book.sheet_names,key=key+'_sheet')
            data=pd.read_excel(book,sheet_name=sheet,dtype=str,keep_default_na=False)
    else:
        sep=st.selectbox('CSV separator',[',',';','\t'],key=key+'_sep')
        encoding=st.selectbox('Encoding',['utf-8-sig','cp1252','latin1'],key=key+'_enc')
        data=pd.read_csv(BytesIO(upload.getvalue()),sep=sep,encoding=encoding,dtype=str,keep_default_na=False)
    data.columns=[str(c).strip() for c in data]
    if data.empty or data.columns.duplicated().any():raise ValueError('Use nonempty data with unique column names.')
    if len(data)>100000 or len(data.columns)>300:raise ValueError('Limit: 100,000 rows and 300 fields.')
    return data.reset_index(drop=True)


def validate_schema(schema):
    from .universal import TYPES,ROLES,AGGREGATIONS,FORMATS
    for field,allowed in [('Type',TYPES),('Role',ROLES),('Aggregation',AGGREGATIONS),('Number format',FORMATS)]:
        if not schema[field].isin(allowed).all():raise ValueError('Invalid '+field)
    if schema.Column.duplicated().any():raise ValueError('Duplicate schema fields.')
    for _,r in schema.iterrows():
        if r.Role=='Measure' and r.Type!='Number':raise ValueError(r.Column+': Measure requires Number.')
        if r.Role=='Date' and r.Type!='Date':raise ValueError(r.Column+': Date role requires Date type.')
        if r.Role in ['Identifier','Category','Ignore'] and r.Aggregation not in ['None','Count','Distinct']:raise ValueError(r.Column+': choose None, Count or Distinct.')
    if schema.Role.eq('Ignore').all():raise ValueError('Keep at least one field.')


def render():
    from .universal import profile,convert,TYPES,ROLES,FORMATS,AGGREGATIONS
    st.header('Universal Data Studio')
    if st.session_state.get('studio_flash'):st.success(st.session_state.pop('studio_flash'))
    owner=st.session_state.get('account_email')
    if not owner:st.info('Sign in to open your private workspace.');return
    state_key='studio_v2_'+owner
    store=Store(Path(__file__).resolve().parent.parent/'private'/'studio_v2.db')
    workflow=st.radio('Workflow',['Dataset workspace','Connect datasets'],horizontal=True,key='studio_v2_workflow')
    if workflow=='Connect datasets':
        from .relationships import render_relationships
        render_relationships();return
    with st.expander('Open saved dataset snapshots',expanded=state_key not in st.session_state):
        saved=store.list(owner)
        if saved:
            labels={r[0]:f'{r[1]} | {r[2]} UTC' for r in saved}
            selected=st.selectbox('Snapshot',list(labels),format_func=labels.get)
            a,b=st.columns(2)
            if a.button('Open snapshot'):
                state=store.load(owner,selected);state['revision']=uuid.uuid4().hex;state['redo']=[]
                state['token']=uuid.uuid4().hex;st.session_state[state_key]=state;st.rerun()
            confirm=b.checkbox('Confirm deletion')
            if b.button('Delete snapshot',disabled=not confirm):store.delete(owner,selected);st.rerun()
        else:st.caption('No snapshots yet. Saved snapshots include dataset rows and reopen without upload.')
    upload=st.file_uploader('Open CSV or Excel dataset',type=['csv','xlsx'],key='studio_v2_upload')
    if upload:
        raw=read_upload(upload,'studio_read')
        if st.button('Start a new dataset from this file',type='primary'):
            st.session_state[state_key]={'raw':raw,'schema':None,'operations':[],'settings':{},'dictionary':[], 'revision':uuid.uuid4().hex,'redo':[],'token':uuid.uuid4().hex}
            st.rerun()
    if state_key not in st.session_state:st.info('Upload a dataset or open a snapshot.');return
    state=st.session_state[state_key];raw=state['raw'];token=state['token'];schema=state['schema']
    summary,automatic=profile(raw)
    with st.expander('Dataset profiler / schema editor',expanded=schema is None):
        st.dataframe(summary,hide_index=True)
        imported=st.file_uploader('Optional schema profile JSON',type=['json'],key=token+'_schemafile')
        defaults=schema if schema is not None else automatic
        if imported:
            candidate=pd.DataFrame(json.loads(imported.getvalue()))
            required=set(automatic.columns)
            if not required.issubset(candidate.columns) or set(candidate.Column)!=set(raw.columns):st.error('Profile fields do not match this dataset.')
            else:defaults=candidate.set_index('Column').loc[list(raw.columns)].reset_index()
        with st.form(token+'_schema'):
            edited=st.data_editor(defaults,num_rows='fixed',hide_index=True,disabled=['Column'],column_config={
                'Type':st.column_config.SelectboxColumn(options=TYPES,required=True),
                'Role':st.column_config.SelectboxColumn(options=ROLES,required=True),
                'Aggregation':st.column_config.SelectboxColumn(options=AGGREGATIONS,required=True),
                'Number format':st.column_config.SelectboxColumn(options=FORMATS,required=True)})
            submit=st.form_submit_button('Confirm schema')
        if submit:
            validate_schema(edited);state['schema']=edited.copy();state['operations']=[];state['redo']=[];state['settings']={};state['revision']=uuid.uuid4().hex;st.rerun()
        st.caption('Dates: %Y-%m-%d or %d/%m/%Y. Schema changes reset transformations and chart selections.')
    if schema is None:return
    base,issues=convert(raw,schema)
    data=replay(base,state['operations'])
    if not issues.empty:
        st.warning(f'{len(issues):,} conversion issues. Unconvertible values remain missing.')
        with st.expander('Conversion issues'):st.dataframe(issues.head(200));st.download_button('Download issues',safe_excel(issues).to_csv(index=False).encode('utf-8-sig'),'issues.csv')
    if 'source_stat_category' in data:st.warning('Multiple source categories: verify entity grain before summing statistics.')
    transformation_panel(state,data)
    with st.expander('Refresh dataset using the saved schema'):
        refresh=st.file_uploader('Replacement CSV / Excel',type=['csv','xlsx'],key=token+'_refresh')
        if refresh:
            incoming=read_upload(refresh,'refresh_read');missing,added=schema_diff(schema,incoming)
            st.write({'Missing fields':missing,'New fields':added,'Current rows':len(raw),'Incoming rows':len(incoming)})
            if not missing:
                if st.button('Validate refresh and preview'):
                    next_base,next_issues=convert(incoming,schema);next_data=replay(next_base,state['operations'])
                    state['refresh_preview']={'hash':hashlib.sha256(incoming.to_csv(index=False).encode()).hexdigest(),'issues':len(next_issues),'rows':len(next_data)}
                preview=state.get('refresh_preview')
                if preview and preview['hash']==hashlib.sha256(incoming.to_csv(index=False).encode()).hexdigest():
                    st.write(preview)
                    st.caption('New fields are retained in the source; edit the schema to include them. Existing operations are replayed.')
                    if st.button('Apply refresh'):
                        # Extend schema with explicitly ignored new fields.
                        if added:
                            _,new_schema=profile(incoming[added]);new_schema['Role']='Ignore';new_schema['Aggregation']='None';state['schema']=pd.concat([schema,new_schema],ignore_index=True)
                        state['raw']=incoming;state['revision']=uuid.uuid4().hex;state['redo']=[];state.pop('refresh_preview',None);st.rerun()
            else:st.error('Refresh blocked: required fields are missing. Start a new dataset or correct the source.')
    dictionary_panel(state,data)
    filtered=filter_panel(data,state)
    if filtered.empty:st.info('No records match filters.');return
    numeric=[c for c in filtered if pd.api.types.is_numeric_dtype(filtered[c]) and not pd.api.types.is_bool_dtype(filtered[c]) and (c not in set(schema.Column) or schema.set_index('Column').loc[c,'Role']=='Measure')]
    a,b,c=st.columns(3);a.metric('Selected rows',len(filtered));b.metric('Fields',len(filtered.columns));c.metric('Missing cells',int(filtered.isna().sum().sum()))
    chart_data,chart=dashboard_panel(filtered,schema,state,numeric)
    with st.expander('Save snapshot / export'):
        name=st.text_input('Snapshot / report name','My dataset review',key=token+'_name')
        if st.button('Save dataset snapshot'):
            store.save(owner,name,state['raw'],state['schema'],state['operations'],state['settings'],state['dictionary']);st.session_state['studio_flash']='Dataset and configuration saved.';st.rerun()
        st.download_button('Download schema profile',schema.to_json(orient='records',indent=2).encode(),'schema_profile.json','application/json')
        st.download_button('Download filtered CSV',safe_excel(filtered).to_csv(index=False).encode('utf-8-sig'),'filtered_data.csv','text/csv')
        if st.button('Prepare PDF and Excel exports'):
            from .studio_exports import excel_report,pdf_report
            png=chart.to_dict() if chart is not None else None
            png_bytes=None
            if png:
                import vl_convert as vlc
                png_bytes=vlc.vegalite_to_png(png,scale=1.5)
            state['exports']={'signature':export_signature(filtered,state,name),'xlsx':excel_report(filtered,schema,state['operations'],state['dictionary'],chart_data),'pdf':pdf_report(filtered,name,state['operations'],chart_data,png_bytes)}
        ready=state.get('exports')
        if ready and ready['signature']==export_signature(filtered,state,name):
            st.download_button('Download Excel',ready['xlsx'],'dataset_report.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            st.download_button('Download PDF',ready['pdf'],'dataset_report.pdf','application/pdf')


def export_signature(data,state,name):
    return hashlib.sha256(data.to_csv(index=False).encode()+json.dumps([state['settings'],state['operations'],state['dictionary'],name],sort_keys=True).encode()).hexdigest()


def commit(state,operation):
    state['operations'].append(operation);state['redo']=[];state['revision']=uuid.uuid4().hex;st.rerun()


def transformation_panel(state,data):
    with st.expander('Clean, calculate and undo transformations'):
        a,b=st.columns(2)
        if a.button('Undo',disabled=not state['operations']):state['redo'].append(state['operations'].pop());state['revision']=uuid.uuid4().hex;st.rerun()
        if b.button('Redo',disabled=not state['redo']):state['operations'].append(state['redo'].pop());state['revision']=uuid.uuid4().hex;st.rerun()
        st.dataframe(pd.DataFrame([{'Step':i+1,'Operation':str(o)} for i,o in enumerate(state['operations'])]),hide_index=True)
        action=st.radio('Transformation',['Resolve duplicates','Calculated field'],horizontal=True)
        operation=None
        if action=='Resolve duplicates':
            keys=st.multiselect('Duplicate keys',list(data.columns))
            if keys:
                duplicates=data.duplicated(keys,keep=False);st.write(f'{int(duplicates.sum())} rows share duplicate keys.');st.dataframe(data.loc[duplicates].head(100))
                policy=st.selectbox('Resolution',['Keep first','Keep last','Aggregate'])
                if policy=='Aggregate':
                    measures=st.multiselect('Numeric fields to aggregate',[c for c in data if pd.api.types.is_numeric_dtype(data[c]) and c not in keys]);agg=st.selectbox('Aggregation',['Mean','Sum','Max','Min','Median'])
                    operation={'kind':'aggregate','keys':keys,'measures':measures,'aggregation':agg}
                    st.caption('Output contains selected grouping keys and measures only. Other fields are removed.')
                else:operation={'kind':'deduplicate','keys':keys,'keep':'first' if policy=='Keep first' else 'last'}
        else:
            name=st.text_input('New field name');method=st.selectbox('Operation',['Subtract','Add','Multiply','Divide','Percentage','Days between'])
            candidates=[c for c in data if pd.api.types.is_datetime64_any_dtype(data[c])] if method=='Days between' else [c for c in data if pd.api.types.is_numeric_dtype(data[c])]
            if candidates:
                a=st.selectbox('Field A',candidates);b=st.selectbox('Field B',candidates)
                operation={'kind':'calculate','name':name,'method':method,'a':a,'b':b}
                st.caption('A operation B. Percentage = A/B × 100. Zero divisors become missing values.')
        if operation is not None:
            if st.button('Preview transformation'):
                preview=transform(data,operation);state['pending']={'operation':operation,'revision':state['revision']}
            pending=state.get('pending')
            if pending and pending['operation']==operation and pending['revision']==state['revision']:
                preview=transform(data,operation);st.write(f'{len(data)} → {len(preview)} rows');st.dataframe(preview.head(100))
                if st.button('Apply transformation'):commit(state,operation)


def dictionary_panel(state,data):
    with st.expander('Data dictionary'):
        old={r['Field']:r for r in state['dictionary']}
        dictionary=pd.DataFrame([old.get(c,{'Field':c,'Description':'','Unit':''}) for c in data])
        edited=st.data_editor(dictionary,disabled=['Field'],hide_index=True,key=state['token']+'_dictionary_'+state['revision'])
        if st.button('Save dictionary'):state['dictionary']=edited.to_dict('records');st.success('Dictionary saved in this workspace. Save a snapshot to persist it.')


def filter_panel(data,state):
    settings=state['settings'];view=data.copy();prefix=state['token']+state['revision']
    with st.expander('Filters'):
        columns=list(data.columns);default=[c for c in settings.get('filter_fields',[]) if c in columns]
        chosen=st.multiselect('Filter fields',columns,default=default,key=prefix+'_fields');settings['filter_fields']=chosen
        for col in chosen:
            values=settings.setdefault('filters',{}).get(col,{})
            if pd.api.types.is_numeric_dtype(data[col]):
                lo=st.text_input(col+' minimum (blank = no bound)',str(values.get('lo','')),key=prefix+col+'_lo');hi=st.text_input(col+' maximum',str(values.get('hi','')),key=prefix+col+'_hi')
                settings['filters'][col]={'lo':lo,'hi':hi}
                if lo:view=view[view[col]>=float(lo)]
                if hi:view=view[view[col]<=float(hi)]
            elif pd.api.types.is_datetime64_any_dtype(data[col]):
                lo=st.text_input(col+' from YYYY-MM-DD',values.get('lo',''),key=prefix+col+'_lo');hi=st.text_input(col+' through YYYY-MM-DD',values.get('hi',''),key=prefix+col+'_hi');settings['filters'][col]={'lo':lo,'hi':hi}
                if lo:view=view[view[col]>=pd.Timestamp(lo)]
                if hi:view=view[view[col]<pd.Timestamp(hi)+pd.Timedelta(days=1)]
            else:
                query=st.text_input(col+' contains',values.get('query',''),key=prefix+col);settings['filters'][col]={'query':query}
                if query:view=view[view[col].astype('string').str.contains(query,case=False,regex=False,na=False)]
    return view


def dashboard_panel(data,schema,state,numeric):
    settings=state['settings'];prefix=state['token']+state['revision'];columns=list(data.columns)
    st.subheader('Suggested dashboards')
    plans=suggest(data,schema)
    for i,plan in enumerate(plans):
        label=f"{plan['kind']}: {plan['operation']} of {plan['measure'] or 'rows'} by {plan['group']}"
        if st.button('Apply suggestion: '+label,key=prefix+'_suggest'+str(i)):
            settings['chart']=plan;state['revision']=uuid.uuid4().hex;st.rerun()
    st.caption('Suggestions are heuristics. Review the aggregation and entity grain, especially for repeated statistics.')
    selected=st.multiselect('KPI measures',numeric,default=[c for c in settings.get('kpis',numeric[:2]) if c in numeric][:4],max_selections=4,key=prefix+'_kpis');settings['kpis']=selected
    methods=['Mean','Sum','Median','Max','Min','Count','Distinct']
    for col,card in zip(selected,st.columns(max(1,len(selected)))):
        op=card.selectbox(col+' KPI operation',methods,index=methods.index(settings.get('kpi_ops',{}).get(col,'Mean')),key=prefix+'_kop'+col);settings.setdefault('kpi_ops',{})[col]=op
        vals=data[col];val=vals.sum(min_count=1) if op=='Sum' else getattr(vals,{'Mean':'mean','Median':'median','Max':'max','Min':'min','Count':'count','Distinct':'nunique'}[op])();card.metric(col,'No values' if pd.isna(val) else f'{val:,.2f}')
    cfg=settings.get('chart',{})
    kinds=['Bar','Line','Area','Donut','Scatter','Histogram'];kind=st.selectbox('Chart format',kinds,index=kinds.index(cfg.get('kind','Bar')),key=prefix+'_kind')
    group=st.selectbox('X / grouping field',columns,index=columns.index(cfg.get('group')) if cfg.get('group') in columns else 0,key=prefix+'_group')
    options=['Row count']+numeric;measure=st.selectbox('Measure',options,index=options.index(cfg.get('measure')) if cfg.get('measure') in options else 0,key=prefix+'_measure');measure=None if measure=='Row count' else measure
    op=st.selectbox('Calculation',methods,index=methods.index(cfg.get('operation','Mean')) if cfg.get('operation') in methods else 0,key=prefix+'_operation')
    settings['chart']={'kind':kind,'group':group,'measure':measure,'operation':op}
    limit=st.selectbox('Display limit',[10,20,50,100],key=prefix+'_limit')
    grouped=None;chart=None;plot=data
    if kind in ['Scatter','Histogram']:
        if not measure:st.info('Choose a numeric measure.')
        elif kind=='Scatter':
            if not pd.api.types.is_numeric_dtype(data[group]):st.info('Choose a numeric X field.')
            else:
                plot=pd.DataFrame({'X':data[group],'Value':data[measure]}).dropna();chart=alt.Chart(plot.head(5000)).mark_circle(opacity=.6).encode(x=alt.X('X:Q',title=group),y=alt.Y('Value:Q',title=measure),tooltip=['X','Value']).interactive();st.caption('Scatter displays up to 5,000 records; filters and exports use all selected records.')
        else:chart=alt.Chart(pd.DataFrame({'Value':data[measure].dropna()})).mark_bar().encode(x=alt.X('Value:Q',bin=True,title=measure),y='count()')
    else:
        source=pd.DataFrame({'_dimension':data[group]})
        if measure is not None: source['_measure']=data[measure]
        grouped=aggregate(source,'_dimension','_measure' if measure is not None else None,op).rename(columns={'_dimension':'Group'}).dropna(subset=['Value'])
        if pd.api.types.is_datetime64_any_dtype(data[group]) or kind in ['Line','Area']:visible=grouped.sort_values('Group').head(limit)
        else:visible=grouped.sort_values('Value',ascending=False).head(limit)
        st.caption(f'{len(visible)} of {len(grouped)} groups displayed. Null group keys omitted; missing measures are not zero-filled.')
        plot=alt.Chart(visible)
        if kind=='Donut':
            if visible.empty or (visible.Value<0).any() or visible.Value.sum()<=0:st.warning('Donut requires a positive total and no negative values.')
            else:chart=plot.mark_arc(innerRadius=70).encode(theta='Value:Q',color='Group:N',tooltip=['Group','Value']);st.caption('Shares are for displayed groups only.')
        else:
            chart=(plot.mark_bar() if kind=='Bar' else plot.mark_line(point=True) if kind=='Line' else plot.mark_area()).encode(x=alt.X('Group:T' if pd.api.types.is_datetime64_any_dtype(data[group]) else 'Group:N',sort=None,title=group),y=alt.Y('Value:Q',title=(op+' '+measure) if measure else 'Rows'),tooltip=['Group','Value'])
    if chart is not None:
        chart=chart.properties(height=350).configure_axis(labelFontWeight='bold',titleFontWeight='bold')
        if kind in ['Bar','Line','Area']:
            # Vega selection drives a detail table; Altair uses field names without dataset-specific syntax.
            selection=alt.selection_point(fields=['Group'],name='drill')
            event=st.altair_chart(chart.add_params(selection),use_container_width=True,on_select='rerun',key=prefix+'_drill')
            records=event.selection.get('drill',[])
            if records:
                values=[r['Group'] for r in records if 'Group' in r]
                if pd.api.types.is_datetime64_any_dtype(data[group]):values=pd.to_datetime(values,unit='ms') if values and isinstance(values[0],(int,float)) else pd.to_datetime(values)
                details=data[data[group].isin(values)];st.write(f'Drill-down: {len(details)} records');st.dataframe(details,hide_index=True)
        else:st.altair_chart(chart,use_container_width=True)
    with st.expander('Filtered table and grouped values'):
        st.dataframe(data,hide_index=True)
        if grouped is not None:st.dataframe(grouped,hide_index=True)
    return grouped,chart
