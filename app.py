import streamlit as st
import boto3
from botocore.exceptions import ClientError
import pandas as pd
from datetime import datetime

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
# 2. データの取得・更新・初期化関数
# --------------------------------------------------
def get_lockers():
    """DynamoDBから全ロッカーの情報を取得する"""
    try:
        response = table.scan()
        items = response['Items']
        # 数字順 (1, 2, 10...) に並べ替えるための処理
        def sort_key(item):
            try:
                return int(item['locker_id'])
            except ValueError:
                return 99999
        
        return sorted(items, key=sort_key)
    except ClientError as e:
        st.error(f"データ取得失敗: {e}")
        return []

def initialize_lockers():
    """1番から200番までのロッカーを一括作成・リセットする"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with table.batch_writer() as batch:
            for i in range(1, 201):
                batch.put_item(Item={
                    'locker_id': str(i),
                    'status': 'available',
                    'student_id': '-',
                    'user_name': '-',
                    'last_updated': timestamp
                })
        return True
    except ClientError as e:
        st.error(f"初期化失敗: {e}")
        return False

def rent_locker(locker_id, student_id, user_name):
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
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        table.update_item(
            Key={'locker_id': str(locker_id)},
            UpdateExpression="set #st = :s, student_id = :empty, user_name = :empty, last_updated = :t",
            ExpressionAttributeNames={'#st': 'status'},
            ExpressionAttributeValues={
                ':s': 'available',
                ':empty': '-',
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
# 【タブ1】利用者画面（登録のみ）
# ==========================================
with tab_user:
    st.header("利用開始 (登録)")
    
    # --- 空きロッカーの取得 ---
    if not df.empty and 'status' in df.columns:
        available_lockers = df[df['status'] == 'available']['locker_id'].tolist()
    else:
        available_lockers = []
        
    # --- 登録フォーム ---
    if not available_lockers:
        st.warning("現在、空いているロッカーはありません。")
    else:
        with st.form("user_rent_form"):
            st.markdown("空いているロッカーを選択して、利用登録を行ってください。")
            u_locker = st.selectbox("ロッカー番号", available_lockers)
            u_sid = st.text_input("学籍番号 (例: 2403036)")
            u_name = st.text_input("氏名 (例: 埼玉太郎)")
            
            # 返却機能は削除し、登録ボタンのみ配置
            if st.form_submit_button("利用開始", type="primary"):
                if not u_sid or not u_name:
                    st.error("すべての項目を入力してください。")
                elif rent_locker(u_locker, u_sid, u_name):
                    st.success(f"ロッカー番号 {u_locker} を借りました！")
                    st.rerun()

    st.divider()
    st.caption("現在の空き状況")
    if not df.empty:
        status_view = df[['locker_id', 'status']].copy()
        status_view['status'] = status_view['status'].apply(lambda x: "🔵 空き" if x == "available" else "🔴 使用中")
        st.dataframe(status_view, hide_index=True, use_container_width=True)

# ==========================================
# 【タブ2】管理者画面
# ==========================================
with tab_admin:
    st.header("管理者メニュー")
    
    password = st.text_input("管理者パスワード", type="password")
    if password == "admin123":
        st.success("認証成功")
        
        # --- 1. 一覧表示 ---
        st.subheader("📋 利用状況一覧")
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("CSVダウンロード", csv, "lockers.csv", "text/csv")

        st.divider()

        # --- 2. 手動操作 ---
        st.subheader("🛠️ 手動操作")
        admin_action = st.radio("操作種別", ["代理貸出", "強制返却"], horizontal=True, key="admin_radio")

        if admin_action == "代理貸出":
            if not df.empty:
                admin_avail = df[df['status'] == 'available']['locker_id'].tolist()
                with st.form("admin_rent"):
                    a_locker = st.selectbox("対象ロッカー", admin_avail)
                    a_sid = st.text_input("学籍番号")
                    a_name = st.text_input("氏名")
                    if st.form_submit_button("登録"):
                        rent_locker(a_locker, a_sid, a_name)
                        st.rerun()

        elif admin_action == "強制返却":
            if not df.empty:
                admin_use = df[df['status'] == 'in_use']['locker_id'].tolist()
                with st.form("admin_ret"):
                    a_ret_locker = st.selectbox("対象ロッカー", admin_use)
                    if st.form_submit_button("強制返却"):
                        return_locker(a_ret_locker)
                        st.rerun()
        
        st.divider()

        # --- 3. システム設定（初期化） ---
        st.subheader("⚠️ システム設定")
        st.warning("このボタンを押すと、ロッカー番号1〜200が作成・リセットされます。")
        if st.button("データ初期化 (1~200番を作成)", type="secondary"):
            with st.spinner("データベースを作成中..."):
                if initialize_lockers():
                    st.success("1番から200番のロッカーを作成しました！")
                    st.rerun()
