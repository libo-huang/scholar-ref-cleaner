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

# ==========================================
# 0. 配置与多语言字典 / Configuration & i18n
# ==========================================

st.set_page_config(page_title="Scholar Ref Cleaner Pro", page_icon="🎓", layout="wide")

LANG_DICT = {
    "CN": {
        "title": "🎓 学术文献 AI 幻觉清洗机 (Pro版)",
        "subtitle": "优先使用 Google Scholar，自动降级至 Semantic Scholar 和 Crossref。",
        "sidebar_title": "设置 / Settings",
        "lang_select": "语言 / Language",
        "source_priority": "当前数据源优先级：",
        "instr_title": "📖 使用说明",
        "instr_text": """
        1. **上传文件**：支持 .bib (推荐), .docx (Word), .txt。
        2. **清洗逻辑**：
           - **Step 1**: 尝试 Google Scholar (最全，但容易触发验证码)。
           - **Step 2**: 失败则切换 Semantic Scholar (免费，稳定)。
           - **Step 3**: 再次失败则尝试 Crossref (出版商官方数据)。
        3. **结果**：
           - 相似度 > 85%：自动修正元数据。
           - 相似度 < 50%：标记为“幻觉/不存在”。
        """,
        "upload_label": "上传参考文献文件",
        "btn_start": "开始清洗 / Start Cleaning",
        "status_processing": "正在处理",
        "col_original": "原标题",
        "col_status": "状态",
        "col_source": "来源",
        "download_bib": "📥 下载清洗后的 .bib",
        "download_report": "📥 下载验证报告 (.txt)",
        "warn_gs": "⚠️ 注意：Google Scholar 在云端部署极易被封锁 IP。如果处理速度变慢或报错，系统会自动切换到后续数据源，请耐心等待。",
        "tab_bib": "BibTeX 模式",
        "tab_doc": "Word/文本 模式"
    },
    "EN": {
        "title": "🎓 Scholar Ref Cleaner Pro",
        "subtitle": "Prioritizes Google Scholar, cascades to Semantic Scholar and Crossref.",
        "sidebar_title": "Settings",
        "lang_select": "Language",
        "source_priority": "Data Source Priority:",
        "instr_title": "📖 Instructions",
        "instr_text": """
        1. **Upload**: Supports .bib (Recommended), .docx, .txt.
        2. **Logic**:
           - **Step 1**: Try Google Scholar (Best coverage, strict rate limits).
           - **Step 2**: Fallback to Semantic Scholar (Stable, Free).
           - **Step 3**: Fallback to Crossref (Official Publisher Data).
        3. **Output**:
           - Similarity > 85%: Auto-correct metadata.
           - Similarity < 50%: Flagged as Hallucination.
        """,
        "upload_label": "Upload Reference File",
        "btn_start": "Start Cleaning",
        "status_processing": "Processing",
        "col_original": "Original Title",
        "col_status": "Status",
        "col_source": "Source",
        "download_bib": "📥 Download Cleaned .bib",
        "download_report": "📥 Download Report (.txt)",
        "warn_gs": "⚠️ Note: Google Scholar blocks cloud IPs easily. The system will auto-switch to other sources if GS fails.",
        "tab_bib": "BibTeX Mode",
        "tab_doc": "Word/Text Mode"
    }
}

# 初始化 Session State
if 'lang' not in st.session_state:
    st.session_state['lang'] = 'CN'

# 侧边栏
with st.sidebar:
    st.header("⚙️ " + LANG_DICT[st.session_state['lang']]['sidebar_title'])
    lang_choice = st.radio("Language", ["中文", "English"], index=0 if st.session_state['lang']=='CN' else 1)
    if lang_choice == "中文": st.session_state['lang'] = 'CN'
    else: st.session_state['lang'] = 'EN'
    
    st.info(f"**{LANG_DICT[st.session_state['lang']]['source_priority']}**\n\n1. Google Scholar\n2. Semantic Scholar\n3. Crossref")

T = LANG_DICT[st.session_state['lang']]

# ==========================================
# 1. 核心搜索逻辑 (Waterfall) / Core Logic
# ==========================================

def search_google_scholar(query):
    """尝试 Google Scholar"""
    try:
        search_query = scholarly.search_pubs(query)
        result = next(search_query) # 获取第一个结果
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
    """尝试 Semantic Scholar"""
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
    """尝试 Crossref"""
    url = "https://api.crossref.org/works"
    params = {"query.bibliographic": query, "rows": 1}
    try:
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            items = r.json()['message']['items']
            if items:
                item = items[0]
                # Crossref 返回的日期比较复杂
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
    """瀑布流搜索控制器"""
    # 1. Google Scholar (加延迟防止秒封)
    time.sleep(random.uniform(1, 2)) 
    res = search_google_scholar(query)
    if res: return res

    # 2. Semantic Scholar
    time.sleep(0.5)
    res = search_semantic_scholar(query)
    if res: return res

    # 3. Crossref
    time.sleep(0.5)
    res = search_crossref(query)
    if res: return res

    return None

