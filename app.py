from pathlib import Path
from tempfile import TemporaryDirectory
import streamlit as st
from src.processor import validate_sales
from src.analysis import analyze_sales
from src.report import create_report

st.set_page_config(page_title="Sales Report Automation", layout="wide")

from src.account_ui import bold_line_chart, bold_bar_chart
from src.account_ui import require_login
require_login()

st.markdown('\n<style>\n.block-container {\n    max-width: 1280px;\n    padding-top: 2.5rem;\n    padding-bottom: 3rem;\n}\n[data-testid="stAppViewContainer"] {\n    background:\n        radial-gradient(ellipse at top right, #12363755, transparent 45%),\n        #0B1120;\n}\n[data-testid="stSidebar"] {\n    background: #10192A;\n    border-right: 1px solid #263449;\n}\n[data-testid="stSidebar"] .block-container {\n    padding-top: 2rem;\n}\n.hero {\n    padding: 30px;\n    margin-bottom: 26px;\n    background: linear-gradient(120deg, #16283D, #103936);\n    border: 1px solid #2D5658;\n    border-radius: 22px;\n}\n.hero-label {\n    color: #5EEAD4;\n    font-size: 12px;\n    font-weight: 700;\n    letter-spacing: 2px;\n    margin-bottom: 12px;\n}\n.hero h1 {\n    color: #F8FAFC;\n    font-size: clamp(28px, 4vw, 42px);\n    font-weight: 750;\n    padding: 0;\n    margin: 0 0 12px;\n    letter-spacing: -1px;\n}\n.hero p {\n    color: #B7C9D5;\n    font-size: 15px;\n    margin: 0;\n    max-width: 680px;\n}\n.hero-tags {\n    display: flex;\n    flex-wrap: wrap;\n    gap: 8px;\n    margin-top: 22px;\n}\n.hero-tags span {\n    padding: 6px 12px;\n    background: #FFFFFF0B;\n    border: 1px solid #FFFFFF20;\n    border-radius: 30px;\n    font-size: 12px;\n    color: #D8E9EE;\n}\n[data-testid="stMetric"] {\n    background: linear-gradient(140deg, #19263B, #111C2E);\n    border: 1px solid #2A3B52;\n    border-top: 3px solid #2DD4BF;\n    padding: 22px;\n    border-radius: 16px;\n    min-height: 135px;\n    box-shadow: 0 8px 24px #00000018;\n}\n[data-testid="stMetricLabel"] {\n    color: #AABCD0;\n}\n[data-testid="stMetricValue"] {\n    color: #F1F5F9;\n    font-weight: 700;\n    font-size: clamp(23px, 2.4vw, 34px);\n}\n[data-testid="stFileUploader"] {\n    background: #131F32;\n    border: 1px dashed #3D6871;\n    border-radius: 18px;\n    padding: 18px;\n    margin-bottom: 22px;\n}\n[data-testid="stFileUploaderDropzone"] {\n    background: transparent;\n}\n.stTabs [data-baseweb="tab-list"] {\n    gap: 8px;\n    background: #111C2E;\n    padding: 8px;\n    border-radius: 14px;\n    margin-top: 24px;\n}\n.stTabs [data-baseweb="tab"] {\n    height: 44px;\n    border-radius: 9px;\n    padding: 0 18px;\n    color: #AFC1D6;\n}\n.stTabs [aria-selected="true"] {\n    background: #234C4C;\n    color: #7CF3DD;\n}\n.stTabs [data-baseweb="tab-highlight"] {\n    background: transparent;\n}\n[data-testid="stDataFrame"] {\n    border: 1px solid #293A50;\n    border-radius: 12px;\n    overflow: hidden;\n}\n[data-testid="stDownloadButton"] button {\n    background: #2DD4BF;\n    color: #082F2B;\n    font-weight: 700;\n    border: 1px solid #2DD4BF;\n    border-radius: 10px;\n    padding: 10px 20px;\n    transition: background 0.2s ease;\n}\n[data-testid="stDownloadButton"] button:hover {\n    background: #5EEAD4;\n    color: #082F2B;\n    border-color: #5EEAD4;\n}\n[data-testid="stDownloadButton"] button:focus-visible {\n    outline: 3px solid #99F6E4;\n    outline-offset: 3px;\n}\n[data-testid="stAlert"] {\n    border-radius: 12px;\n}\n@media (max-width: 640px) {\n    .block-container { padding-top: 1rem; }\n    .hero { padding: 22px; }\n    .stTabs [data-baseweb="tab"] { padding: 0 10px; }\n}\n</style>\n<div class="hero">\n    <div class="hero-label">SALES ANALYTICS WORKSPACE</div>\n    <h1>Your sales. Clearly understood.</h1>\n    <p>Turn spreadsheets into clear insights, review data quality,\n    and create polished Excel reports in one place.</p>\n    <div class="hero-tags">\n        <span>CSV &amp; Excel</span>\n        <span>Data validation</span>\n        <span>Interactive charts</span>\n        <span>Excel export</span>\n    </div>\n</div>\n', unsafe_allow_html=True)


