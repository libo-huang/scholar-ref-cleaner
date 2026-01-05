import streamlit as st
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from scholarly import scholarly, ProxyGenerator
import requests
from thefuzz import fuzz
import docx
import time
import pandas as pd
import io

# --- 页面设置 ---
st.set_page_config(page_title="AI文献超级清洗机", page_icon="🧬", layout="wide")

# --- 全局状态管理 (用于记录 GS 是否被封锁) ---
if 'gs_fail_count' not in st.session_state:
    st.session_state.gs_fail_count = 0
if 'gs_blocked' not in st.session_state:
    st.session_state.gs_blocked = False

# --- 核心搜索函数群 ---

def search_google_scholar(title):
    """
    优先级 1: Google Scholar
    注意：极易触发验证码，仅作为首选尝试
    """
    if st.session_state.gs_blocked:
        return None, "Blocked"

    try:
        # 增加随机延迟，减少封锁概率
        time.sleep(2) 
        search_query = scholarly.search_pubs(title)
        result = next(search_query) # 获取第一个结果
        
        # 提取关键信息
        bib = result['bib']
        data = {
            'title': bib.get('title'),
            'year': bib.get('pub_year', ''),
            'author': " and ".join(bib.get('author', [])),
            'journal': bib.get('venue', ''),
            'source': 'Google Scholar'
        }
        return data, "Success"
    except StopIteration:
        return None, "Not Found"
    except Exception as e:
        # 记录失败次数，连续失败3次则熔断
        st.session_state.gs_fail_count += 1
        if st.session_state.gs_fail_count >= 3:
            st.session_state.gs_blocked = True
        return None, "Error/Blocked"

def search_semantic_scholar(title):
    """
    优先级 2: Semantic Scholar
    稳定、免费、速度快
    """
    try:
        time.sleep(0.5)
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {"query": title, "limit": 1, "fields": "title,authors,year,venue"}
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data['total'] > 0:
                paper = data['data'][0]
                authors = [a['name'] for a in paper.get('authors', [])]
                return {
                    'title': paper.get('title'),
                    'year': paper.get('year', ''),
                    'author': " and ".join(authors),
                    'journal': paper.get('venue', ''),
                    'source': 'Semantic Scholar'
                }, "Success"
    except:
        pass
    return None, "Not Found"

def search_crossref(title):
    """
    优先级 3: Crossref
    官方数据，但模糊匹配能力稍弱
    """
    try:
        time.sleep(0.5)
        url = "https://api.crossref.org/works"
        params = {"query.bibliographic": title, "rows": 1}
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            items = r.json()['message']['items']
            if items:
                item = items[0]
                authors = [f"{a.get('given','')} {a.get('family','')}" for a in item.get('author', [])]
                return {
                    'title': item.get('title', [''])[0],
                    'year': item.get('created', {}).get('date-parts', [[None]])[0][0],
                    'author': " and ".join(authors),
                    'journal': item.get('container-title', [''])[0],
                    'source': 'Crossref'
                }, "Success"
    except:
        pass
    return None, "Not Found"

def cascaded_search(original_title):
    """
    瀑布流搜索逻辑：GS -> SS -> Crossref
    """
    # 1. Try Google Scholar
    res, status = search_google_scholar(original_title)
    if res: return res
    
    # 2. Try Semantic Scholar
    res, status = search_semantic_scholar(original_title)
    if res: return res

    # 3. Try Crossref
    res, status = search_crossref(original_title)
    if res: return res

    return None

# --- 文件解析辅助函数 ---

def parse_docx(file):
    doc = docx.Document(file)
    text_list = []
    for p in doc.paragraphs:
        if len(p.text.strip()) > 30: # 忽略过短的行
            text_list.append(p.text.strip())
    return text_list

def parse_txt(file):
    stringio = io.StringIO(file.getvalue().decode("utf-8"))
    return [line.strip() for line in stringio.readlines() if len(line.strip()) > 30]

# --- 界面 UI ---

st.markdown("""
# 🧬 AI 文献超级清洗机
### 支持 BibTeX / Word / TXT | 多源校对 (Google Scholar > Semantic > Crossref)
""")

with st.expander("📖 **使用说明 (点击展开)**", expanded=True):
    st.markdown("""
    1. **功能**：自动检测 AI 生成的“幻觉”文献，修正年份、作者和期刊。
    2. **数据源优先级**：
       - 🥇 **Google Scholar** (最全，但容易被反爬拦截，拦截后自动跳过)
       - 🥈 **Semantic Scholar** (稳定，主力数据源)
       - 🥉 **Crossref** (官方 DOI 数据，最后兜底)
    3. **支持格式**：
       - **.bib**: 输出修正后的 .bib 文件，可直接导入 LaTeX。
       - **.docx / .txt**: 逐行读取参考文献列表，输出校对报告。
    """)

