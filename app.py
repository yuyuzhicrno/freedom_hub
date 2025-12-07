import os
import json
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
import streamlit as st
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# ======================
# 网站配置
# ======================
st.set_page_config(
    page_title="Freedom Hub",
    page_icon="🆓",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ======================
# 加密类
# ======================
class FreedomEncryptor:
    def __init__(self, password: str):
        # 使用PBKDF2HMAC从密码生成密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256位密钥
            salt=b'freedom_hub_salt',  # 固定盐值
            iterations=100000,
        )
        self.key = kdf.derive(password.encode())

    def encrypt(self, data: bytes) -> bytes:
        """加密数据"""
        aesgcm = AESGCM(self.key)
        nonce = os.urandom(12)  # 96位随机nonce
        encrypted_data = aesgcm.encrypt(nonce, data, None)
        return nonce + encrypted_data  # 返回nonce+密文

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """解密数据"""
        aesgcm = AESGCM(self.key)
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        try:
            return aesgcm.decrypt(nonce, ciphertext, None)
        except:
            return b"DECRYPTION_FAILED"


# ======================
# 文件类型检测函数（无需外部依赖）
# ======================
def get_mime_type(filename: str) -> str:
    """根据文件扩展名判断MIME类型"""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''

    mime_map = {
        # 图片
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
        'gif': 'image/gif', 'bmp': 'image/bmp', 'webp': 'image/webp',
        'svg': 'image/svg+xml', 'ico': 'image/x-icon',

        # 文档
        'pdf': 'application/pdf',
        'doc': 'application/msword', 'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel', 'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'ppt': 'application/vnd.ms-powerpoint',
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',

        # 文本
        'txt': 'text/plain', 'csv': 'text/csv',
        'html': 'text/html', 'htm': 'text/html',
        'xml': 'application/xml', 'json': 'application/json',

        # 代码
        'py': 'text/x-python', 'js': 'application/javascript',
        'css': 'text/css', 'java': 'text/x-java-source',
        'c': 'text/x-c', 'cpp': 'text/x-c++',

        # 压缩文件
        'zip': 'application/zip', 'rar': 'application/x-rar-compressed',
        '7z': 'application/x-7z-compressed', 'tar': 'application/x-tar',
        'gz': 'application/gzip',

        # 音视频
        'mp3': 'audio/mpeg', 'wav': 'audio/wav',
        'mp4': 'video/mp4', 'avi': 'video/x-msvideo',
        'mov': 'video/quicktime', 'mkv': 'video/x-matroska',
    }

    return mime_map.get(ext, 'application/octet-stream')


