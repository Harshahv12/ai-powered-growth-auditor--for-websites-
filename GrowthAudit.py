import streamlit as st
import requests
from bs4 import BeautifulSoup
from google import genai
import plotly.graph_objects as go
import textstat
import time
import json
import re
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


# 1. SETUP & CONFIGURATION
st.set_page_config(page_title="AI Growth Intelligence", layout="wide")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# The Advanced Agency Rubrics
EXPERT_RUBRICS = {
    "Above-the-Fold Clarity": "8-10: Explicitly names the ICP and exact problem solved without scrolling. 5-7: Explains 'What' but misses 'Who/Why'. 1-4: Buzzword salad. NOTE: Penalize if the ML Reading Grade is above 10.",
    "Conversion Psychology": "8-10: Benefit-driven, directly handles objections, explicit Risk Reversal. 5-7: Features dressed up as benefits. 1-4: Self-centered copy.",
    "Technical Maturity": "8-10: Detects both Analytics AND Ads pixels. 5-7: Basic analytics only. 1-4: Flying blind (no tracking).",
    "Authority Transfer": "8-10: Uses specific, verifiable numbers and recognizable logos. 5-7: Generic claims ('Trusted by thousands'). 1-4: Zero external validation.",
    "Full-Funnel Architecture": "8-10: Has BOFU (Pricing/Trial) AND MOFU (Blog/Lead Magnet). 5-7: Missing a safety net for unready buyers. 1-4: Single generic CTA."
}

# 2. HYBRID DATA COLLECTION
@st.cache_data(show_spinner=False)
def fetch_and_read_website_data(website_url):
    """Gets website data and finds basic tech tools and reading toughness."""
    clean_url = website_url.rstrip("/")
    
    try:
        web_response = requests.get(clean_url, headers=HEADERS, timeout=12)
        website_html_code = web_response.text
        parsed_webpage = BeautifulSoup(website_html_code, "html.parser")
        
        extracted_text = ""
        text_elements = parsed_webpage.find_all(["h1", "h2", "p", "a"])
        
        for element in text_elements[:25]:
            extracted_text = extracted_text + element.text.strip() + " "
        
        html_in_lowercase = website_html_code.lower()
        installed_tools = []
        
        if "gtag" in html_in_lowercase or "google-analytics" in html_in_lowercase: 
            installed_tools.append("Google Analytics")
        if "fbq" in html_in_lowercase or "connect.facebook.net" in html_in_lowercase: 
            installed_tools.append("Meta Ads")
        if "hubspot" in html_in_lowercase: 
            installed_tools.append("HubSpot")
        
        all_links_on_page = parsed_webpage.find_all('a')
        has_blog_page = "No"
        has_pricing_page = "No"
        
        for link in all_links_on_page:
            link_url = link.get('href', '')
            if type(link_url) == str:
                link_url_lower = link_url.lower()
                if "blog" in link_url_lower:
                    has_blog_page = "Yes"
                if "pricing" in link_url_lower:
                    has_pricing_page = "Yes"
        
        reading_difficulty_score = textstat.flesch_kincaid_grade(extracted_text)
        
        return {
            "url": clean_url, 
            "text": extracted_text[:2000], 
            "tech": installed_tools, 
            "blog": has_blog_page, 
            "pricing": has_pricing_page,
            "ml_grade": reading_difficulty_score
        }
        
    except Exception as error:
        return None


# 3. THE AI (KEY Processing) LOOP
def ask_gemini_json(api_key, prompt):
    """Helper function with Automatic Model Fallback."""
    client = genai.Client(api_key=api_key)
    
    try:
        raw_response = client.models.generate_content(model="gemma-3-27b-it", contents=prompt).text
    except Exception as e:
        print("Flash model overloaded. Switching to Pro...")
        time.sleep(2)
        raw_response = client.models.generate_content(model="gemini-2.5-pro", contents=prompt).text
        
    clean_json = re.sub(r"```json|```", "", raw_response).strip()
    return json.loads(clean_json)

