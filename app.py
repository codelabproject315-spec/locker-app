import streamlit as st
import boto3
from botocore.exceptions import ClientError
import pandas as pd

# --------------------------------------------------
# 1. AWS DynamoDBへの接続設定
# --------------------------------------------------
try:
    # Secretsから認証情報を取得して接続
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=st.secrets["AWS_DEFAULT_REGION"],
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"]
    )
    # ★テーブル名を正しいもの('Lockers')に指定
    table = dynamodb.Table('Lockers')
except Exception as e:
    st.error(f"AWS接続エラー: {e}")
    st.stop()

# --------------------------------------------------
# 2. データの取得・更新関数
# --------------------------------------------------
def get_lockers():
    """DynamoDBから全ロッカーの情報を取得する"""
    try:
        response = table.scan()
        items = response['Items']
        # locker_id順に並べ替え（1, 2, 3...）
        return sorted(items, key=lambda x: x['locker_id'])
    except ClientError as e:
        st.error(f"データ取得失敗: {e}")
        return []

def update_locker_status(locker_id, new_status):
    """ロッカーの状態を更新する (available <-> in_use)"""
    try:
        table.update_item(
            Key={'locker_id': str(locker_id)}, # IDは文字列で渡す
            UpdateExpression="set #st = :s",
            ExpressionAttributeNames={'#st': 'status'},
            ExpressionAttributeValues={':s': new_status}
        )
        st.success(f"ロッカー {locker_id} を更新しました！")
    except ClientError as e:
        st.error(f"更新失敗: {e}")

# --------------------------------------------------
# 3. アプリの画面構成（タブ作成）
# --------------------------------------------------
st.title("ロッカー管理システム 🔐")

# ★ここでタブを作成します
tab_user, tab_admin = st.tabs(["🙋 利用者画面", "⚙️ 管理者画面"])

# ==========================================
# 【タブ1】利用者画面 (ロッカーの貸出/返却)
# ==========================================
with tab_user:
    st.header("ロッカーの利用状況")
    st.write("ボタンを押して使用/空きを変更できます。")

    # データを取得
    lockers = get_lockers()

    if not lockers:
        st.info("データがありません。")
    else:
        # 3列のカラムを作成して並べる
        cols = st.columns(3)
        for i, locker in enumerate(lockers):
            locker_id = locker['locker_id']
            status = locker['status']
            
            # カラムを循環させる (col1 -> col2 -> col3 -> col1...)
            with cols[i % 3]:
                st.write(f"### 🚪 {locker_id}")
                
                if status == 'available':
                    st.success("空き")
                    if st.button(f"使う", key=f"use_{locker_id}"):
                        update_locker_status(locker_id, 'in_use')
                        st.rerun() # 画面更新
                else:
                    st.error("使用中")
                    if st.button(f"終了する", key=f"end_{locker_id}"):
                        update_locker_status(locker_id, 'available')
                        st.rerun() # 画面更新
                st.divider()

# ==========================================
# 【タブ2】管理者画面 (一覧表示・リセット)
# ==========================================
with tab_admin:
    st.header("管理者用メニュー")
    
    # 簡易的なパスワード機能（任意）
    password = st.text_input("管理者パスワードを入力", type="password")
    
    if password == "admin123":  # パスワードが合っている時だけ表示
        st.success("ログイン成功")
        
        # 現在のデータを表で表示
        st.subheader("データベースの中身")
        lockers_data = get_lockers()
        if lockers_data:
            df = pd.DataFrame(lockers_data)
            st.dataframe(df) # 表を表示
        
        st.divider()
        st.warning("⚠️ 危険な操作エリア")
        if st.button("全ロッカーを「空き」にリセットする"):
            # ここに全リセットの処理を書く（今回は省略）
            st.write("リセット機能はまだ実装していません！")
            
    elif password:
        st.error("パスワードが違います")
    else:
        st.info("パスワードを入力してください")