st.markdown('\n<style>\n@keyframes colourFlow {\n    0% { background-position: 0% 50%; }\n    50% { background-position: 100% 50%; }\n    100% { background-position: 0% 50%; }\n}\n.hero {\n    background: linear-gradient(\n        120deg, #173353, #124C48, #34305F, #173353\n    );\n    background-size: 300% 300%;\n    animation: colourFlow 14s ease infinite;\n    box-shadow: 0 12px 45px #14B8A620;\n}\n[data-testid="stMetric"] {\n    transition: transform .22s ease, box-shadow .22s ease,\n                border-color .22s ease;\n}\n@media (hover: hover) {\n    [data-testid="stMetric"]:hover {\n        transform: translateY(-5px);\n        border-color: #5EEAD4;\n        box-shadow: 0 12px 30px #2DD4BF28;\n    }\n    .hero-tags span:hover {\n        background: #2DD4BF25;\n        border-color: #5EEAD4;\n    }\n}\nbutton, [role="tab"], .hero-tags span {\n    transition: transform .15s ease, background .2s ease,\n                box-shadow .2s ease;\n    touch-action: manipulation;\n}\nbutton:active, [role="tab"]:active {\n    transform: scale(.96);\n}\nbutton:focus-visible, [role="tab"]:focus-visible {\n    outline: 3px solid #5EEAD4 !important;\n    outline-offset: 3px;\n}\n[data-testid="stDownloadButton"] button {\n    min-height: 48px;\n    box-shadow: 0 5px 20px #14B8A625;\n}\n.stTabs [data-baseweb="tab"] {\n    min-height: 48px;\n}\n[data-testid="stFileUploader"]:focus-within {\n    border-color: #5EEAD4;\n    box-shadow: 0 0 0 3px #2DD4BF20;\n}\n@media (prefers-reduced-motion: reduce) {\n    .hero { animation: none !important; }\n    button, [role="tab"], [data-testid="stMetric"],\n    .hero-tags span {\n        transition: none !important;\n        transform: none !important;\n    }\n}\n</style>\n', unsafe_allow_html=True)