@st.cache_data(show_spinner=False)
def generate_intelligence_report(target_data, competitor_data, api_key):
    final_report = {}
    progress_bar = st.progress(0)
    
    step = 1
    for category, rubric in EXPERT_RUBRICS.items():
        st.write(f"AI Agent analyzing: {category}...")
        
        prompt = f"""
        Act as an elite Growth Consultant. Grade these two companies strictly on: {category}.
        
        TARGET: {target_data['url']} | ML Reading Grade: {target_data['ml_grade']} | Tech: {target_data['tech']} | Funnel: Blog({target_data['blog']}), Pricing({target_data['pricing']})
        Text: {target_data['text']}
        
        COMPETITOR: {competitor_data['url']} | ML Reading Grade: {competitor_data['ml_grade']} | Tech: {competitor_data['tech']} | Funnel: Blog({competitor_data['blog']}), Pricing({competitor_data['pricing']})
        Text: {competitor_data['text']}
        
        Strict Rubric: {rubric}
        
        Return EXACTLY this JSON format (no markdown):
        {{"target_score": 8, "competitor_score": 6, "target_analysis": "2 short sentences", "competitor_analysis": "2 short sentences", "key_gap": "1 sentence explaining the gap"}}
        """
        try:
            final_report[category] = ask_gemini_json(api_key, prompt)
        except:
            final_report[category] = {"target_score": 5, "competitor_score": 5, "target_analysis": "Analysis failed.", "competitor_analysis": "Analysis failed.", "key_gap": "Data parsing error."}
            
        progress_bar.progress(step / len(EXPERT_RUBRICS))
        step += 1
        time.sleep(1) 
        
    progress_bar.empty()
    return final_report

@st.cache_data(show_spinner=False)
def generate_executive_summary(target_url, final_report, api_key):
    gaps = "\n".join([f"- {data['key_gap']}" for data in final_report.values()])
    
    prompt = f"""
    Based on these competitive gaps: {gaps}.
    Write a 1-sentence brutal verdict summarizing the competitive position.
    
    Return EXACTLY this JSON format:
    {{"verdict": "string"}}
    """
    return ask_gemini_json(api_key, prompt)

# 4. EXPORT GENERATORS
def create_radar_chart(report_data):
    categories_list = list(report_data.keys())
    target_scores = []
    competitor_scores = []
    
    for data in report_data.values():
        target_scores.append(data["target_score"])
        competitor_scores.append(data["competitor_score"])

    # Close the loop for the radar chart
    categories_list.append(categories_list[0])
    target_scores.append(target_scores[0])
    competitor_scores.append(competitor_scores[0])

    chart_figure = go.Figure()
    chart_figure.add_trace(go.Scatterpolar(r=target_scores, theta=categories_list, fill='toself', name="Target", line_color='#e74c3c'))
    chart_figure.add_trace(go.Scatterpolar(r=competitor_scores, theta=categories_list, fill='toself', name="Competitor", line_color='#2ecc71'))
    chart_figure.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10])))
    
    return chart_figure

