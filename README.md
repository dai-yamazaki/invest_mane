# 投資ポートフォリオ管理ツール

楽天証券の保有データと Yahoo Finance Japan の配当情報をもとに、投資ダッシュボードを自動更新するツール群です。

## ダッシュボード

**[投資ダッシュボードを見る →](https://dai-yamazaki.github.io/invest_mane/)**

## ファイル構成

| ファイル | 説明 |
|---|---|
| `投資ダッシュボード.html` | メインダッシュボード（Chart.js製） |
| `fetch_dividends.py` | Yahoo Finance Japan から配当データをスクレイピング |
| `write_dividends_to_sheets.py` | 配当データを Google スプレッドシートに書き込む |
| `ダッシュボード作成マニュアル.md` | 更新手順マニュアル |

## ダッシュボードの更新手順

1. Google スプレッドシート「日本株管理」を最新の楽天証券データで更新
2. `fetch_dividends.py` を実行して Yahoo Finance から配当データを取得
3. Claude Code の `/update-dashboard` スキルで HTML を自動更新
4. `git push` で GitHub Pages に反映

## 表示内容

- 総資産・評価損益サマリー
- カテゴリ別内訳（投資信託・ETF / 個別株 / ゴールド / 債券）
- 個別株式一覧（配当・利回り含む）
- 投資信託・ETF一覧
- 配当金増減比較（前年実績 vs 今期予想）
- 月別配当カレンダー
- アセット配分ドーナツチャート
