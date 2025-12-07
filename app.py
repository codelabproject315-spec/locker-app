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
# 2. データの取得・更新関数
# --------------------------------------------------
def get_lockers():
    """DynamoDBから全ロッカーの情報を取得する"""
    try:
        response = table.scan()
        items = response['Items']
        # 文字列として並べ替え (A-1, A-10, A-2... となるのを防ぐには工夫が必要ですが、一旦文字順)
        return sorted(items, key=lambda x: x['locker_id'])
    except ClientError as e:
        st.error(f"データ取得失敗: {e}")
        return []

def rent_locker(locker_id, student_id, user_name):
    """ロッカーを借りる"""
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
    """ロッカーを返却する"""
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
# 【タブ1】利用者画面 (通常の借りる・返す)
# ==========================================
with tab_user:
    st.header("利用申請")
    
    user_action = st.radio("操作を選択", ["利用開始 (借りる)", "利用終了 (返す)"], horizontal=True, key="user_radio")
    
    if user_action == "利用開始 (借りる)":
        st.subheader("🔑 ロッカーを借りる")
        if not df.empty and 'status' in df.columns:
            available_lockers = df[df['status'] == 'available']['locker_id'].tolist()
        else:
            available_lockers = []
            
        if not available_lockers:
            st.warning("現在、空いているロッカーはありません。")
        else:
            with st.form("user_rent_form"):
                u_locker = st.selectbox("ロッカー番号", available_lockers, key="u_rent_sel")
                u_sid = st.text_input("学籍番号", key="u_rent_sid")
                u_name = st.text_input("氏名", key="u_rent_name")
                if st.form_submit_button("利用開始", type="primary"):
                    if not u_sid or not u_name:
                        st.error("学籍番号と氏名を入力してください。")
                    elif rent_locker(u_locker, u_sid, u_name):
                        st.success(f"{u_locker} を借りました！")
                        st.rerun()

    elif user_action == "利用終了 (返す)":
        st.subheader("↩️ ロッカーを返す")
        if not df.empty and 'status' in df.columns:
            in_use_lockers = df[df['status'] == 'in_use']['locker_id'].tolist()
        else:
            in_use_lockers = []
            
        if not in_use_lockers:
            st.info("使用中のロッカーはありません。")
        else:
            with st.form("user_return_form"):
                u_ret_locker = st.selectbox("返却するロッカー", in_use_lockers, key="u_ret_sel")
                if st.form_submit_button("返却する"):
                    if return_locker(u_ret_locker):
                        st.success(f"{u_ret_locker} を返却しました。")
                        st.rerun()
    
    st.divider()
    st.caption("現在の空き状況")
    if not df.empty:
        status_view = df[['locker_id', 'status']].copy()
        status_view['status'] = status_view['status'].apply(lambda x: "🔵 空き" if x == "available" else "🔴 使用中")
        st.dataframe(status_view, hide_index=True, use_container_width=True)

# ==========================================
# 【タブ2】管理者画面 (一覧・代理操作)
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

        # --- 2. 手動操作 (代理入力) ---
        st.subheader("🛠️ 手動操作 (代理貸出・強制返却)")
        
        admin_action = st.radio("操作種別", ["代理貸出 (手動登録)", "強制返却 (リセット)"], horizontal=True, key="admin_radio")

        if admin_action == "代理貸出 (手動登録)":
            st.info("管理者が学生の代わりに情報を入力して貸出処理を行います。")
            if not df.empty:
                # 空きロッカーリスト
                admin_avail = df[df['status'] == 'available']['locker_id'].tolist()
                if not admin_avail:
                    st.warning("空きロッカーがありません。")
                else:
                    with st.form("admin_rent_form"):
                        a_locker = st.selectbox("対象ロッカー", admin_avail, key="a_rent_sel")
                        a_sid = st.text_input("学籍番号", key="a_rent_sid")
                        a_name = st.text_input("氏名", key="a_rent_name")
                        if st.form_submit_button("管理者権限で登録"):
                            if rent_locker(a_locker, a_sid, a_name):
                                st.success(f"管理者権限で {a_locker} を登録しました。")
                                st.rerun()

        elif admin_action == "強制返却 (リセット)":
            st.warning("使用中のロッカーを強制的に空き状態に戻します。")
            if not df.empty:
                # 使用中ロッカーリスト
                admin_use = df[df['status'] == 'in_use']['locker_id'].tolist()
                if not admin_use:
                    st.info("使用中のロッカーはありません。")
                else:
                    with st.form("admin_return_form"):
                        a_ret_locker = st.selectbox("強制返却するロッカー", admin_use, key="a_ret_sel")
                        if st.form_submit_button("強制返却実行"):
                            if return_locker(a_ret_locker):
                                st.error(f"管理者権限で {a_ret_locker} を返却済みにしました。")
                                st.rerun()
