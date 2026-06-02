#!/usr/bin/env python3
"""
スクレイピングした配当データを Google Sheets の「配当履歴」シートに書き出す。

【初回のみ】セットアップ手順:
  1. https://console.cloud.google.com/ を開く
  2. 新しいプロジェクト作成（例: "dividend-tracker"）
  3. 「APIとサービス」→「ライブラリ」→「Google Sheets API」を有効化
  4. 「APIとサービス」→「認証情報」→「認証情報を作成」→「OAuth クライアント ID」
  5. アプリの種類: 「デスクトップアプリ」を選択 → 作成
  6. 「JSONをダウンロード」→ ~/.config/gspread/credentials.json として保存
     mkdir -p ~/.config/gspread
     mv ~/Downloads/client_secret_*.json ~/.config/gspread/credentials.json
  7. このスクリプトを初回実行 → ブラウザが開くので Google アカウントで許可
     以降は自動認証（~/.config/gspread/authorized_user.json に保存される）
"""

import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import json
import sys
import time
from datetime import date
from pathlib import Path

# ── 設定 ──────────────────────────────────────────────────────────────────
SPREADSHEET_ID = '1b3Hfdt4R51y7A55LECap7K-uTN_hjd8JMnKMF33_vAU'
SHEET_NAME     = '配当履歴'   # 書き込み先シート名（なければ自動作成）
SCOPES         = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]
CREDS_PATH = Path.home() / '.config' / 'gspread' / 'credentials.json'
TOKEN_PATH = Path.home() / '.config' / 'gspread' / 'authorized_user.json'

# ── 保有銘柄（fetch_dividends.py と同じ） ─────────────────────────────────
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

# ── Google Sheets 認証 ────────────────────────────────────────────────────
def authenticate() -> gspread.Client:
    """OAuth2 でブラウザ認証（初回のみ）、以降はトークンを再利用"""
    if not CREDS_PATH.exists():
        print(f'\n❌ 認証情報が見つかりません: {CREDS_PATH}')
        print(__doc__)
        sys.exit(1)

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())
        print('✅ 認証完了。トークンを保存しました。')

    return gspread.authorize(creds)


# ── スクレイピングデータ取得（fetch_dividends.py を import して使用）────
def get_dividend_data() -> list[dict]:
    """fetch_dividends.py のロジックを使って配当データを取得"""
    # fetch_dividends.py が同じディレクトリにあれば import
    script_dir = Path(__file__).parent
    sys.path.insert(0, str(script_dir))

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'fetch_dividends', script_dir / 'fetch_dividends.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        rows = []
        today = date.today().isoformat()
        for code, (name, qty) in mod.HOLDINGS.items():
            print(f'  取得中: {name}({code})...', end=' ', flush=True)
            data = mod.fetch_dividend(code)
            div     = data.get('div_per_share')
            prv_div = data.get('prev_div_per_share')
            yld     = data.get('yield')
            prv_lbl = data.get('prev_year_label', '')
            annual  = round(div * qty) if div else None
            diff    = round(div - prv_div, 1) if (div and prv_div) else None
            diff_pct = round((diff / prv_div * 100), 2) if (diff and prv_div) else None

            rows.append({
                '取得日':        today,
                'コード':        code,
                '銘柄名':        name,
                '保有数量':      qty,
                '今期予想(1株)': div,
                '前年実績(1株)': prv_div,
                '前年度':        prv_lbl,
                '増配額(1株)':   diff,
                '増配率(%)':     diff_pct,
                '配当利回り(%)': yld,
                '年間配当合計':  annual,
                '取得元URL':     f'https://finance.yahoo.co.jp/quote/{code}.T',
            })
            status = f'¥{div}' if div else 'N/A'
            print(status)
            time.sleep(0.3)

        return rows

    except Exception as e:
        print(f'\n❌ データ取得エラー: {e}')
        raise


# ── Google Sheets への書き込み ────────────────────────────────────────────
def write_to_sheet(client: gspread.Client, rows: list[dict]) -> None:
    ss = client.open_by_key(SPREADSHEET_ID)

    # シートを取得 or 作成
    try:
        ws = ss.worksheet(SHEET_NAME)
        print(f'\n📄 既存シート「{SHEET_NAME}」に追記します')
    except WorksheetNotFound:
        ws = ss.add_worksheet(title=SHEET_NAME, rows=200, cols=15)
        print(f'\n📄 新規シート「{SHEET_NAME}」を作成しました')

    existing = ws.get_all_values()
    headers  = list(rows[0].keys())

    # ヘッダーがなければ書き込む
    if not existing or existing[0] != headers:
        ws.clear()
        ws.append_row(headers, value_input_option='USER_ENTERED')
        print('  ヘッダー行を書き込みました')

    # データ行を追記
    data_rows = [[str(r.get(h, '')) for h in headers] for r in rows]
    ws.append_rows(data_rows, value_input_option='USER_ENTERED')

    total = sum(r['年間配当合計'] for r in rows if r['年間配当合計'])
    print(f'  {len(rows)} 行を書き込みました（年間配当合計: ¥{total:,}）')
    print(f'\n✅ 完了: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/')


# ── メイン ────────────────────────────────────────────────────────────────
def main():
    print('=== 配当データ → Google Sheets 書き出しツール ===\n')

    print('① Yahoo Finance Japan からデータ取得中...')
    rows = get_dividend_data()
    print(f'   {len(rows)} 銘柄取得完了\n')

    print('② Google Sheets に認証中...')
    client = authenticate()

    print('③ スプレッドシートに書き込み中...')
    write_to_sheet(client, rows)


if __name__ == '__main__':
    main()