# ==========================================
# 2. 界面构建 / UI Builder
# ==========================================

st.title(T['title'])
st.markdown(T['subtitle'])

with st.expander(T['instr_title'], expanded=True):
    st.markdown(T['instr_text'])
    st.warning(T['warn_gs'])

tab1, tab2 = st.tabs([T['tab_bib'], T['tab_doc']])

# --- TAB 1: BibTeX ---
with tab1:
    uploaded_bib = st.file_uploader(T['upload_label'] + " (.bib)", type="bib", key="bib_up")
    
    if uploaded_bib and st.button(T['btn_start'], key="btn_bib"):
        bib_db = bibtexparser.load(uploaded_bib)
        cleaned_entries = []
        report_data = []
        
        progress = st.progress(0)
        status_text = st.empty()
        
        total = len(bib_db.entries)
        for i, entry in enumerate(bib_db.entries):
            progress.progress((i + 1) / total)
            original_title = entry.get('title', '').replace('{','').replace('}','').replace('\n',' ')
            
            if not original_title:
                continue

            status_text.text(f"{T['status_processing']}: {original_title[:40]}...")
            
            # 执行搜索
            found_data = waterfall_search(original_title)
            
            row = {
                T['col_original']: original_title,
                T['col_status']: "❌ Not Found",
                T['col_source']: "-"
            }

            if found_data:
                # 计算相似度
                sim = fuzz.ratio(original_title.lower(), found_data['title'].lower())
                row[T['col_source']] = found_data['source']
                
                if sim > 85:
                    row[T['col_status']] = f"✅ Verified ({sim}%)"
                    # 更新 Bib 数据
                    entry['title'] = found_data['title']
                    if found_data['year']: entry['year'] = str(found_data['year'])
                    if found_data['author']: entry['author'] = found_data['author']
                    if found_data['journal']: entry['journal'] = found_data['journal']
                    entry['note'] = f"Verified by {found_data['source']}"
                elif sim > 50:
                    row[T['col_status']] = f"⚠️ Ambiguous ({sim}%)"
                    entry['note'] = f"Ambiguous match: {found_data['title']}"
                else:
                    row[T['col_status']] = f"❌ Hallucination?"
                    entry['note'] = "Potential Hallucination"
            else:
                entry['note'] = "Not Found in any DB"

            cleaned_entries.append(entry)
            report_data.append(row)
            
        st.success("Done!")
        st.dataframe(report_data)
        
        # 下载 Bib
        db = BibDatabase()
        db.entries = cleaned_entries
        writer = BibTexWriter()
        st.download_button(T['download_bib'], writer.write(db), "cleaned.bib", "text/plain")

# --- TAB 2: Word/Text ---
with tab2:
    uploaded_doc = st.file_uploader(T['upload_label'] + " (.docx, .txt)", type=['docx', 'txt'], key="doc_up")
    
    if uploaded_doc and st.button(T['btn_start'], key="btn_doc"):
        # 读取文本
        lines = []
        if uploaded_doc.name.endswith('.docx'):
            doc = docx.Document(uploaded_doc)
            lines = [p.text for p in doc.paragraphs if len(p.text) > 20] # 忽略短行
        else:
            stringio = io.StringIO(uploaded_doc.getvalue().decode("utf-8"))
            lines = [l.strip() for l in stringio.readlines() if len(l) > 20]
            
        report_txt = "=== Validation Report ===\n\n"
        progress = st.progress(0)
        status_text = st.empty()
        
        for i, line in enumerate(lines):
            progress.progress((i + 1) / len(lines))
            # 简单的清理，假设每行是一个引用
            query_text = line
            # 如果有[1]这种编号，尝试去掉
            if "]" in query_text[:5]: 
                query_text = query_text.split("]", 1)[1].strip()
            
            status_text.text(f"{T['status_processing']}: {query_text[:30]}...")
            
            found_data = waterfall_search(query_text)
            
            report_txt += f"Original: {line}\n"
            if found_data:
                sim = fuzz.partial_ratio(query_text.lower(), found_data['title'].lower())
                if sim > 80:
                    report_txt += f"✅ Match ({found_data['source']}): {found_data['title']} ({found_data['year']})\n"
                else:
                    report_txt += f"⚠️ Low Confidence ({found_data['source']}): Found '{found_data['title']}'\n"
            else:
                report_txt += "❌ Not Found in any database (Likely Hallucination)\n"
            report_txt += "-"*30 + "\n"
            
        st.success("Done!")
        st.text_area("Report", report_txt, height=400)
        st.download_button(T['download_report'], report_txt, "report.txt", "text/plain")