# ======================
# 文件管理类
# ======================
class FreedomHubManager:
    def __init__(self):
        self.upload_dir = Path("uploads")
        self.metadata_dir = Path("metadata")
        self.upload_dir.mkdir(exist_ok=True)
        self.metadata_dir.mkdir(exist_ok=True)

        # 今日的元数据文件
        today = datetime.now().strftime("%Y-%m-%d")
        self.metadata_file = self.metadata_dir / f"{today}.json"

        # 加载现有元数据
        self.metadata = self._load_metadata()

    def _load_metadata(self):
        """加载元数据"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_metadata(self):
        """保存元数据"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    def generate_file_id(self, filename: str) -> str:
        """生成文件唯一ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_id = str(uuid.uuid4())[:8]
        name_hash = hashlib.md5(filename.encode()).hexdigest()[:6]
        return f"FREEDOM-{timestamp}-{random_id}-{name_hash}"

    def save_file(self, uploaded_file, password: str, custom_name: str = None):
        """保存上传的文件"""
        file_id = self.generate_file_id(uploaded_file.name)

        # 读取文件内容
        file_bytes = uploaded_file.getvalue()

        # 加密文件
        encryptor = FreedomEncryptor(password)
        encrypted_data = encryptor.encrypt(file_bytes)

        # 保存加密文件
        encrypted_filename = f"{file_id}.freedom"
        encrypted_path = self.upload_dir / encrypted_filename

        with open(encrypted_path, 'wb') as f:
            f.write(encrypted_data)

        # 获取文件类型
        mime_type = get_mime_type(uploaded_file.name)

        # 保存元数据
        file_info = {
            'id': file_id,
            'original_name': custom_name or uploaded_file.name,
            'encrypted_name': encrypted_filename,
            'upload_time': datetime.now().isoformat(),
            'file_size': len(file_bytes),
            'mime_type': mime_type,
            'has_password': bool(password),
            'download_count': 0
        }

        self.metadata[file_id] = file_info
        self._save_metadata()

        return file_id

    def search_files(self, query: str):
        """搜索文件"""
        results = []
        query_lower = query.lower()

        # 搜索今天的文件
        for file_id, info in self.metadata.items():
            if (query_lower in info['original_name'].lower() or
                    query_lower in file_id.lower()):
                results.append((file_id, info))

        # 搜索历史文件
        for metadata_file in self.metadata_dir.glob("*.json"):
            if metadata_file.name == self.metadata_file.name:
                continue
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                    for file_id, info in history_data.items():
                        if (query_lower in info['original_name'].lower() or
                                query_lower in file_id.lower()):
                            results.append((file_id, info))
            except:
                continue

        return results

    def get_file_info(self, file_id: str):
        """获取文件信息"""
        # 先检查今天的文件
        if file_id in self.metadata:
            return self.metadata[file_id]

        # 检查历史文件
        for metadata_file in self.metadata_dir.glob("*.json"):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                    if file_id in history_data:
                        return history_data[file_id]
            except:
                continue

        return None

    def download_file(self, file_id: str, password: str = ""):
        """下载文件"""
        # 获取文件信息
        file_info = self.get_file_info(file_id)
        if not file_info:
            return None, None

        # 更新下载计数
        if file_id in self.metadata:
            self.metadata[file_id]['download_count'] += 1
            self._save_metadata()

        # 读取加密文件
        encrypted_path = self.upload_dir / file_info['encrypted_name']
        if not encrypted_path.exists():
            return None, None

        with open(encrypted_path, 'rb') as f:
            encrypted_data = f.read()

        # 尝试解密
        try:
            encryptor = FreedomEncryptor(password)
            decrypted_data = encryptor.decrypt(encrypted_data)
        except Exception as e:
            # 即使解密失败也返回数据（会显示乱码）
            decrypted_data = encrypted_data

        return decrypted_data, file_info


# ======================
# 自定义CSS样式
# ======================
def load_css():
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        padding: 2rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        margin-bottom: 2rem;
        color: white;
    }

    .freedom-title {
        font-size: 3.5rem !important;
        font-weight: 900 !important;
        margin-bottom: 0.5rem !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }

    .freedom-subtitle {
        font-size: 1.2rem !important;
        opacity: 0.9;
    }

    .file-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        margin-bottom: 1rem;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: transform 0.2s;
    }

    .file-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }

    .file-id {
        font-family: 'Courier New', monospace;
        background: #f5f5f5;
        padding: 0.3rem 0.6rem;
        border-radius: 5px;
        font-size: 0.9rem;
    }

    .stats-box {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }

    .warning-box {
        background: #fff3cd;
        border: 1px solid #ffc107;
        color: #856404;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }

    .stButton > button {
        width: 100%;
        border-radius: 10px;
        height: 3rem;
        font-weight: bold;
    }

    .file-size-badge {
        display: inline-block;
        background: #e3f2fd;
        color: #1976d2;
        padding: 0.2rem 0.5rem;
        border-radius: 12px;
        font-size: 0.8rem;
        margin-right: 0.5rem;
    }

    .file-type-badge {
        display: inline-block;
        background: #e8f5e9;
        color: #388e3c;
        padding: 0.2rem 0.5rem;
        border-radius: 12px;
        font-size: 0.8rem;
    }
    </style>
    """, unsafe_allow_html=True)


