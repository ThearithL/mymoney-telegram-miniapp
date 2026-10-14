import logging
from decimal import Decimal
from types import SimpleNamespace

import pytest
import requests
from sqlalchemy import MetaData, create_engine, select

from bank_rates import SOURCES, define_cache, market_quote, parse_quote


def html(row='<td>USD</td><td>KHR 4,060</td><td>KHR 4,075</td>', stamp='October 14, 2026 8:10 AM', headers='Currency,Bid,Ask'):
    return '<p>'+stamp+'</p><table><tr>'+''.join('<th>'+x+'</th>' for x in headers.split(','))+'</tr><tr>'+row+'</tr></table>'


def response(body):
    return SimpleNamespace(text=body, raise_for_status=lambda:None)


@pytest.mark.parametrize('row,headers', [
    ('<td>USD</td><td>KHR 4,060</td><td>KHR 4,075</td>', 'Currency,Bid,Ask'),
    ('<td><img src="flag.png">USD / KHR</td><td>4,060 KHR</td><td><span>4,075</span> KHR</td>', 'Currency,Buy,Sell'),
    ('<td>USD / KHR</td><td>4,075</td><td>4,060</td>', 'Currency,Sell,Buy'),
])
def test_bank_parser_accepts_real_currency_layouts_and_sell_column(row,headers):
    quote=parse_quote(html(row,headers=headers))
    assert quote['rate']==Decimal('4075')
    assert quote['quote_date']=='October 14, 2026 8:10 AM'


@pytest.mark.parametrize('row', [
    '<td>USD</td><td>JPY 4,060</td><td>JPY 4,075</td>',
    '<td>USD / EUR</td><td>4,060</td><td>4,075</td>',
    '<td>USD / KHR</td><td>4,060</td><td>-</td>',
    '<td>USD / KHR</td><td>4,060</td><td>4,000</td>',
])
def test_bank_parser_rejects_wrong_currency_and_invalid_quotes(row):
    with pytest.raises(ValueError):parse_quote(html(row))


def test_bank_parser_requires_date_and_ignores_scripts_and_unlabelled_ticker():
    with pytest.raises(ValueError):parse_quote(html(stamp='No publication date'))
    source='<script>October 1, 2026</script><table><tr><td>USD</td><td>4,000</td><td>4,010</td></tr></table>'+html(stamp='October 14, 2026&nbsp;8:10 AM')
    assert parse_quote(source)['rate']==4075
    assert parse_quote(source)['quote_date']=='October 14, 2026 8:10 AM'


@pytest.fixture
def database(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'rates.db'))
    meta=MetaData();table=define_cache(meta);meta.create_all(engine)
    yield engine,table
    engine.dispose()


def test_bank_real_quote_persists_and_failure_returns_cache(database,monkeypatch):
    engine,table=database
    monkeypatch.setattr(requests,'get',lambda *a,**k:response(html()))
    quote=market_quote(engine,table,logging.getLogger('test'))
    assert quote['live'] is True and quote['sell_rate']==4075
    assert quote['source_url']==SOURCES[0]
    def fail(*a,**k):raise requests.Timeout()
    monkeypatch.setattr(requests,'get',fail)
    # Separate SQLAlchemy engine sees the same durable cache after restart.
    restarted=create_engine(engine.url)
    cached=market_quote(restarted,table,logging.getLogger('test'))
    assert cached['live'] is False and cached['sell_rate']==4075
    assert cached['date']==quote['date'] and cached['checked_at']==quote['checked_at']
    restarted.dispose()


def test_bank_failure_without_cache_does_not_invent_a_rate(database,monkeypatch):
    engine,table=database
    monkeypatch.setattr(requests,'get',lambda *a,**k:response('<html>No rate table</html>'))
    assert market_quote(engine,table,logging.getLogger('test')) is None
    with engine.connect() as conn:assert conn.execute(select(table)).first() is None


def test_bank_fallback_parses_widget_and_does_not_roll_back_newer_quote(database,monkeypatch):
    engine,table=database
    monkeypatch.setattr(requests,'get',lambda *a,**k:response(html()))
    market_quote(engine,table,logging.getLogger('test'))
    calls=[]
    def fallback(url,**kwargs):
        calls.append(url)
        if url==SOURCES[0]:raise requests.Timeout()
        return response(html(row='<td>USD</td><td>KHR 4,062</td><td>KHR 4,078</td>',stamp='October 13, 2026 3:55 PM'))
    monkeypatch.setattr(requests,'get',fallback)
    quote=market_quote(engine,table,logging.getLogger('test'))
    assert calls==list(SOURCES)
    assert quote['live'] is False and quote['sell_rate']==4075
    with engine.begin() as conn:conn.execute(table.delete())
    quote=market_quote(engine,table,logging.getLogger('test'))
    assert quote['live'] is True and quote['sell_rate']==4078
    assert quote['source_url']==SOURCES[1]
