import streamlit as st
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from scholarly import scholarly
import requests
import docx
from thefuzz import fuzz
import time
import random
import io
import datetime

# ==========================================
# 0. 配置与多语言字典 / Configuration & i18n
# ==========================================

st.set_page_config(page_title="Scholar Ref Cleaner", page_icon="🎓", layout="wide")

LANG_DICT = {
    "CN": {
        "title": "🎓 学术文献 AI 幻觉清洗机",
        "subtitle": """
            **🛡️ AI 参考文献自动清洗机** \\
            上传 BibTeX 或 Word，系统将自动检索全球学术数据库，为您执行“三步走”清洗：
            * **验真**：它是真的吗？(检测是否存在)
            * **纠错**：它是对的吗？(修正元数据)
            * **报告**：下载清洗后的完美引用格式。
            """,
        "sidebar_title": "设置 / Settings",
        "lang_select": "语言 / Language",
        "source_priority": "当前数据源优先级：",
        "instr_title": "📖 使用说明",
        "instr_text": """
        1. **上传文件**：支持 .bib (推荐), .docx (Word), .txt。
        2. **清洗逻辑**：
           - **Step 1**: 尝试 Google Scholar (最全)。
           - **Step 2**: 失败则切换 Semantic Scholar (免费)。
           - **Step 3**: 再次失败则尝试 Crossref。
        3. **结果**：
           - 相似度 > 85%：自动修正元数据。
           - 相似度 < 50%：标记为“幻觉/不存在”。
        """,
        "upload_label": "上传参考文献文件",
        "btn_start": "🚀 开始清洗 / Start Cleaning",
        "col_original": "原标题",
        "col_status": "状态",
        "col_source": "来源",
        "download_bib": "📥 下载清洗后的 .bib",
        "download_report": "📥 下载验证报告 (.txt)",
        "warn_gs": "⚠️ 注意：Google Scholar 极易封锁云端 IP。如果处理变慢，系统会自动切换源，请耐心等待。",
        "tab_bib": "BibTeX 模式",
        "tab_doc": "Word/文本 模式",
        "stat_progress": "处理进度",
        "stat_verified": "成功验证",
        "stat_eta": "预计剩余时间",
        "log_title": "📜 实时处理日志",
        "done_msg": "🎉 清洗完成！"
    },
    "EN": {
        "title": "🎓 Scholar Ref Cleaner",
        "subtitle": """
            **🛡️ AI Reference Auto-Cleaner**\\
            Upload your BibTeX or Word file. We auto-verify against global academic databases in three steps:
            * **Verify**: Is it real? (Existence Check)
            * **Correct**: Is it accurate? (Metadata Auto-Fix)
            * **Report**: Download your perfectly cleaned citations.
            """,
        "sidebar_title": "Settings",
        "lang_select": "Language",
        "source_priority": "Data Source Priority:",
        "instr_title": "📖 Instructions",
        "instr_text": """
        1. **Upload**: Supports .bib (Recommended), .docx, .txt.
        2. **Logic**:
           - **Step 1**: Try Google Scholar.
           - **Step 2**: Fallback to Semantic Scholar.
           - **Step 3**: Fallback to Crossref.
        3. **Output**:
           - Similarity > 85%: Auto-correct metadata.
           - Similarity < 50%: Flagged as Hallucination.
        """,
        "upload_label": "Upload Reference File",
        "btn_start": "🚀 Start Cleaning",
        "col_original": "Original Title",
        "col_status": "Status",
        "col_source": "Source",
        "download_bib": "📥 Download Cleaned .bib",
        "download_report": "📥 Download Report (.txt)",
        "warn_gs": "⚠️ Note: Google Scholar blocks cloud IPs easily. System auto-switches if blocked.",
        "tab_bib": "BibTeX Mode",
        "tab_doc": "Word/Text Mode",
        "stat_progress": "Progress",
        "stat_verified": "Verified",
        "stat_eta": "Est. Time Remaining",
        "log_title": "📜 Live Log",
        "done_msg": "🎉 All Done!"
    }
}

if 'lang' not in st.session_state:
    st.session_state['lang'] = 'CN'

with st.sidebar:
    st.header("⚙️ " + LANG_DICT[st.session_state['lang']]['sidebar_title'])
    lang_choice = st.radio("Language", ["中文", "English"], index=0 if st.session_state['lang']=='CN' else 1)
    if lang_choice == "中文": st.session_state['lang'] = 'CN'
    else: st.session_state['lang'] = 'EN'
    st.info(f"**{LANG_DICT[st.session_state['lang']]['source_priority']}**\n\n1. Google Scholar\n2. Semantic Scholar\n3. Crossref")

