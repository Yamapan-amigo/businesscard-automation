# 管理者向けセットアップ手順

## 1. 目的

この手順書は、社内で従業員がこのツールを利用できるようにするための管理者向け設定手順です。

## 2. 事前に必要なもの

- Python 3.10 以上
- Eight を使う従業員
- Microsoft Graph API 用の Azure App Registration
- 社内で共有するアプリ実行環境

## 3. アプリをセットアップする

リポジトリ直下で以下を実行します。

```bash
pip install -r requirements.txt
pip install playwright playwright-stealth
playwright install chromium
```

## 4. `.env` を設定する

最低限、以下を設定してください。

```env
MS_CLIENT_ID=your-azure-app-client-id
MS_TENANT_ID=common
HEADLESS=true
```

社内利用では、認証設定も入れてください。

### 推奨: ユーザー別パスワード方式

```env
APP_USER_PASSWORDS={"yamanaka":"pass1","sato":"pass2","suzuki":"pass3"}
```

この方式では、各従業員が自分のユーザー名と自分専用のパスワードでログインします。

### 非推奨: 共通パスワード方式

```env
APP_SHARED_PASSWORD=your-internal-password
APP_ALLOWED_USERS=yamanaka,sato,suzuki
```

この方式は、共通パスワードを知っている人が他ユーザー名で入れてしまうため、本人確認にはなりません。

## 5. Outlook 側の前提

各従業員は、アプリ内の「設定」ページから自分の Microsoft アカウントで認証します。

そのため、管理者が全員分の Outlook 認証を事前に入れる必要はありません。

## 6. アプリを起動する

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

社内からアクセスできる URL を従業員へ共有してください。

例:

```text
http://社内PCのIPアドレス:8501
```

## 7. 初回移行が必要な場合

以前の単一ユーザー版で使っていた場合は、「設定」ページの以下を必要に応じて実行してください。

- `共有DBを現在ユーザーへ取り込む`
- `共有Outlook認証を現在ユーザーへコピー`

ただし Outlook 認証は本来ユーザーごとに別であるべきなので、コピー後に各従業員が自分のアカウントで再認証する運用を推奨します。

## 8. 従業員へ案内する内容

従業員には以下を配布してください。

- アプリの URL
- 自分のユーザー名
- 自分のパスワード
- [EMPLOYEE_GUIDE.md](./EMPLOYEE_GUIDE.md)

## 9. 運用ルール

- 各従業員は必ず自分のユーザー名でログインする
- Eight セッションは他人と共有しない
- Outlook 認証は自分の Microsoft アカウントで行う
- パスワードは定期的に変更する

## 10. 動作確認

管理者側で最低限以下を確認してください。

1. ログインできる
2. Eight セッションをアップロードできる
3. Outlook 認証コードが表示される
4. 名刺取得ができる
5. Outlook 下書きが作成される

## 11. テスト

変更後は以下を実行してください。

```bash
pytest -q
```
