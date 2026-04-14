# 名刺自動化ツール

Eight の名刺データを取得し、Outlook にメール下書きを作成する社内向け Streamlit アプリです。

現在はマルチユーザー対応済みで、以下をユーザーごとに分離しています。

- Eight セッション
- Outlook 認証トークン
- 連絡先データ
- 処理済みデータ
- テンプレート

社内で他の従業員に使ってもらう場合は、まず管理者がセットアップし、その後に各従業員へ利用手順を配布してください。

- 管理者向け: [ADMIN_SETUP.md](./ADMIN_SETUP.md)
- 従業員向け: [EMPLOYEE_GUIDE.md](./EMPLOYEE_GUIDE.md)

## 推奨運用

- 認証は `APP_USER_PASSWORDS` を使ったユーザー別パスワード方式を推奨します。
- `APP_SHARED_PASSWORD` は共通パスワード方式なので、ユーザー単位の本人確認にはなりません。
- 各従業員は自分の PC で `login_helper.py` を実行し、自分の Eight セッションをアップロードしてください。
- 各従業員は自分の Microsoft アカウントで Outlook 認証を行ってください。

## 起動コマンド

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

## テスト

```bash
pytest -q
```