T = LANG_DICT[st.session_state['lang']]

# ==========================================
# 1. 核心搜索逻辑 / Core Logic
# ==========================================

def search_google_scholar(query):
    try:
        search_query = scholarly.search_pubs(query)
        result = next(search_query)
        return {
            'title': result['bib'].get('title'),
            'year': result['bib'].get('pub_year'),
            'author': " and ".join(result['bib'].get('author', [])),
            'journal': result['bib'].get('venue'),
            'source': 'Google Scholar'
        }
    except Exception:
        return None

def search_semantic_scholar(query):
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {"query": query, "limit": 1, "fields": "title,authors,year,venue"}
    try:
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200 and r.json()['total'] > 0:
            data = r.json()['data'][0]
            authors = [a['name'] for a in data.get('authors', [])]
            return {
                'title': data.get('title'),
                'year': data.get('year'),
                'author': " and ".join(authors),
                'journal': data.get('venue'),
                'source': 'Semantic Scholar'
            }
    except:
        return None
    return None

def search_crossref(query):
    url = "https://api.crossref.org/works"
    params = {"query.bibliographic": query, "rows": 1}
    try:
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            items = r.json()['message']['items']
            if items:
                item = items[0]
                year = item['published-print']['date-parts'][0][0] if 'published-print' in item else None
                authors = [f"{a.get('given','')} {a.get('family','')}" for a in item.get('author', [])]
                return {
                    'title': item.get('title', [''])[0],
                    'year': year,
                    'author': " and ".join(authors),
                    'journal': item.get('container-title', [''])[0],
                    'source': 'Crossref'
                }
    except:
        return None
    return None

def waterfall_search(query):
    # 稍微随机延迟，模拟人类行为，也方便计算 ETA
    time.sleep(random.uniform(0.8, 1.5)) 
    
    res = search_google_scholar(query)
    if res: return res

    res = search_semantic_scholar(query)
    if res: return res

    res = search_crossref(query)
    if res: return res

    return None

def format_eta(seconds):
    """将秒数转换为人类可读格式"""
    if seconds < 60:
        return f"{int(seconds)}s"
    else:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s"

# ==========================================
# 2. 界面构建 / UI Builder
# ==========================================

st.title(T['title'])
st.markdown(T['subtitle'])

with st.expander(T['instr_title'], expanded=False):
    st.markdown(T['instr_text'])
    st.warning(T['warn_gs'])

tab1, tab2 = st.tabs([T['tab_bib'], T['tab_doc']])

# --- TAB 1: BibTeX ---
with tab1:
    uploaded_bib = st.file_uploader(T['upload_label'] + " (.bib)", type="bib", key="bib_up")
    
    if uploaded_bib:
        bib_db = bibtexparser.load(uploaded_bib)
        total_items = len(bib_db.entries)
        st.info(f"📄 Detected {total_items} entries.")
        
        if st.button(T['btn_start'], key="btn_bib"):
            cleaned_entries = []
            report_data = []
            verified_count = 0
            
            # --- 初始化 UI 占位符 ---
            # 1. 顶部数据看板
            dashboard = st.empty()
            # 2. 进度条
            prog_bar = st.progress(0)
            # 3. 当前正在处理的文本
            status_text = st.empty()
            # 4. 实时日志区域
            log_container = st.expander(T['log_title'], expanded=True)
            
            start_time = time.time()
            
            for i, entry in enumerate(bib_db.entries):
                original_title = entry.get('title', '').replace('{','').replace('}','').replace('\n',' ')
                
                # --- 更新时间与 ETA ---
                elapsed_time = time.time() - start_time
                if i > 0:
                    avg_time = elapsed_time / i
                    remaining_time = avg_time * (total_items - i)
                    eta_str = format_eta(remaining_time)
                else:
                    eta_str = "Calculating..."

                # --- 更新 UI 面板 ---
                with dashboard.container():
                    c1, c2, c3 = st.columns(3)
                    c1.metric(T['stat_progress'], f"{i + 1} / {total_items}")
                    c2.metric(T['stat_verified'], f"{verified_count}", delta_color="normal")
                    c3.metric(T['stat_eta'], eta_str)
                
                prog_bar.progress((i + 1) / total_items)
                status_text.caption(f"🔍 Searching: **{original_title[:50]}...**")

                if not original_title:
                    continue

                # --- 执行核心逻辑 ---
                found_data = waterfall_search(original_title)
                
                row = {
                    T['col_original']: original_title,
                    T['col_status']: "❌ Not Found",
                    T['col_source']: "-"
                }

                log_msg = ""
                if found_data:
                    sim = fuzz.ratio(original_title.lower(), found_data['title'].lower())
                    row[T['col_source']] = found_data['source']
                    
                    if sim > 85:
                        row[T['col_status']] = f"✅ Verified ({sim}%)"
                        entry['title'] = found_data['title']
                        if found_data['year']: entry['year'] = str(found_data['year'])
                        if found_data['author']: entry['author'] = found_data['author']
                        if found_data['journal']: entry['journal'] = found_data['journal']
                        entry['note'] = f"Verified by {found_data['source']}"
                        
                        verified_count += 1
                        log_msg = f"✅ Verified: {found_data['title'][:30]}..."
                    elif sim > 50:
                        row[T['col_status']] = f"⚠️ Ambiguous ({sim}%)"
                        entry['note'] = f"Ambiguous match: {found_data['title']}"
                        log_msg = f"⚠️ Ambiguous: {found_data['title'][:30]}..."
                    else:
                        row[T['col_status']] = f"❌ Hallucination?"
                        entry['note'] = "Potential Hallucination"
                        log_msg = f"❌ Hallucination: {original_title[:30]}..."
                else:
                    entry['note'] = "Not Found in any DB"
                    log_msg = f"❌ Not Found: {original_title[:30]}..."

                # --- 写入实时日志 ---
                log_container.text(f"[{i+1}] {log_msg}")

                cleaned_entries.append(entry)
                report_data.append(row)
            
            # --- 完成 ---
            status_text.empty()
            st.success(T['done_msg'])
            st.balloons()
            
            st.dataframe(report_data, use_container_width=True)
            
            # 下载
            db = BibDatabase()
            db.entries = cleaned_entries
            writer = BibTexWriter()
            st.download_button(T['download_bib'], writer.write(db), "cleaned.bib", "text/plain")