# --- 侧边栏设置 ---
with st.sidebar:
    st.header("⚙️ 设置")
    use_gs = st.checkbox("启用 Google Scholar", value=True, help="如果不勾选，将直接使用 Semantic Scholar，速度更快且稳定。")
    if not use_gs:
        st.session_state.gs_blocked = True
    
    st.info("💡 提示：Word 文档请确保每条参考文献占一行。")

# --- 主逻辑区 ---
upload_type = st.radio("选择上传文件类型", ["BibTeX (.bib)", "Word文档 (.docx) / 文本 (.txt)"], horizontal=True)
uploaded_file = st.file_uploader("上传文件", type=['bib', 'docx', 'txt'])

if uploaded_file:
    # ------------------ 处理 BIB 文件 ------------------
    if upload_type == "BibTeX (.bib)" and uploaded_file.name.endswith('.bib'):
        bib_db = bibtexparser.load(uploaded_file)
        st.write(f"📊 识别到 {len(bib_db.entries)} 条文献")
        
        if st.button("开始清洗", type="primary"):
            cleaned_entries = []
            report_data = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, entry in enumerate(bib_db.entries):
                title = entry.get('title', '').replace('{','').replace('}','')
                progress_bar.progress((i + 1) / len(bib_db.entries))
                status_text.text(f"正在处理: {title[:40]}...")

                # 执行搜索
                valid_data = cascaded_search(title)
                
                if valid_data:
                    # 计算相似度
                    sim = fuzz.ratio(title.lower(), valid_data['title'].lower())
                    
                    if sim > 80:
                        # 修正数据
                        entry['title'] = valid_data['title']
                        entry['year'] = str(valid_data['year'])
                        entry['author'] = valid_data['author']
                        entry['journal'] = valid_data['journal']
                        entry['note'] = f"Verified by {valid_data['source']}"
                        
                        report_data.append({
                            "原标题": title,
                            "结果": "✅ 修正",
                            "来源": valid_data['source'],
                            "修正后年份": valid_data['year']
                        })
                    else:
                        entry['note'] = f"Low Confidence Match ({valid_data['source']})"
                        report_data.append({"原标题": title, "结果": "⚠️ 存疑 (标题差异大)", "来源": valid_data['source'], "修正后年份": "-"})
                else:
                    entry['note'] = "POSSIBLE HALLUCINATION"
                    report_data.append({"原标题": title, "结果": "❌ 未找到 (可能是幻觉)", "来源": "-", "修正后年份": "-"})
                
                cleaned_entries.append(entry)

            # 结果展示
            st.success("处理完成！")
            st.dataframe(pd.DataFrame(report_data))
            
            # 下载 Bib
            db = BibDatabase()
            db.entries = cleaned_entries
            writer = BibTexWriter()
            st.download_button("📥 下载清洗后的 .bib", writer.write(db), file_name="cleaned.bib")

    # ------------------ 处理 Word/Txt 文件 ------------------
    elif upload_type == "Word文档 (.docx) / 文本 (.txt)":
        if st.button("开始验证", type="primary"):
            # 读取内容
            if uploaded_file.name.endswith('.docx'):
                lines = parse_docx(uploaded_file)
            else:
                lines = parse_txt(uploaded_file)
            
            st.write(f"📊 提取到 {len(lines)} 行文本")
            
            report_lines = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, line in enumerate(lines):
                progress_bar.progress((i + 1) / len(lines))
                # 简单清洗：去除前面的 [1] 或 1. 
                clean_query = line.split(']')[-1].strip() if ']' in line else line
                # 再次尝试去除数字点 1. 
                if len(clean_query) > 0 and clean_query[0].isdigit():
                    clean_query = clean_query.split('.', 1)[-1].strip()

                status_text.text(f"正在搜索: {clean_query[:30]}...")
                
                valid_data = cascaded_search(clean_query)
                
                report_lines.append(f"🔴 原文: {line}")
                if valid_data:
                    sim = fuzz.token_set_ratio(clean_query, valid_data['title'])
                    if sim > 80:
                        report_lines.append(f"🟢 [✅ 真 - {valid_data['source']}]")
                        report_lines.append(f"    -> 匹配标题: {valid_data['title']}")
                        report_lines.append(f"    -> 年份: {valid_data['year']} | 期刊: {valid_data['journal']}")
                    else:
                        report_lines.append(f"🟡 [⚠️ 存疑 - {valid_data['source']}]")
                        report_lines.append(f"    -> 搜索结果: {valid_data['title']} (相似度低)")
                else:
                    report_lines.append("⚫ [❌ 未找到 - 可能是AI幻觉]")
                report_lines.append("-" * 50)
            
            result_text = "\n".join(report_lines)
            st.text_area("验证报告预览", result_text, height=400)
            st.download_button("📥 下载验证报告 (.txt)", result_text, file_name="verification_report.txt")
    
    else:
        st.warning("请上传与选择类型匹配的文件！")
