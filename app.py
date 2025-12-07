import streamlit as st
import boto3
import pandas as pd
from datetime import datetime
from decimal import Decimal

# ---------------------------------------------------------
# 設定（自分の環境に合わせて変更してください）
# ---------------------------------------------------------
TABLE_NAME = "Lockers"  # AWSで作ったテーブル名
REGION_NAME = "ap-northeast-1"  # 東京リージョン

# ---------------------------------------------------------
# AWS DynamoDBへの接続設定
# ---------------------------------------------------------
# キャッシュを使って接続を高速化
@st.cache_resource
def get_dynamodb_resource():
    # Streamlit CloudのSecrets機能から鍵を読み込む
    return boto3.resource(
        'dynamodb',
        region_name=REGION_NAME,
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"]
    )

try:
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(TABLE_NAME)
except Exception as e:
    st.error(f"AWSへの接続に失敗しました。Secretsが設定されているか確認してください。\nエラー: {e}")
    st.stop()

# ---------------------------------------------------------
# 関数定義
# ---------------------------------------------------------

def get_all_lockers():
    """ロッカーの全データを取得してDataFrameにする"""
    try:
        response = table.scan()
        items = response.get('Items', [])
        
        if not items:
            return pd.DataFrame()

        # Decimal型をint/floatに変換（エラー回避のため）
        for item in items:
            for key, value in item.items():
                if isinstance(value, Decimal):
                    item[key] = int(value)
        
        df = pd.DataFrame(items)
        
        # 表示を見やすく並べ替え（locker_id順）
        if 'locker_id' in df.columns:
            df = df.sort_values('locker_id')
            
        return df
    except Exception as e:
        st.error(f"データの取得に失敗しました: {e}")
        return pd.DataFrame()

def update_locker(locker_id, user_name, status):
    """ロッカーの状態を更新する"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        # 使用開始の場合
        if status == "使用中":
            table.update_item(
                Key={'locker_id': int(locker_id)},
                UpdateExpression="set #st = :s, user_name = :u, last_updated = :t",
                ExpressionAttributeNames={'#st': 'status'},  # statusは予約語のため別名使用
                ExpressionAttributeValues={
                    ':s': '使用中',
                    ':u': user_name,
                    ':t': timestamp
                }
            )
            st.success(f"ロッカー {locker_id} を {user_name} さんが使用開始しました！")
            
        # 返却（空きにする）場合
        else:
            table.update_item(
                Key={'locker_id': int(locker_id)},
                UpdateExpression="set #st = :s, user_name = :u, last_updated = :t",
                ExpressionAttributeNames={'#st': 'status'},
                ExpressionAttributeValues={
                    ':s': '空き',
                    ':u': '-',  # 名前をハイフンに戻す
                    ':t': timestamp
                }
            )
            st.success(f"ロッカー {locker_id} を返却しました！")
            
    except Exception as e:
        st.error(f"更新エラー: {e}")

# ---------------------------------------------------------
# アプリの画面構成（UI）
# ---------------------------------------------------------

st.title("🔐 クラウド・ロッカー管理システム")
st.caption("AWS DynamoDB x Streamlit 連携版")

# 再読み込みボタン
if st.button('🔄 最新状態に更新'):
    st.rerun()

# データの読み込み
df = get_all_lockers()

# --- 現在の状況を表示（メトリクス） ---
if not df.empty and 'status' in df.columns:
    total_lockers = len(df)
    used_lockers = len(df[df['status'] == '使用中'])
    free_lockers = total_lockers - used_lockers
    
    col1, col2, col3 = st.columns(3)
    col1.metric("全ロッカー数", f"{total_lockers} 個")
    col2.metric("使用中", f"{used_lockers} 個", delta_color="inverse")
    col3.metric("空き", f"{free_lockers} 個")
else:
    st.warning("データがありません。DynamoDBにデータが入っているか確認してください。")

st.divider()

# --- 操作パネル（2列レイアウト） ---
col_action, col_view = st.columns([1, 2])

with col_action:
    st.subheader("🛠 操作パネル")
    
    # ロッカーIDのリストを作成（データがあれば）
    if not df.empty and 'locker_id' in df.columns:
        locker_list = df['locker_id'].tolist()
    else:
        locker_list = [1, 2, 3, 4, 5] # デフォルト値

    # 入力フォーム
    target_id = st.selectbox("ロッカーNo.を選択", locker_list)
    user_name_input = st.text_input("利用者名（使用時のみ入力）")

    # ボタン配置
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("利用開始", type="primary"):
            if user_name_input:
                update_locker(target_id, user_name_input, "使用中")
                st.rerun() # 画面更新
            else:
                st.warning("利用者名を入力してください")
    
    with col_btn2:
        if st.button("返却する"):
            update_locker(target_id, "-", "空き")
            st.rerun() # 画面更新

with col_view:
    st.subheader("📋 現在のロッカー一覧")
    if not df.empty:
        # データフレームを表示（statusで色分けなどはシンプル化のため省略）
        st.dataframe(
            df, 
            column_config={
                "locker_id": "No.",
                "status": "状態",
                "user_name": "利用者",
                "last_updated": "最終更新"
            },
            hide_index=True,
            use_container_width=True
        )