st.markdown('\n<style>\n[data-testid="stAppViewContainer"] {\n    background:\n        radial-gradient(ellipse at 10% 25%, #F7B9D688, transparent 45%),\n        radial-gradient(ellipse at 90% 55%, #B8BBF088, transparent 45%),\n        linear-gradient(150deg, #F4EEE9, #ECDCF0 55%, #DDDFF7);\n    color: #392052;\n}\n[data-testid="stHeader"] {\n    background: transparent;\n}\n[data-testid="stSidebar"] {\n    background: #F7F0FAE8;\n    border-right: 1px solid #FFFFFFAA;\n}\n[data-testid="stSidebar"] * {\n    color: #44285E;\n}\n.block-container {\n    max-width: 1320px;\n    padding-top: 2rem;\n}\n.pastel-nav {\n    display: flex;\n    align-items: center;\n    justify-content: space-between;\n    flex-wrap: wrap;\n    gap: 12px;\n    margin-bottom: 24px;\n    color: #43205F;\n}\n.pastel-brand {\n    font-size: 29px;\n    font-weight: 800;\n    letter-spacing: -1.3px;\n}\n.pastel-pill {\n    background: #FFFFFF70;\n    border: 1px solid #FFFFFFB0;\n    border-radius: 28px;\n    padding: 12px 22px;\n    backdrop-filter: blur(16px);\n    font-size: 13px;\n}\n.hero {\n    position: relative;\n    isolation: isolate;\n    overflow: hidden;\n    min-height: 350px;\n    padding: 55px 38px;\n    border-radius: 30px;\n    border: 1px solid #FFFFFFCC;\n    background:\n        radial-gradient(ellipse at 75% 80%, #A08BCC88, transparent 50%),\n        linear-gradient(130deg, #F2DCE8, #E7D6F0 55%, #C7D2EF);\n    background-size: auto;\n    animation: none;\n    box-shadow: 0 22px 65px #70508422;\n}\n.hero::before, .hero::after {\n    content: "";\n    position: absolute;\n    z-index: -1;\n    border-radius: 50%;\n    pointer-events: none;\n    background:\n        radial-gradient(circle at 30% 22%, #FFFFFFE6, transparent 24%),\n        radial-gradient(circle at 72% 75%, #E790D48C, transparent 44%),\n        linear-gradient(145deg, #F8E5F999, #A3B9E3AA 50%, #EAA6CFAA);\n    border: 1px solid #FFFFFFAA;\n    box-shadow:\n        inset -15px -20px 35px #754AA344,\n        inset 8px 8px 22px #FFFFFFBB,\n        0 25px 35px #79589433;\n    animation: pastelFloat 8s ease-in-out infinite;\n}\n.hero::before {\n    width: 210px;\n    height: 210px;\n    right: 7%;\n    top: 32px;\n}\n.hero::after {\n    width: 95px;\n    height: 95px;\n    right: 29%;\n    bottom: 25px;\n    animation-delay: -4s;\n}\n@keyframes pastelFloat {\n    0%, 100% { transform: translateY(0) rotate(-5deg); }\n    50% { transform: translateY(-20px) rotate(5deg); }\n}\n.hero-label {\n    color: #79458A;\n    letter-spacing: 2.5px;\n}\n.hero h1 {\n    color: #43205F;\n    max-width: 65%;\n    font-size: clamp(34px, 5vw, 64px);\n    line-height: 1.08;\n    letter-spacing: -2px;\n}\n.hero p {\n    color: #634F76;\n    max-width: 60%;\n}\n.hero-tags span {\n    background: #FFFFFF65;\n    border-color: #FFFFFFAA;\n    color: #55366E;\n    backdrop-filter: blur(12px);\n}\n[data-testid="stMetric"] {\n    background: #FFFFFF8C;\n    border: 1px solid #FFFFFFDD;\n    border-top: 3px solid #BD8ACD;\n    border-radius: 20px;\n    backdrop-filter: blur(16px);\n    box-shadow: 0 10px 30px #68447F12;\n}\n[data-testid="stMetricLabel"],\n[data-testid="stMetricLabel"] * {\n    color: #75617F !important;\n}\n[data-testid="stMetricValue"],\n[data-testid="stMetricValue"] * {\n    color: #43205F !important;\n}\n[data-testid="stFileUploader"] {\n    background: #FFFFFF75;\n    border: 1px dashed #AF8ABD;\n    border-radius: 22px;\n    color: #44285E;\n}\n[data-testid="stFileUploaderDropzone"] {\n    background: #FFFFFF55;\n    color: #44285E;\n}\n[data-testid="stFileUploader"] p,\n[data-testid="stFileUploader"] small {\n    color: #634F76;\n}\n.stTabs [data-baseweb="tab-list"] {\n    background: #FFFFFF60;\n    border: 1px solid #FFFFFFAA;\n}\n.stTabs [data-baseweb="tab"] {\n    color: #644578;\n}\n.stTabs [aria-selected="true"] {\n    background: #DCC4EB;\n    color: #43205F;\n}\n[data-testid="stDownloadButton"] button {\n    background: linear-gradient(120deg, #8756AC, #AD6DA2);\n    color: white;\n    border: 1px solid #FFFFFF70;\n    box-shadow: 0 8px 22px #8756AC30;\n}\n[data-testid="stDownloadButton"] button:hover {\n    background: #754394;\n    color: white;\n    border-color: #FFFFFF;\n}\n[data-testid="stDataFrame"] {\n    border-color: #D4BEDF;\n}\n@media (hover: hover) {\n    [data-testid="stMetric"]:hover {\n        transform: translateY(-6px);\n        border-color: #B47DCC;\n        box-shadow: 0 18px 35px #8756AC25;\n    }\n    .hero-tags span:hover {\n        background: #FFFFFFAA;\n        border-color: #C095D2;\n    }\n}\n@media (max-width: 700px) {\n    .hero { padding: 30px 22px; min-height: 400px; }\n    .hero h1 { max-width: 100%; }\n    .hero p { max-width: 100%; }\n    .hero::before {\n        width: 115px; height: 115px;\n        top: auto; bottom: 12px; right: 12px;\n        opacity: .6;\n    }\n    .hero::after { display: none; }\n}\n@media (prefers-reduced-motion: reduce) {\n    .hero::before, .hero::after { animation: none; }\n}\n</style>\n<div class="pastel-nav">\n    <div class="pastel-brand">Sales Studio</div>\n    <div class="pastel-pill">Explore your data. Discover your growth.</div>\n</div>\n', unsafe_allow_html=True)


