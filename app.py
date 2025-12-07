import streamlit as st
import boto3
from botocore.exceptions import ClientError
import pandas as pd
from datetime import datetime
from decimal import Decimal

# --------------------------------------------------
# 1. AWS DynamoDBへの接続設定
# --------------------------------------------------
try:
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=st.secrets["AWS_DEFAULT_REGION"],
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"]
    )
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
        # locker_id順に並べ替え（文字として並べ替え）
        return sorted(items, key=lambda x: x['locker_id'])
    except ClientError as e:
        st.error(f"データ取得失敗: {e}")
        return []

def rent_locker(locker_id, student_id, user_name):
    """ロッカーを借りる（情報を保存して使用中にする）"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        table.update_item(
            Key={'locker_id': str(locker_id)},
            UpdateExpression="set #st = :s, student_id = :sid, user_name = :u, last_updated = :t",
            ExpressionAttributeNames={'#st': 'status'},
            ExpressionAttributeValues={
                ':s': 'in_use',
                ':sid': student_id,
                ':u': user_name,
                ':t': timestamp
            }
        )
        return True
    except ClientError as e:
        st.error(f"更新失敗: {e}")
        return False

def return_locker(locker_id):
    """ロッカーを返却する（空きにする）"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        table.update_item(
            Key={'locker_id': str(locker_id)},
            UpdateExpression="set #st = :s, student_id = :empty, user_name = :empty, last_updated = :t",
            ExpressionAttributeNames={'#st': 'status'},
            ExpressionAttributeValues={
                ':s': 'available',
                ':empty': '-', # 情報を消す
                ':t': timestamp
            }
        )
        return True
    except ClientError as e:
        st.error(f"返却失敗: {e}")
        return False

# --------------------------------------------------
# 3. アプリの画面構成
# --------------------------------------------------
st.title("ロッカー管理システム 🔐")

# データを取得
lockers = get_lockers()
df = pd.DataFrame(lockers)

# タブ作成
tab_user, tab_admin = st.tabs(["🙋 利用者画面", "⚙️ 管理者画面"])

# ==========================================
# 【タブ1】利用者画面 (借りる・返す)
# ==========================================
with tab_user:
    st.header("利用申請")
    
    # --- 操作を選んでもらう ---
    action = st.radio("操作を選択してください", ["利用開始 (借りる)", "利用終了 (返す)"], horizontal=True)
    
    if action == "利用開始 (借りる)":
        st.subheader("🔑 ロッカーを借りる")
        
        # 空いているロッカーだけをリストアップ
        if not df.empty and 'status' in df.columns:
            available_lockers = df[df['status'] == 'available']['locker_id'].tolist()
        else:
            available_lockers = []
            
        if not available_lockers:
            st.warning("現在、空いているロッカーはありません。")
        else:
            with st.form("rent_form"):
                # 入力フォーム
                selected_locker = st.selectbox("ロッカー番号を選択", available_lockers)
                input_student_id = st.text_input("学籍番号 (例: 2403036)")
                input_name = st.text_input("氏名 (例: 埼玉太郎)")
                
                submitted = st.form_submit_button("利用開始", type="primary")
                
                if submitted:
                    if not input_student_id or not input_name:
                        st.error("学籍番号と氏名を入力してください。")
                    else:
                        if rent_locker(selected_locker, input_student_id, input_name):
                            st.success(f"{selected_locker} の利用を開始しました！")
                            st.rerun()

    elif action == "利用終了 (返す)":
        st.subheader("↩️ ロッカーを返す")
        
        # 使用中のロッカーをリストアップ
        if not df.empty and 'status' in df.columns:
            in_use_lockers = df[df['status'] == 'in_use']['locker_id'].tolist()
        else:
            in_use_lockers = []
            
        if not in_use_lockers:
            st.info("現在、使用中のロッカーはありません。")
        else:
            with st.form("return_form"):
                return_locker_id = st.selectbox("返却するロッカー番号を選択", in_use_lockers)
                return_submitted = st.form_submit_button("返却する")
                
                if return_submitted:
                    if return_locker(return_locker_id):
                        st.success(f"{return_locker_id} を返却しました。")
                        st.rerun()
    
    st.divider()
    st.write("現在の空き状況:")
    # 利用者には個人情報を見せず、状態だけ表示
    if not df.empty:
        status_view = df[['locker_id', 'status']].copy()
        status_view['status'] = status_view['status'].apply(lambda x: "🔵 空き" if x == "available" else "🔴 使用中")
        st.dataframe(status_view, hide_index=True, use_container_width=True)

# ==========================================
# 【タブ2】管理者画面 (詳細確認・リセット)
# ==========================================
with tab_admin:
    st.header("管理者メニュー")
    
    password = st.text_input("管理者パスワード", type="password")
    if password == "admin123":
        st.success("認証成功")
        
        st.subheader("📋 利用状況一覧")
        if not df.empty:
            # 管理者には全ての情報（学籍番号・氏名など）を表示
            st.dataframe(df, use_container_width=True)
            
            # CSVダウンロードボタン
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "データをCSVでダウンロード",
                csv,
                "lockers.csv",
                "text/csv",
                key='download-csv'
            )
        
        st.divider()
        st.write("メンテナンス:")
        # 強制返却などの機能が必要ならここに追加できます