# --- TAB 2: Word/Text ---
with tab2:
    uploaded_doc = st.file_uploader(T['upload_label'] + " (.docx, .txt)", type=['docx', 'txt'], key="doc_up")
    
    if uploaded_doc and st.button(T['btn_start'], key="btn_doc"):
        lines = []
        if uploaded_doc.name.endswith('.docx'):
            doc = docx.Document(uploaded_doc)
            lines = [p.text for p in doc.paragraphs if len(p.text) > 20]
        else:
            stringio = io.StringIO(uploaded_doc.getvalue().decode("utf-8"))
            lines = [l.strip() for l in stringio.readlines() if len(l) > 20]
            
        total_items = len(lines)
        report_txt = "=== Validation Report ===\n\n"
        verified_count = 0
        
        # --- UI Initialization ---
        dashboard = st.empty()
        prog_bar = st.progress(0)
        status_text = st.empty()
        log_container = st.expander(T['log_title'], expanded=True)
        
        start_time = time.time()
        
        for i, line in enumerate(lines):
            # ETA Calc
            elapsed_time = time.time() - start_time
            if i > 0:
                avg_time = elapsed_time / i
                remaining_time = avg_time * (total_items - i)
                eta_str = format_eta(remaining_time)
            else:
                eta_str = "Calculating..."

            with dashboard.container():
                c1, c2, c3 = st.columns(3)
                c1.metric(T['stat_progress'], f"{i + 1} / {total_items}")
                c2.metric(T['stat_verified'], f"{verified_count}")
                c3.metric(T['stat_eta'], eta_str)
            
            prog_bar.progress((i + 1) / total_items)
            
            query_text = line
            if "]" in query_text[:5]: 
                query_text = query_text.split("]", 1)[1].strip()
            
            status_text.caption(f"🔍 Checking: **{query_text[:50]}...**")
            
            found_data = waterfall_search(query_text)
            
            report_txt += f"Original: {line}\n"
            log_msg = ""
            if found_data:
                sim = fuzz.partial_ratio(query_text.lower(), found_data['title'].lower())
                if sim > 80:
                    verified_count += 1
                    report_txt += f"✅ Match ({found_data['source']}): {found_data['title']} ({found_data['year']})\n"
                    log_msg = f"✅ Match: {found_data['title'][:30]}..."
                else:
                    report_txt += f"⚠️ Low Confidence: Found '{found_data['title']}'\n"
                    log_msg = f"⚠️ Low Conf: {found_data['title'][:30]}..."
            else:
                report_txt += "❌ Not Found (Likely Hallucination)\n"
                log_msg = f"❌ Not Found"
            
            report_txt += "-"*30 + "\n"
            log_container.text(f"[{i+1}] {log_msg}")
            
        st.success(T['done_msg'])
        st.text_area("Final Report", report_txt, height=300)
        st.download_button(T['download_report'], report_txt, "report.txt", "text/plain")