mode = st.sidebar.radio(
    "Workspace mode",
    ["Sales dashboard", "Any-data explorer", "Universal studio"],
    key="workspace_mode",
)
if mode == "Universal studio":
    from src.universal import render_universal
    render_universal()
    st.stop()

if mode == "Any-data explorer":
    from src.explorer import render_explorer
    render_explorer()
    st.stop()

with st.sidebar:
    st.header("Required columns")
    st.code("Order_ID,Date,Product,Category,Quantity,Unit_Price")
    st.write("Date: YYYY-MM-DD")
    st.write("Multiple product rows per Order_ID are supported.")
    sample = Path("data/sample_sales.csv")
    if sample.exists():
        st.download_button(
            "Download sample CSV",
            sample.read_bytes(),
            "sample_sales.csv",
            "text/csv",
        )

from src.smart_upload import prepare_upload
sales_payload = prepare_upload()

try:
    with TemporaryDirectory() as temporary:
        folder = Path(temporary)
        source = folder / "mapped_sales.csv"
        source.write_bytes(sales_payload)
        clean, issues = validate_sales(source)
        from src.corrections import correction_editor
        clean, issues = correction_editor(clean, issues)

        a, b = st.columns(2)
        a.metric("Valid rows", len(clean))
        b.metric("Rows needing review", len(issues))

        if not issues.empty:
            st.warning("Rows with issues are excluded from totals.")
            st.dataframe(issues)
            st.download_button(
                "Download validation issues",
                issues.to_csv(index=False).encode("utf-8-sig"),
                "validation_issues.csv",
                "text/csv",
            )

        if clean.empty:
            st.error("No valid rows. Correct the issues and upload again.")
            st.stop()

        from src.workspace import render_workspace
        render_workspace(clean, issues)

except Exception as error:
    st.error(f"Unable to process file: {error}")
