"""Deterministic operations shared by the Universal Studio UI and tests."""
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from pathlib import Path
import json
import sqlite3
import pandas as pd


def normalize_keys(series, trim=True, casefold=False, numeric=False):
    def normalize(value):
        if pd.isna(value):
            return pd.NA
        value = str(value).strip() if trim else str(value)
        if not value:
            return pd.NA
        if numeric:
            try:
                number = Decimal(value)
                if number.is_finite():
                    value = format(number.normalize(), 'f')
            except InvalidOperation:
                pass
        return value.casefold() if casefold else value
    return series.map(normalize).astype('string')


def aggregate(data, group, measure=None, operation='Mean'):
    source = data.dropna(subset=[group])
    if measure is None:
        return source.groupby(group, dropna=True).size().rename('Value').reset_index()
    grouped = source.groupby(group, dropna=True)[measure]
    if operation == 'Sum':
        result = grouped.sum(min_count=1)
    else:
        method = {'Mean':'mean','Median':'median','Max':'max','Min':'min','Count':'count','Distinct':'nunique'}[operation]
        result = getattr(grouped, method)()
    return result.rename('Value').reset_index()


def transform(data, operation):
    result = data.copy()
    kind = operation['kind']
    if kind == 'deduplicate':
        keys = operation['keys']
        if not keys:
            raise ValueError('Select duplicate keys.')
        return result.drop_duplicates(keys, keep=operation['keep']).reset_index(drop=True)
    if kind == 'aggregate':
        keys = operation['keys']
        measures = operation['measures']
        if not keys or not measures or set(keys) & set(measures):
            raise ValueError('Choose separate grouping keys and measures.')
        if operation['aggregation'] == 'Sum':
            return result.groupby(keys, dropna=False)[measures].sum(min_count=1).reset_index()
        method = {'Mean':'mean','Max':'max','Min':'min','Median':'median'}[operation['aggregation']]
        return result.groupby(keys, dropna=False)[measures].agg(method).reset_index()
    if kind == 'calculate':
        name = operation['name'].strip()
        if not name or name in result.columns:
            raise ValueError('Use a new, non-empty field name.')
        a, b = result[operation['a']], result[operation['b']]
        method = operation['method']
        if method == 'Days between':
            values = (pd.to_datetime(a, errors='coerce') - pd.to_datetime(b, errors='coerce')).dt.total_seconds()/86400
        else:
            a = pd.to_numeric(a, errors='coerce')
            b = pd.to_numeric(b, errors='coerce')
            if method == 'Add': values = a+b
            elif method == 'Subtract': values = a-b
            elif method == 'Multiply': values = a*b
            else:
                values = a / b.where(b.ne(0))
                if method == 'Percentage': values *= 100
        result[name] = values.replace([float('inf'),-float('inf')], float('nan'))
        return result
    raise ValueError('Unknown transformation.')


def replay(base, operations):
    data = base.copy()
    for operation in operations:
        data = transform(data, operation)
    return data


def schema_diff(schema, frame):
    expected = set(schema['Column'])
    actual = set(frame.columns)
    return sorted(expected-actual), sorted(actual-expected)


def suggest(data, schema):
    measures = [c for c in data if c in set(schema.loc[schema.Role.eq('Measure'),'Column']) and pd.api.types.is_numeric_dtype(data[c])]
    dates = [c for c in data if pd.api.types.is_datetime64_any_dtype(data[c])]
    categories = [c for c in data if c not in measures+dates and data[c].nunique() > 1 and not str(c).lower().endswith(('_id','_code'))]
    categories.sort(key=lambda c: (not str(c).lower().endswith('name'), data[c].nunique()))
    plans=[]
    for i, measure in enumerate(measures[:4]):
        row = schema.loc[schema.Column.eq(measure)].iloc[0]
        operation = row.Aggregation if row.Aggregation in ['Sum','Mean','Median','Min','Max'] else 'Mean'
        if dates and i == 0:
            plans.append({'group':dates[0], 'measure':measure, 'operation':operation,'kind':'Line'})
        elif categories:
            plans.append({'group':categories[min(i,len(categories)-1)],'measure':measure,'operation':operation,'kind':'Bar'})
    if not plans and categories:
        plans.append({'group':categories[0],'measure':None,'operation':'Count','kind':'Bar'})
    return plans


def safe_excel(frame):
    result=frame.copy()
    for col in result:
        result[col]=result[col].map(lambda x: "'"+x if isinstance(x,str) and x.lstrip().startswith(('=','+','-','@')) else x)
    return result


class Store:
    def __init__(self, path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as con:
            con.execute('CREATE TABLE IF NOT EXISTS studio_snapshots (id INTEGER PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL, payload TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP)')
    def connect(self): return sqlite3.connect(self.path)
    def save(self,owner,name,raw,schema,operations,settings,dictionary):
        if not owner or not name.strip(): raise ValueError('Account and name required.')
        payload=json.dumps({'raw':raw.to_json(orient='table',date_format='iso',index=False),'schema':schema.to_dict('records'),'operations':operations,'settings':settings,'dictionary':dictionary})
        with self.connect() as con:
            cursor=con.execute('INSERT INTO studio_snapshots(owner,name,payload) VALUES (?,?,?)',(owner,name.strip(),payload))
            return cursor.lastrowid
    def list(self,owner):
        with self.connect() as con:
            return con.execute('SELECT id,name,created FROM studio_snapshots WHERE owner=? ORDER BY id DESC',(owner,)).fetchall()
    def load(self,owner,key):
        with self.connect() as con:
            row=con.execute('SELECT payload FROM studio_snapshots WHERE id=? AND owner=?',(key,owner)).fetchone()
        if row is None: raise ValueError('Snapshot unavailable for this account.')
        payload=json.loads(row[0]); payload['raw']=pd.read_json(StringIO(payload['raw']),orient='table');payload['schema']=pd.DataFrame(payload['schema'])
        return payload
    def delete(self,owner,key):
        with self.connect() as con: con.execute('DELETE FROM studio_snapshots WHERE id=? AND owner=?',(key,owner))
