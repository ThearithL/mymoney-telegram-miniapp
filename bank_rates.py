"""Read ACLEDA's published cash-note USD/KHR sell quote; cache only parsed quotes."""
import re
import time
from datetime import datetime
from decimal import Decimal
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import Table, Column, String, Numeric, BigInteger, select

SOURCES = (
    'https://www.acledabank.com.kh/kh/eng/ps_cmforeignexchange',
    'https://www.acledabank.com.kh/assets/unity/exchangerate',
)
CACHE_KEY = 'acleda_cash_usd_khr'
TZ = ZoneInfo('Asia/Phnom_Penh')


def define_cache(metadata):
    return Table('bank_rate_cache', metadata,
        Column('key', String(40), primary_key=True),
        Column('rate', Numeric(12, 4), nullable=False),
        Column('quote_date', String(80), nullable=False),
        Column('published_at', BigInteger, nullable=False),
        Column('checked_at', BigInteger, nullable=False),
        Column('source_url', String(200), nullable=False))


class RateTables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.stack, self.text = [], [], []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.ignored += 1
        if tag == 'table':
            table = {'rows': [], 'row': None, 'cell': None}
            self.tables.append(table)
            self.stack.append(table)
        elif self.stack and tag == 'tr':
            self.stack[-1]['row'] = []
        elif self.stack and tag in ('td', 'th'):
            self.stack[-1]['cell'] = []

    def handle_data(self, data):
        if self.ignored or not data.strip():
            return
        self.text.append(data.strip())
        if self.stack and self.stack[-1]['cell'] is not None:
            self.stack[-1]['cell'].append(data.strip())

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.ignored = max(0, self.ignored - 1)
        if not self.stack:
            return
        table = self.stack[-1]
        if tag in ('td', 'th') and table['cell'] is not None:
            if table['row'] is not None:
                table['row'].append(' '.join(table['cell']))
            table['cell'] = None
        elif tag == 'tr' and table['row'] is not None:
            table['rows'].append(table['row'])
            table['row'] = None
        elif tag == 'table':
            self.stack.pop()


def parse_quote(html):
    parser = RateTables()
    parser.feed(html)
    page_text = re.sub(r'\s+', ' ', ' '.join(parser.text))
    stamp = re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December) '
                      r'\d{1,2}, \d{4}(?: \d{1,2}:\d{2} ?[AP]M)?', page_text, re.I)
    if not stamp:
        raise ValueError('Published quote date missing')
    quote_date = stamp.group(0)
    fmt = '%B %d, %Y %I:%M %p' if ':' in quote_date else '%B %d, %Y'
    quote_date = re.sub(r'(\d)([AP]M)$', r'\1 \2', quote_date, flags=re.I)
    published = datetime.strptime(quote_date, fmt).replace(tzinfo=TZ)
    if published.timestamp() > time.time() + 3600:
        raise ValueError('Published quote date is in the future')
    number = re.compile(r'(?<![\w.])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w.])')
    for table in parser.tables:
        buy_index = sell_index = None
        for row in table['rows']:
            labels = [cell.strip().lower() for cell in row]
            if 'currency' in labels:
                buy_index = next((i for i, cell in enumerate(labels) if cell in ('buy', 'bid')), None)
                sell_index = next((i for i, cell in enumerate(labels) if cell in ('sell', 'ask')), None)
                continue
            if buy_index is None or sell_index is None or len(row) <= max(buy_index, sell_index):
                continue
            pair = re.sub(r'\s+', '', row[0]).upper()
            if pair not in ('USD/KHR', 'USD'):
                continue
            buy_cell, sell_cell = row[buy_index], row[sell_index]
            if pair == 'USD' and not all(re.search(r'\bKHR\b', cell, re.I) for cell in (buy_cell, sell_cell)):
                continue
            values = [number.findall(cell) for cell in (buy_cell, sell_cell)]
            if any(len(value) != 1 for value in values):
                continue
            bid, ask = [Decimal(value[0].replace(',', '')) for value in values]
            if 1000 <= bid <= ask <= 10000:
                return {'rate': ask, 'quote_date': quote_date, 'published_at': int(published.timestamp())}
    raise ValueError('No labelled USD/KHR buy/sell row found')


def market_quote(engine, table, logger):
    def stored():
        with engine.connect() as conn:
            return conn.execute(select(table).where(table.c.key == CACHE_KEY)).mappings().first()

    def result(row, live):
        rate = float(row['rate'])
        return {'rate_khr_per_usd': rate, 'sell_rate': rate, 'date': row['quote_date'],
                'source': 'ACLEDA Bank (cash-note USD sell rate)', 'source_url': row['source_url'],
                'live': live, 'checked_at': row['checked_at']}

    headers = {'Accept': 'text/html', 'Accept-Language': 'en-US,en;q=0.9',
               'User-Agent': 'MyMoney/1.0 (published exchange-rate reader)'}
    for url in SOURCES:
        try:
            response = requests.get(url, headers=headers, timeout=(3, 5))
            response.raise_for_status()
            quote = parse_quote(response.text)
        except (requests.RequestException, ValueError) as exc:
            logger.warning('ACLEDA quote unavailable at %s: %s', url, type(exc).__name__)
            continue
        if engine.dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert as upsert
        else:
            from sqlalchemy.dialects.sqlite import insert as upsert
        values = dict(quote, key=CACHE_KEY, checked_at=int(time.time()), source_url=url)
        stmt = upsert(table).values(**values)
        with engine.begin() as conn:
            conn.execute(stmt.on_conflict_do_update(index_elements=['key'],
                set_={key: value for key, value in values.items() if key != 'key'},
                where=stmt.excluded.published_at >= table.c.published_at))
        latest = stored()
        if latest['published_at'] > quote['published_at']:
            # Never replace a newer stored quote with an older fallback page.
            continue
        logger.info('ACLEDA sell quote parsed: %s KHR; published %s', quote['rate'], quote['quote_date'])
        return result(latest, True)
    cached = stored()
    return result(cached, False) if cached else None