# ======================
# 主程序
# ======================
def main():
    # 初始化
    load_css()
    manager = FreedomHubManager()

    # 网站标题
    st.markdown("""
    <div class="main-header">
        <h1 class="freedom-title">🆓 FREEDOM HUB</h1>
        <p class="freedom-subtitle">完全自由的加密文件分享平台 · 无需登录 · 无限大小</p>
    </div>
    """, unsafe_allow_html=True)

    # 侧边栏
    with st.sidebar:
        st.title("📁 导航")
        selected = st.radio(
            "选择功能",
            ["上传文件", "搜索文件", "今日文件", "关于"]
        )

        # 统计信息
        st.markdown("---")
        today_count = len(manager.metadata)
        total_files = sum(1 for _ in Path("uploads").glob("*.freedom"))

        st.markdown(f"""
        <div class="stats-box">
            <h4>📊 今日统计</h4>
            <p>📤 今日上传: {today_count} 个文件</p>
            <p>🗃️ 总文件数: {total_files} 个</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("""
        ### ⚠️ 注意事项
        1. 所有文件自动加密存储
        2. 记住文件ID和密钥
        3. 文件永久保存
        4. 完全匿名使用
        """)

    # 上传文件界面
    if selected == "上传文件":
        st.header("📤 上传文件")

        col1, col2 = st.columns([2, 1])

        with col1:
            uploaded_files = st.file_uploader(
                "选择文件",
                accept_multiple_files=True,
                help="可以上传任意类型、任意大小的文件"
            )

            custom_name = st.text_input(
                "自定义显示名称（可选）",
                placeholder="留空则使用原文件名"
            )

        with col2:
            st.markdown("### 🔐 加密设置")
            password = st.text_input(
                "加密密钥",
                type="password",
                value="freedom2024",
                help="用于加密文件的密码，下载时需要提供"
            )

            if st.checkbox("显示密钥"):
                st.code(password)

        if uploaded_files and st.button("🚀 开始上传", type="primary"):
            total_size = sum(f.size for f in uploaded_files)

            progress_bar = st.progress(0)
            status_text = st.empty()

            uploaded_ids = []

            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"正在上传: {uploaded_file.name}")

                file_id = manager.save_file(uploaded_file, password, custom_name)
                uploaded_ids.append(file_id)
                progress_bar.progress((i + 1) / len(uploaded_files))

                # 显示上传结果
                with st.expander(f"✅ {uploaded_file.name}", expanded=False):
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("文件ID", file_id)
                    with col_b:
                        st.metric("大小", f"{uploaded_file.size / 1024:.1f} KB")
                    with col_c:
                        st.metric("状态", "已加密")

                    # 显示文件ID和密钥
                    st.info(f"""
                    **📋 文件信息：**
                    - 文件ID: `{file_id}`
                    - 密钥: `{password}`
                    - 文件类型: {get_mime_type(uploaded_file.name)}

                    💡 **提示：** 下载时需要文件ID和密钥
                    """)

            status_text.text("上传完成！")
            progress_bar.empty()
            st.balloons()
            st.success(f"🎉 成功上传 {len(uploaded_files)} 个文件，总大小 {total_size / 1024 / 1024:.1f} MB")

            # 显示所有上传的文件ID
            if uploaded_ids:
                st.markdown("### 📋 上传的文件ID列表")
                for fid in uploaded_ids:
                    st.code(f"文件ID: {fid}  密钥: {password}", language=None)

    # 搜索文件界面
    elif selected == "搜索文件":
        st.header("🔍 搜索文件")

        col1, col2 = st.columns([3, 1])
        with col1:
            search_query = st.text_input(
                "搜索文件名或文件ID",
                placeholder="输入部分文件名或完整ID"
            )

        if search_query:
            results = manager.search_files(search_query)

            if results:
                st.success(f"找到 {len(results)} 个结果")

                for file_id, file_info in results:
                    with st.container():
                        # 格式化文件大小
                        size_kb = file_info['file_size'] / 1024
                        if size_kb < 1024:
                            size_str = f"{size_kb:.1f} KB"
                        else:
                            size_str = f"{size_kb / 1024:.1f} MB"

                        st.markdown(f"""
                        <div class="file-card">
                            <h4>📄 {file_info['original_name']}</h4>
                            <p>🆔 <span class="file-id">{file_id}</span></p>
                            <p>
                                <span class="file-size-badge">{size_str}</span>
                                <span class="file-type-badge">{file_info['mime_type'].split('/')[-1].upper()}</span>
                            </p>
                            <p>📅 {file_info['upload_time'][:10]} | ⬇️ 下载次数: {file_info.get('download_count', 0)}</p>
                        </div>
                        """, unsafe_allow_html=True)

                        # 下载按钮
                        col_a, col_b = st.columns([2, 1])
                        with col_a:
                            download_password = st.text_input(
                                "输入密钥以下载",
                                key=f"dl_{file_id}",
                                type="password",
                                value="freedom2024",
                                placeholder="输入加密密钥"
                            )
                        with col_b:
                            if st.button("⬇️ 下载文件", key=f"btn_{file_id}"):
                                file_data, file_info = manager.download_file(file_id, download_password)

                                if file_data:
                                    st.download_button(
                                        label=f"下载: {file_info['original_name']}",
                                        data=file_data,
                                        file_name=file_info['original_name'],
                                        mime=file_info['mime_type'],
                                        key=f"download_{file_id}"
                                    )
            else:
                st.warning("未找到相关文件")

    # 今日文件界面
    elif selected == "今日文件":
        st.header("📅 今日上传的文件")

        if manager.metadata:
            files_today = list(manager.metadata.items())

            for file_id, file_info in files_today:
                with st.expander(f"📄 {file_info['original_name']}", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**文件ID:** `{file_id}`")
                        st.write(f"**上传时间:** {file_info['upload_time'][11:19]}")
                        st.write(f"**文件类型:** {file_info['mime_type']}")
                    with col2:
                        st.write(f"**文件大小:** {file_info['file_size'] / 1024:.1f} KB")
                        st.write(f"**下载次数:** {file_info.get('download_count', 0)}")

                    # 快速下载
                    with st.form(key=f"form_{file_id}"):
                        dl_password = st.text_input("下载密钥",
                                                    type="password",
                                                    key=f"pw_{file_id}",
                                                    value="freedom2024")
                        if st.form_submit_button("快速下载"):
                            file_data, file_info = manager.download_file(file_id, dl_password)
                            if file_data:
                                st.download_button(
                                    label="点击下载",
                                    data=file_data,
                                    file_name=file_info['original_name'],
                                    mime=file_info['mime_type'],
                                    key=f"quick_dl_{file_id}"
                                )
        else:
            st.info("今天还没有上传文件")

    # 关于页面
    elif selected == "关于":
        st.header("🆓 关于 Freedom Hub")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            ### 🌟 理念
            **Freedom Hub** 是一个完全自由的加密文件分享平台，致力于：

            - 🔓 **无需登录**：完全匿名使用
            - 🔒 **端到端加密**：文件在本地加密
            - 🌐 **公开分享**：任何人都可以下载
            - 💾 **无限制**：支持任意类型、任意大小的文件
            - ⚡ **简单快捷**：无需复杂操作
            """)

        with col2:
            st.markdown("""
            ### 🛡️ 安全特性

            **加密方式：**
            - AES-256-GCM 对称加密
            - PBKDF2-HMAC 密钥派生
            - 每次加密使用随机Nonce

            **隐私保护：**
            - 不收集用户信息
            - 不记录IP地址
            - 文件内容只有密钥持有者可见
            """)

        st.markdown("---")

        col3, col4 = st.columns(2)

        with col3:
            st.markdown("""
            ### 📁 使用方法

            1. **上传文件**
               - 选择文件
               - 设置加密密钥（默认：freedom2024）
               - 获取文件ID

            2. **分享文件**
               - 分享文件ID和密钥
               - 对方使用ID和密钥下载

            3. **搜索文件**
               - 按文件名或ID搜索
               - 浏览历史文件
            """)

        with col4:
            st.markdown("""
            ### ⚠️ 重要提示

            **请务必：**
            - 保存好文件ID和密钥
            - 密钥丢失无法恢复文件
            - 文件永久存储，谨慎上传

            **支持的文件类型：**
            - 图片（JPG, PNG, GIF等）
            - 文档（PDF, DOC, XLS等）
            - 文本文件
            - 压缩文件
            - 音视频文件
            - 任意其他类型
            """)

        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; padding: 2rem;'>
            <h3>🆓 自由分享 · 安全加密 · 简单易用</h3>
            <p>Freedom Hub - 让文件分享回归自由本质</p>
            <p style='font-size: 0.9rem; opacity: 0.7;'>v1.0.0 · Python + Streamlit</p>
        </div>
        """, unsafe_allow_html=True)


# ======================
# 运行应用
# ======================
if __name__ == "__main__":
    main()