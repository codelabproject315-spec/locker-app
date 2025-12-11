import streamlit as st
import boto3
from botocore.exceptions import ClientError
import pandas as pd
from datetime import datetime

# --------------------------------------------------
# 0. 背景画像の設定 (CSSカスタマイズ)
# --------------------------------------------------

# ★★★ 取得した画像の公開URLをここに貼り付けてください ★★★
# 例: GitHub PagesやS3などにアップロードした画像の直リンク
BACKGROUND_IMAGE_URL =https://d.kuku.lu/4zbzxsbfa

# 背景を設定するCSSコード
st.markdown(
    f"""
    <style>
    .stApp {{
        background-image: url({BACKGROUND_IMAGE_URL});
        background-size: cover; /* 画面全体に画像を拡大 */
        background-attachment: fixed; /* スクロールしても背景を固定 */
        background-repeat: no-repeat;
        
        /* 文字が背景と被って見えなくなるのを防ぐために、コンテンツに少し透明な背景を追加 */
        background-color: rgba(255, 255, 255, 0.7); 
    }}
    .stApp > header {{
        background-color: rgba(0,0,0,0); /* ヘッダーのStreamlitマークを透明に */
    }}
    </style>
    """,
    unsafe_allow_html=True
)

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
        # 数字順に並べ替え
        def sort_key(item):
            try:
                return int(item['locker_id'])
            except ValueError:
                return 99999
        return sorted(items, key=sort_key)
    except ClientError as e:
        st.error(f"データ取得失敗: {e}")
        return []

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
    
    # 登録完了メッセージをセッションステートで管理
    if 'rent_success_message' not in st.session_state:
        st.session_state.rent_success_message = None

    # 成功メッセージがあれば表示し、すぐにクリア
    if st.session_state.rent_success_message:
        st.success(st.session_state.rent_success_message)
        st.session_state.rent_success_message = None # メッセージをクリア

    if not df.empty and 'status' in df.columns:
        available_lockers = df[df['status'] == 'available']['locker_id'].tolist()
    else:
        available_lockers = []
        
    if not available_lockers:
        st.warning("現在、空いているロッカーはありません。")
    else:
        with st.form("user_rent_form"):
            st.markdown("空いているロッカーを選択して、利用登録を行ってください。")
            u_locker = st.selectbox("ロッカー番号", available_lockers)
            u_sid = st.text_input("学籍番号 (例: 2403036)")
            u_name = st.text_input("氏名 (例: 埼玉太郎)")
            
            if st.form_submit_button("利用開始", type="primary"):
                if not u_sid or not u_name:
                    st.error("すべての項目を入力してください。")
                elif rent_locker(u_locker, u_sid, u_name):
                    # 成功メッセージをセッションステートに保存
                    st.session_state.rent_success_message = f"ロッカー番号 **{u_locker}** の登録が完了しました！"
                    st.rerun() # 再読み込みでメッセージを表示

    st.divider()
    st.caption("現在の空き状況")
    if not df.empty:
        status_view = df[['locker_id', 'status']].copy()
        status_view = status_view.rename(columns={'locker_id': 'ロッカー番号', 'status': '状態'})
        status_view['状態'] = status_view['状態'].replace({'available': '🔵 空き', 'in_use': '🔴 使用中'})
        st.dataframe(status_view, hide_index=True, use_container_width=True)

# ==========================================
# 【タブ2】管理者画面
# ==========================================
with tab_admin:
    st.header("管理者メニュー")
    
    # ログイン状態を管理する変数を初期化
    if 'admin_logged_in' not in st.session_state:
        st.session_state.admin_logged_in = False

    # --- ログインしていない場合 ---
    if not st.session_state.admin_logged_in:
        password = st.text_input("管理者パスワード", type="password")
        if st.button("ログイン"):
            if password == "admin123":
                st.session_state.admin_logged_in = True
                st.rerun() # 画面を再読み込みして管理者画面を表示
            else:
                st.error("パスワードが間違っています")

    # --- ログイン済みの場合 ---
    else:
        # ヘッダー部分（認証済みメッセージとログアウトボタン）
        col1, col2 = st.columns([3, 1])
        with col1:
            st.success("✅ 管理者としてログイン中")
        with col2:
            if st.button("ログアウト"):
                st.session_state.admin_logged_in = False
                st.rerun() # 画面を再読み込みしてログイン画面に戻る

        # --- 1. 一覧表示（日本語化・列整理） ---
        st.subheader("📋 利用状況一覧")
        if not df.empty:
            display_df = df.copy()
            target_cols = ['locker_id', 'status', 'student_id', 'user_name']
            cols_to_use = [c for c in target_cols if c in display_df.columns]
            display_df = display_df[cols_to_use]

            display_df = display_df.rename(columns={
                'locker_id': 'ロッカー番号',
                'status': '状態',
                'student_id': '学籍番号',
                'user_name': '氏名'
            })

            display_df['状態'] = display_df['状態'].replace({
                'available': '空き',
                'in_use': '使用中'
            })

            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            csv = display_df.to_csv(index=False).encode('utf-8')
            st.download_button("CSVダウンロード", csv, "lockers.csv", "text/csv")

        st.divider()

        # --- 2. 手動操作 ---
        st.subheader("🛠️ 手動操作")
        admin_action = st.radio("操作種別", ["代理貸出", "強制返却"], horizontal=True, key="admin_radio")

        if admin_action == "代理貸出":
            if not df.empty:
                admin_avail = df[df['status'] == 'available']['locker_id'].tolist()
                if not admin_avail:
                    st.info("空きロッカーはありません。")
                else:
                    with st.form("admin_rent"):
                        a_locker = st.selectbox("対象ロッカー", admin_avail)
                        a_sid = st.text_input("学籍番号")
                        a_name = st.text_input("氏名")
                        if st.form_submit_button("登録"):
                            if not a_sid or not a_name:
                                st.error("入力が不足しています")
                            else:
                                rent_locker(a_locker, a_sid, a_name)
                                st.rerun()

        elif admin_action == "強制返却":
            if not df.empty:
                admin_use = df[df['status'] == 'in_use']['locker_id'].tolist()
                if not admin_use:
                    st.info("使用中のロッカーはありません。")
                else:
                    with st.form("admin_ret"):
                        a_ret_locker = st.selectbox("対象ロッカー", admin_use)
                        if st.form_submit_button("強制返却"):
                            return_locker(a_ret_locker)
                            st.rerun()