def create_pdf_document(target_url, competitor_url, report_data, summary_data):
    pdf_memory_buffer = io.BytesIO()
    pdf_document = SimpleDocTemplate(pdf_memory_buffer, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    
    text_styles = {
        "title": ParagraphStyle("T", fontName="Helvetica-Bold", fontSize=20, textColor=colors.HexColor("#1A1A1A"), spaceAfter=15),
        "heading2": ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=14, textColor=colors.HexColor("#1A1A1A"), spaceAfter=10),
        "normal_text": ParagraphStyle("B", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#555555"), leading=14),
        "footer_text": ParagraphStyle("F", fontName="Helvetica", fontSize=8, textColor=colors.grey)
    }
    
    document_elements = [
        Paragraph("Competitive Growth Intelligence", text_styles["title"]),
        Paragraph(f"Target: {target_url} vs. Competitor: {competitor_url}", text_styles["normal_text"]),
        HRFlowable(width="100%", color=colors.lightgrey, spaceBefore=10, spaceAfter=15),
        Paragraph("Executive Verdict", text_styles["heading2"]),
        Paragraph(summary_data["verdict"], text_styles["normal_text"]),
        Spacer(1, 20)
    ]

    for category, data in report_data.items():
        document_elements.append(Paragraph(category, text_styles["heading2"]))
        
        table_rows = [
            [Paragraph(f"Target ({data['target_score']}/10)", text_styles["normal_text"]), Paragraph(f"Competitor ({data['competitor_score']}/10)", text_styles["normal_text"])],
            [Paragraph(data['target_analysis'], text_styles["normal_text"]), Paragraph(data['competitor_analysis'], text_styles["normal_text"])]
        ]
        comparison_table = Table(table_rows, colWidths=[250, 250])
        comparison_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#FAFAFA")), ('PADDING', (0, 0), (-1, -1), 8), ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey)]))
        
        document_elements.append(comparison_table)
        document_elements.append(Spacer(1, 5))
        document_elements.append(Paragraph(f"The Gap: {data['key_gap']}", text_styles["normal_text"]))
        document_elements.append(Spacer(1, 15))
    
    document_elements.append(Spacer(1, 30))
    document_elements.append(Paragraph("Audit Generated by AI Growth Intelligence", text_styles["footer_text"]))
    
    pdf_document.build(document_elements)
    return pdf_memory_buffer.getvalue()


# 5. STREAMLIT USER INTERFACE
st.title("Hybrid AI Growth Teardown")
st.markdown("Combines traditional NLP algorithms with Agentic LLMs for rigorous competitive analysis.")

with st.sidebar:
    st.header("Authentication")
    user_api_key = st.text_input("Gemini API Key", type="password")

col1, col2 = st.columns(2)
target_website = col1.text_input("Target Website", "https://www.razorpay.com")
competitor_website = col2.text_input("Competitor Website", "https://stripe.com/en-in")

if st.button("Initialize Hybrid Pipeline", type="primary"):
    if not user_api_key:
        st.error("Please provide your Gemini API Key in the sidebar.")
        st.stop()
        
    with st.status("Running Data Engineering...", expanded=True) as status_box:
        st.write("Scraping and running ML Readability algorithms...")
        
        target_website_data = fetch_and_read_website_data(target_website)
        competitor_website_data = fetch_and_read_website_data(competitor_website)
        
        if not target_website_data or not competitor_website_data:
            status_box.update(label="Network Error", state="error")
            st.error("Failed to load websites. They may be blocking basic scrapers.")
            st.stop()
            
        st.write("Engaging Agentic AI Framework...")
        report = generate_intelligence_report(target_website_data, competitor_website_data, user_api_key)
        
        st.write("Synthesizing Final Deliverables...")
        exec_summary = generate_executive_summary(target_website, report, user_api_key)
        
        pdf_bytes = create_pdf_document(target_website, competitor_website, report, exec_summary)
        status_box.update(label="Pipeline Complete!", state="complete")
        
    # --- DASHBOARD RENDERING ---
    st.divider()
    
    # Simple addition loop for average scores
    target_total_score = 0
    competitor_total_score = 0
    
    for category_data in report.values():
        target_total_score = target_total_score + category_data["target_score"]
        competitor_total_score = competitor_total_score + category_data["competitor_score"]
        
    target_average_score = target_total_score / len(report)
    competitor_average_score = competitor_total_score / len(report)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Target Overall Score", f"{target_average_score:.1f}/10")
    m2.metric("Competitor Overall Score", f"{competitor_average_score:.1f}/10")
    m3.download_button("Download PDF Report", pdf_bytes, "Growth_Audit.pdf", "application/pdf", use_container_width=True)
    
    st.success(f"Executive Verdict: {exec_summary['verdict']}")
    
    tab1, tab2 = st.tabs(["Detailed Intelligence", "Visual Gap Analysis"])
    
    with tab1:
        st.info(f"Target NLP Reading Grade: {target_website_data['ml_grade']} | Competitor NLP Reading Grade: {competitor_website_data['ml_grade']}")
        for cat, res in report.items():
            st.subheader(cat)
            c1, c2 = st.columns(2)
            c1.markdown(f"**Target ({res['target_score']}/10):** {res['target_analysis']}")
            c2.markdown(f"**Competitor ({res['competitor_score']}/10):** {res['competitor_analysis']}")
            st.markdown(f"**Gap to close:** {res['key_gap']}")
            st.divider()
            
    with tab2:
        st.plotly_chart(create_radar_chart(report), use_container_width=True)