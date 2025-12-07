import streamlit as st
import pandas as pd
import numpy as np
import streamlit_authenticator as stauth # 認証ライブラリ
import yaml # 設定ファイル読み込み用
import os # Renderのために追加
from io import StringIO # S3用

# --- 1. 永続ディスク（Persistent Disk）へのファイルパス ---
DATA_FILE_PATH = "/var/data/lockers.csv"

def load_data():
    if os.path.exists(DATA_FILE_PATH):
        return pd.read_csv(DATA_FILE_PATH)
    else:
        total_lockers = 200
        locker_numbers = [f"{i:03d}" for i in range(1, total_lockers + 1)]
        student_ids = [np.nan] * total_lockers
        names = [np.nan] * total_lockers
        
        initial_data = {
            'Locker No.': locker_numbers,
            'Student ID': student_ids,
            'Name': names
        }
        df = pd.DataFrame(initial_data)
        df.to_csv(DATA_FILE_PATH, index=False) 
        return df

if 'df' not in st.session_state:
    st.session_state.df = load_data()

if 'viewer_message' not in st.session_state:
    st.session_state.viewer_message = ""
if 'admin_message' not in st.session_state:
    st.session_state.admin_message = ""
if 'admin_reg_message' not in st.session_state:
    st.session_state.admin_reg_message = ""

# --- 2. 認証機能の設定 ---
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

st.title('ロッカー管理システム')
ADMIN_EMAIL = admin_user

# --- 4. タブのコンテンツ関数定義 ---

def display_viewer_tab():
    """閲覧・登録用タブ（登録機能のみ）"""
    
    st.header('ロッカー空き状況')
    
    df_lockers = st.session_state.df 
    available_lockers = df_lockers[df_lockers['Student ID'].isnull()]
    
    if available_lockers.empty:
        st.warning('現在、空きロッカーはありません。')
    else:
        st.dataframe(available_lockers[['Locker No.']], use_container_width=True, height=300)

    st.divider() 

    # ★★★ 変更点: 「操作を選択」を削除し、いきなり登録フォームを表示 ★★★
    st.header('ロッカー新規登録')
    
    available_list_tab1 = available_lockers['Locker No.'].tolist()
    
    if not available_list_tab1:
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
                    st.error('ロッカー番号、学籍番号、氏名をすべて入力してください。')
                else:
                    df_lockers.loc[df_lockers['Locker No.'] == locker_no_reg_tab1, ['Student ID', 'Name']] = [student_id_reg_tab1, name_reg_tab1]
                    st.session_state.df = df_lockers 
                    st.session_state.df.to_csv(DATA_FILE_PATH, index=False)
                    st.session_state.viewer_message = f"【登録完了】ロッカー '{locker_no_reg_tab1}' に '{name_reg_tab1}' さんを登録しました。"
                    st.rerun() 
        
        with col2:
            if st.session_state.viewer_message:
                st.success(st.session_state.viewer_message)
                st.session_state.viewer_message = "" 

def display_admin_tab():
    """管理者用タブ"""
    
    st.header('管理者パネル')
    
    if st.session_state.admin_message:
        st.success(st.session_state.admin_message)
        st.session_state.admin_message = "" 

    df_lockers = st.session_state.df

    st.subheader('📝 ロッカー新規登録')
    
    available_lockers_tab2 = df_lockers[df_lockers['Student ID'].isnull()]
    available_list_tab2 = available_lockers_tab2['Locker No.'].tolist()

    if not available_list_tab2:
        st.info('現在、登録できる空きロッカーがありません。')
    else:
        locker_no_reg_tab2 = st.selectbox(
            '空いているロッカーを選択してください:', 
            available_list_tab2, 
            key='reg_locker_select_tab2',
            index=None, 
            placeholder="ロッカー番号を選択..."
        )
        student_id_reg_tab2 = st.text_input('学籍番号 (例: 2403036)', key='reg_sid_tab2')
        name_reg_tab2 = st.text_input('氏名 (例: 埼玉太郎)', key='reg_name_tab2')
        
        col1, col2 = st.columns([1, 2]) 
        
        with col1:
            if st.button('この内容で登録する', key='reg_button_tab2'):
                if not locker_no_reg_tab2 or not student_id_reg_tab2 or not name_reg_tab2:
                    st.error('ロッカー番号、学籍番号、氏名をすべて入力してください。')
                else:
                    df_lockers.loc[df_lockers['Locker No.'] == locker_no_reg_tab2, ['Student ID', 'Name']] = [student_id_reg_tab2, name_reg_tab2]
                    st.session_state.df = df_lockers 
                    st.session_state.df.to_csv(DATA_FILE_PATH, index=False)
                    st.session_state.admin_reg_message = f"【登録完了】ロッカー '{locker_no_reg_tab2}' に '{name_reg_tab2}' さんを登録しました。"
                    st.rerun()
        
        with col2:
            if st.session_state.admin_reg_message:
                st.success(st.session_state.admin_reg_message)
                st.session_state.admin_reg_message = "" 

    st.divider()

    st.subheader('🗑️ 使用者の削除 (プルダウン)')
    
    used_lockers = df_lockers.dropna(subset=['Student ID'])
    used_locker_list = used_lockers['Locker No.'].tolist()
    
    if not used_locker_list:
        st.info('現在、使用中のロッカーはありません。')
    else:
        locker_no_del = st.selectbox(
            '削除するロッカーを選択してください:', 
            used_locker_list, 
            key='del_locker_select',
            index=None, 
            placeholder="ロッカー番号を選択..."
        )
        
        if st.button('このロッカーの使用者を削除する', type="primary", key='del_button_pulldown'):
            if not locker_no_del: 
                st.error('削除するロッカー番号を選択してください。')
            else:
                df_lockers.loc[df_lockers['Locker No.'] == locker_no_del, ['Student ID', 'Name']] = [np.nan, np.nan]
                st.session_state.df = df_lockers 
                st.session_state.df.to_csv(DATA_FILE_PATH, index=False)
                st.session_state.admin_message = f"【削除完了】ロッカー '{locker_no_del}' の使用者情報を削除しました。"
                st.rerun()
            
    st.divider() 

    st.subheader('🗂️ 全ロッカー一覧 (削除ボタン付き)')

    col_header = st.columns([1, 2, 2, 1]) 
    col_header[0].markdown('**Locker No.**')
    col_header[1].markdown('**Student ID**')
    col_header[2].markdown('**Name**')
    col_header[3].markdown('**操作**')
    st.divider()

    for index in st.session_state.df.index:
        row = st.session_state.df.loc[index]
        
        cols = st.columns([1, 2, 2, 1])
        
        cols[0].text(row['Locker No.'])
        cols[1].text(row.fillna('--- 空き ---')['Student ID'])
        cols[2].text(row.fillna('--- 空き ---')['Name'])
        
        if not pd.isnull(row['Student ID']):
            if cols[3].button('削除', key=f"del_{index}", type="primary"):
                st.session_state.df.loc[index, ['Student ID', 'Name']] = [np.nan, np.nan]
                st.session_state.df.to_csv(DATA_FILE_PATH, index=False)
                st.session_state.admin_message = f"ロッカー '{row['Locker No.']}' の使用者を削除しました。"
                st.rerun()
        else:
            cols[3].text("")
    
    st.divider() 
    st.subheader('💾 データをPCに保存 (バックアップ)')
    csv_string = df_lockers.to_csv(index=False)
    st.download_button(
        label="全ロッカーデータをCSVでダウンロード",
        data=csv_string,
        file_name='locker_data_backup.csv',
        mime='text/csv',
    )

# --- 5. メインロジック ---
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
