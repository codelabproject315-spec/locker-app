import streamlit as st
import pandas as pd
import numpy as np
import streamlit_authenticator as stauth
import yaml
import os
import boto3
from botocore.exceptions import ClientError
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
# 2. データの取得・更新・初期化・削除関数
# --------------------------------------------------
def get_lockers():
    try:
        response = table.scan()
        items = response['Items']
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

# ★★★ ロッカー削除用の関数 ★★★
def delete_locker(locker_id):
    try:
        table.delete_item(Key={'locker_id': str(locker_id)})
        return True
    except ClientError as e:
        st.error(f"削除失敗: {e}")
        return False

# --------------------------------------------------
# 3. アプリの画面構成
# --------------------------------------------------
st.set_page_config(page_title="ロッカー管理システム", layout="wide")

# データを取得
lockers = get_lockers()
df = pd.DataFrame(lockers)

# メッセージ用
if 'admin_message' not in st.session_state:
    st.session_state.admin_message = ""
if 'viewer_message' not in st.session_state:
    st.session_state.viewer_message = ""

# --- 認証設定 ---
admin_user = os.environ.get("ADMIN_USER")
admin_hash = os.environ.get("ADMIN_HASH")
cookie_name = os.environ.get("COOKIE_NAME")
cookie_key = os.environ.get("COOKIE_KEY")

credentials = {
    "usernames": {
        admin_user: {
            "email": admin_user,
            "name": admin_user, 
            "password": admin_hash 
        }
    }
}

authenticator = stauth.Authenticate(
    credentials,
    cookie_name,
    cookie_key,
    3600
)

st.title('ロッカー管理システム 🔐')
ADMIN_EMAIL = admin_user

# --- タブコンテンツ関数 ---

def display_viewer_tab():
    st.header('ロッカー空き状況')
    
    # 状態表示用のDataFrame作成
    if not df.empty:
        status_df = df[['locker_id', 'status']].copy()
        # L001などが混ざっていても表示はする
        st.dataframe(status_df, use_container_width=True, height=300)
    else:
        st.warning("データがありません。")

    st.divider() 
    st.header('ロッカー新規登録')
    
    if not df.empty:
        available_lockers = df[df['status'] == 'available']['locker_id'].tolist()
    else:
        available_lockers = []
    
    if not available_lockers:
        st.info('現在、登録できる空きロッカーがありません。')
    else:
        locker_no_reg_tab1 = st.selectbox(
            '空いているロッカーを選択してください:', 
            available_list_tab1, 
            key='reg_locker_select_tab1',
            index=None, 
            placeholder="ロッカー番号を選択..." 
        )
        student_id_reg_tab1 = st.text_input('学籍番号 (例: 2403036)', key='reg_sid_tab1')
        name_reg_tab1 = st.text_input('氏名 (例: 埼玉太郎)', key='reg_name_tab1')
        
        col1, col2 = st.columns([1, 2]) 
        with col1:
            if st.button('この内容で登録する', key='reg_button_tab1'):
                if not locker_no_reg_tab1 or not student_id_reg_tab1 or not name_reg_tab1:
                    st.error('すべての項目を入力してください。')
                else:
                    rent_locker(locker_no_reg_tab1, student_id_reg_tab1, name_reg_tab1)
                    st.session_state.viewer_message = f"【登録完了】ロッカー '{locker_no_reg_tab1}' を登録しました。"
                    st.rerun()
        with col2:
            if st.session_state.viewer_message:
                st.success(st.session_state.viewer_message)
                st.session_state.viewer_message = ""

def display_admin_tab():
    st.header('管理者パネル')
    
    if st.session_state.admin_message:
        st.success(st.session_state.admin_message)
        st.session_state.admin_message = "" 

    st.subheader('📝 ロッカー新規登録 (管理者)')
    if not df.empty:
        available_lockers = df[df['status'] == 'available']['locker_id'].tolist()
    else:
        available_lockers = []

    if not available_lockers:
        st.info('空きロッカーなし')
    else:
        locker_no_reg_tab2 = st.selectbox('ロッカー選択', available_lockers, key='admin_reg_sel', index=None, placeholder="選択...")
        student_id_reg_tab2 = st.text_input('学籍番号', key='admin_reg_sid')
        name_reg_tab2 = st.text_input('氏名', key='admin_reg_name')
        
        if st.button('登録', key='admin_reg_btn'):
            if locker_no_reg_tab2 and student_id_reg_tab2 and name_reg_tab2:
                rent_locker(locker_no_reg_tab2, student_id_reg_tab2, name_reg_tab2)
                st.session_state.admin_message = f"{locker_no_reg_tab2} を登録しました"
                st.rerun()

    st.divider()
    st.subheader('🗑️ 強制返却')
    if not df.empty:
        used_lockers = df[df['status'] == 'in_use']['locker_id'].tolist()
        if used_lockers:
            locker_no_del = st.selectbox('返却するロッカー', used_lockers, key='admin_del_sel', index=None, placeholder="選択...")
            if st.button('強制返却', key='admin_del_btn'):
                if locker_no_del:
                    return_locker(locker_no_del)
                    st.session_state.admin_message = f"{locker_no_del} を返却しました"
                    st.rerun()

    st.divider()
    st.subheader('📋 全データ一覧')
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("CSVダウンロード", csv, "lockers.csv", "text/csv")

    st.divider()
    
    # ★★★ ここに追加しました ★★★
    st.subheader('⚠️ システム管理')
    col_sys1, col_sys2 = st.columns(2)
    
    with col_sys1:
        st.warning("1〜200番のロッカーを初期化・作成します")
        if st.button("データ初期化 (1~200番)", type="secondary"):
            with st.spinner("作成中..."):
                if initialize_lockers():
                    st.success("初期化完了")
                    st.rerun()

    with col_sys2:
        st.error("テストデータ (L001〜L005) を削除します")
        if st.button("テストデータ削除 (L001-L005)", type="primary"):
            with st.spinner("削除中..."):
                # L001〜L005を削除
                for i in range(1, 6):
                    delete_locker(f"L{i:03d}")
                
                # ついでに A001〜A003 もあれば削除（念のため）
                for i in range(1, 4):
                    delete_locker(f"A{i:03d}")

                st.session_state.admin_message = "テストデータ (L001-L005) を削除しました！"
                st.rerun()

# --- メインロジック ---
available_list_tab1 = df[df['status'] == 'available']['locker_id'].tolist() if not df.empty else []

tab1, tab2 = st.tabs(["🗂️ 閲覧・登録用", "🔒 管理者用"])

with tab1:
    display_viewer_tab()

with tab2:
    authenticator.login(location='main')
    if st.session_state["authentication_status"]:
        current_user_email = st.session_state["name"] 
        if current_user_email == ADMIN_EMAIL: 
            st.write(f'Welcome *{current_user_email}* (Admin)')
            authenticator.logout('Logout', 'main')
            display_admin_tab()
        else:
            st.warning('あなたは管理者として登録されていません。')
            authenticator.logout('Logout', 'main')
    elif st.session_state["authentication_status"] is False:
        st.error('Username/password is incorrect')
    elif st.session_state["authentication_status"] is None:
        st.info('管理者機能にアクセスするには、UsernameとPasswordでログインしてください。')
