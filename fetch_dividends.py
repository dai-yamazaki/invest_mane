#!/usr/bin/env python3
"""
Yahoo Finance Japan から保有銘柄の配当データを取得するスクリプト
取得内容:
  - 今期予想配当（1株）
  - 配当利回り
  - 前年度実績配当（1株）
  - 年間配当合計（今期予想 × 保有数量）
出力: JSON形式
"""
import requests
from bs4 import BeautifulSoup
import re
import json
import time
import sys

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ja-JP,ja;q=0.9',
}

# 保有銘柄: コード -> (銘柄名, 保有数量)
HOLDINGS = {
    '1377': ('サカタのタネ',          10),
    '1605': ('INPEX',                 25),
    '1928': ('積水ハウス',            10),
    '4503': ('アステラス製薬',        100),
    '5108': ('ブリヂストン',          20),
    '5401': ('日本製鉄',              30),
    '6326': ('クボタ',                10),
    '6349': ('小森コーポレーション',  10),
    '6432': ('竹内製作所',             5),
    '7172': ('ジャパンInvest.A',      10),
    '7203': ('トヨタ自動車',          10),
    '7974': ('任天堂',                14),
    '8111': ('ゴールドウイン',        100),
    '8306': ('三菱UFJ',               10),
    '8316': ('三井住友FG',            10),
    '8593': ('三菱HCキャピタル',      30),
    '8725': ('MS&AD',                  5),
    '9101': ('日本郵船',               4),
    '9104': ('商船三井',               5),
    '9432': ('NTT',                  400),
    '9433': ('KDDI',                  20),
    '9434': ('ソフトバンク',          150),
}

def fetch_dividend(code: str) -> dict:
    """今期予想・利回り・前年度実績を取得する"""
    result = {
        'div_per_share':      None,  # 今期予想
        'yield':              None,
        'prev_div_per_share': None,  # 前年度実績
        'prev_year_label':    None,  # 例: "2026年3月期"
    }

    # ─── 1. 株価ページ: 今期予想 + 利回り ───────────────────────
    try:
        r = requests.get(f'https://finance.yahoo.co.jp/quote/{code}.T',
                         headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        for dl in soup.find_all('dl', class_=lambda c: c and 'DataListItem_' in str(c)):
            dt, dd = dl.find('dt'), dl.find('dd')
            if not (dt and dd):
                continue
            label, value = dt.get_text(strip=True), dd.get_text(strip=True)
            if '1株配当' in label:
                m = re.search(r'([\d,]+\.?\d*)', value)
                if m:
                    result['div_per_share'] = float(m.group(1).replace(',', ''))
            if '配当利回り' in label:
                m = re.search(r'([\d\.]+)%', value)
                if m:
                    result['yield'] = float(m.group(1))
    except Exception as e:
        result['error_quote'] = str(e)

    time.sleep(0.3)

    # ─── 2. 配当履歴ページ: 前年度実績 ──────────────────────────
    try:
        r2 = requests.get(f'https://finance.yahoo.co.jp/quote/{code}.T/dividend',
                          headers=HEADERS, timeout=10)
        r2.raise_for_status()
        soup2 = BeautifulSoup(r2.text, 'html.parser')
        tables = soup2.find_all('table')

        # table[1] = 実績テーブル（最新年度が先頭行）
        if len(tables) >= 2:
            rows = tables[1].find_all('tr')
            for row in rows:
                cells = [c.get_text(strip=True) for c in row.find_all(['th', 'td'])]
                if not cells:
                    continue
                # 先頭セルが "YYYY年M月期" 形式
                label_m = re.match(r'(\d{4}年\d+月期)', cells[0])
                if label_m and len(cells) >= 2:
                    # 年間配当（調整後）は2列目
                    val_m = re.search(r'([\d,]+\.?\d*)', cells[1])
                    if val_m:
                        result['prev_div_per_share'] = float(val_m.group(1).replace(',', ''))
                        result['prev_year_label']    = label_m.group(1)
                        break  # 最新年度1件だけ取得

    except Exception as e:
        result['error_history'] = str(e)

    return result


def main():
    results = {}
    total_new  = 0
    total_prev = 0

    print(f"{'コード':<6} {'銘柄':<22} {'数量':>5} {'今期予想':>9} {'前年実績':>9} {'増配額':>8} {'増配率':>7} {'年間配当':>9}", file=sys.stderr)
    print('-' * 84, file=sys.stderr)

    for code, (name, qty) in HOLDINGS.items():
        data    = fetch_dividend(code)
        new_div = data.get('div_per_share')
        prv_div = data.get('prev_div_per_share')
        yld     = data.get('yield')
        annual  = round(new_div * qty) if new_div else None

        diff     = round(new_div - prv_div, 1) if (new_div and prv_div) else None
        diff_pct = (diff / prv_div * 100)       if (diff is not None and prv_div) else None

        results[code] = {
            'name':               name,
            'qty':                qty,
            'div_per_share':      new_div,
            'yield':              yld,
            'prev_div_per_share': prv_div,
            'prev_year_label':    data.get('prev_year_label'),
            'diff_per_share':     diff,
            'diff_pct':           round(diff_pct, 2) if diff_pct is not None else None,
            'annual_div':         annual,
        }

        if annual:  total_new  += annual
        if prv_div: total_prev += round(prv_div * qty)

        def _f(v): return f'{v:.1f}円' if v is not None else 'N/A'
        def _d(v): return ('+' if v >= 0 else '') + f'{v:.1f}円' if v is not None else 'N/A'
        def _p(v): return ('+' if v >= 0 else '') + f'{v:.1f}%'  if v is not None else 'N/A'

        print(f'{code:<6} {name:<22} {qty:>5} {_f(new_div):>9} {_f(prv_div):>9} {_d(diff):>8} {_p(diff_pct):>7} {"¥"+str(annual) if annual else "N/A":>9}', file=sys.stderr)

        time.sleep(0.3)

    print('-' * 84, file=sys.stderr)
    print(f'{"年間配当合計（今期）":>60} ¥{total_new:,}', file=sys.stderr)
    print(f'{"年間配当合計（前年）":>60} ¥{total_prev:,}', file=sys.stderr)
    print(f'{"差額":>60} +¥{total_new-total_prev:,}', file=sys.stderr)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
