import streamlit as st

from detector import analyze_message

import re
import json
import os
import shutil
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="UPI Shield",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# SESSION STATE
# =========================================================

if "message_input" not in st.session_state:
    st.session_state.message_input = ""

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if "analysis_history" not in st.session_state:
    st.session_state.analysis_history = []

if "ocr_text" not in st.session_state:
    st.session_state.ocr_text = ""

if "ocr_result" not in st.session_state:
    st.session_state.ocr_result = None

if "ocr_intelligence" not in st.session_state:
    st.session_state.ocr_intelligence = None


# =========================================================
# CUSTOM CSS
# =========================================================

st.markdown(
    """
    <style>

    .stApp {
        background-color: #080b14;
    }

    [data-testid="stSidebar"] {
        background-color: #0d1220;
        border-right: 1px solid #263244;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1250px;
    }

    div[data-testid="stMetric"] {
        background-color: #111827;
        border: 1px solid #263244;
        padding: 18px;
        border-radius: 14px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# TESSERACT CONFIGURATION
# =========================================================

def configure_tesseract():
    """
    Automatically locate Tesseract OCR on Windows/Linux/macOS.
    Returns True if Tesseract executable is available.
    """

    # First check PATH
    tesseract_path = shutil.which("tesseract")

    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        return True

    # Common Windows installation locations
    windows_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(
            r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"
        )
    ]

    for path in windows_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return True

    return False


TESSERACT_AVAILABLE = configure_tesseract()


# =========================================================
# OCR IMAGE PREPROCESSING
# =========================================================

def preprocess_image(image):
    """
    Improve screenshot quality before OCR.
    """

    # Convert to RGB
    image = image.convert("RGB")

    # Resize image for better OCR
    width, height = image.size

    scale = 2

    image = image.resize(
        (
            width * scale,
            height * scale
        ),
        Image.Resampling.LANCZOS
    )

    # Convert to grayscale
    image = ImageOps.grayscale(image)

    # Increase contrast
    enhancer = ImageEnhance.Contrast(image)

    image = enhancer.enhance(2.0)

    # Sharpen
    image = image.filter(
        ImageFilter.SHARPEN
    )

    # Improve brightness slightly
    brightness = ImageEnhance.Brightness(image)

    image = brightness.enhance(1.1)

    return image


# =========================================================
# OCR EXTRACTION
# =========================================================

def extract_text_from_image(image):
    """
    Extract text from screenshot using Tesseract OCR.
    """

    if not TESSERACT_AVAILABLE:
        raise RuntimeError(
            "Tesseract OCR is not installed or could not be found."
        )

    processed_image = preprocess_image(image)

    # OCR configuration
    custom_config = (
        "--oem 3 --psm 6"
    )

    text = pytesseract.image_to_string(
        processed_image,
        config=custom_config,
        lang="eng"
    )

    return text.strip()


# =========================================================
# OCR CONFIDENCE
# =========================================================

def get_ocr_confidence(image):
    """
    Calculate approximate OCR confidence.
    """

    if not TESSERACT_AVAILABLE:
        return 0

    processed_image = preprocess_image(image)

    data = pytesseract.image_to_data(
        processed_image,
        output_type=pytesseract.Output.DICT,
        config="--oem 3 --psm 6",
        lang="eng"
    )

    confidence_values = []

    for confidence in data["conf"]:

        try:
            value = float(confidence)

            if value >= 0:
                confidence_values.append(value)

        except:
            pass

    if not confidence_values:
        return 0

    return round(
        sum(confidence_values)
        / len(confidence_values)
    )


# =========================================================
# URL DETECTION
# =========================================================

def detect_urls(text):

    if not text:
        return []

    pattern = r"(https?://[^\s]+|www\.[^\s]+)"

    urls = re.findall(
        pattern,
        text,
        flags=re.IGNORECASE
    )

    cleaned = []

    for url in urls:

        url = url.rstrip(
            ".,!?;:)]}"
        )

        if url not in cleaned:
            cleaned.append(url)

    return cleaned


# =========================================================
# UPI ID DETECTION
# =========================================================

def detect_upi_ids(text):

    if not text:
        return []

    pattern = (
        r"\b[a-zA-Z0-9._-]+"
        r"@[a-zA-Z0-9.-]+\b"
    )

    matches = re.findall(
        pattern,
        text
    )

    result = []

    for item in matches:

        if item.lower().endswith(
            (
                "@gmail.com",
                "@yahoo.com",
                "@outlook.com",
                "@hotmail.com"
            )
        ):
            continue

        if item not in result:
            result.append(item)

    return result


# =========================================================
# UPI PAYMENT LINK DETECTION
# =========================================================

def detect_upi_payment_links(text):

    if not text:
        return []

    pattern = r"upi://pay\?[^\s]+"

    return re.findall(
        pattern,
        text,
        flags=re.IGNORECASE
    )


# =========================================================
# UPI LINK INFORMATION
# =========================================================

def extract_upi_link_information(text):

    links = detect_upi_payment_links(text)

    information = []

    for link in links:

        try:

            parsed = urlparse(link)

            params = parse_qs(
                parsed.query
            )

            upi_id = params.get(
                "pa",
                ["Not detected"]
            )[0]

            amount = params.get(
                "am",
                ["Not detected"]
            )[0]

            information.append(
                {
                    "upi_id": upi_id,
                    "amount": amount,
                    "link": link
                }
            )

        except Exception:
            pass

    return information


# =========================================================
# AMOUNT DETECTION
# =========================================================

def detect_amounts(text):

    if not text:
        return []

    patterns = [

        r"₹\s?[0-9,]+(?:\.[0-9]+)?",

        r"Rs\.?\s?[0-9,]+(?:\.[0-9]+)?",

        r"INR\s?[0-9,]+(?:\.[0-9]+)?"
    ]

    amounts = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        for amount in matches:

            if amount not in amounts:
                amounts.append(amount)

    return amounts


# =========================================================
# PAYMENT INTELLIGENCE
# =========================================================

def extract_payment_intelligence(text):

    urls = detect_urls(text)

    upi_ids = detect_upi_ids(text)

    upi_links = detect_upi_payment_links(text)

    upi_link_info = (
        extract_upi_link_information(text)
    )

    amounts = detect_amounts(text)

    return {
        "urls": urls,
        "upi_ids": upi_ids,
        "upi_links": upi_links,
        "upi_link_info": upi_link_info,
        "amounts": amounts
    }


# =========================================================
# RISK MESSAGE
# =========================================================

def get_risk_message(risk_level):

    level = risk_level.upper()

    if level == "HIGH":

        return (
            "🚨 High-risk message detected. "
            "Do not make the requested payment until "
            "the sender is independently verified."
        )

    if level == "MEDIUM":

        return (
            "⚠️ Suspicious indicators were detected. "
            "Verify the sender and payment request carefully."
        )

    return (
        "🟢 No strong scam pattern was detected. "
        "Continue to verify payment requests before paying."
    )


# =========================================================
# REPORT CREATION
# =========================================================

def create_report(
    result,
    message,
    intelligence
):

    report = {

        "application":
            "UPI Shield",

        "generated_at":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "message":
            message,

        "risk_score":
            result.get(
                "risk_score",
                0
            ),

        "risk_level":
            result.get(
                "risk_level",
                "LOW"
            ),

        "detected_signals":
            result.get(
                "detected",
                []
            ),

        "explanations":
            result.get(
                "explanations",
                []
            ),

        "payment_information":
            result.get(
                "payment_info",
                {}
            ),

        "url_detection":
            intelligence
    }

    return report


# =========================================================
# REPORT TO TEXT
# =========================================================

def report_to_text(report):

    lines = []

    lines.append(
        "========================================"
    )

    lines.append(
        "              UPI SHIELD"
    )

    lines.append(
        "        SECURITY ANALYSIS REPORT"
    )

    lines.append(
        "========================================"
    )

    lines.append("")

    lines.append(
        f"Generated: "
        f"{report['generated_at']}"
    )

    lines.append(
        f"Risk Score: "
        f"{report['risk_score']}/100"
    )

    lines.append(
        f"Risk Level: "
        f"{report['risk_level']}"
    )

    lines.append("")

    lines.append("MESSAGE")

    lines.append(
        report["message"]
    )

    lines.append("")

    lines.append(
        "DETECTED SIGNALS"
    )

    for item in report[
        "detected_signals"
    ]:

        if isinstance(
            item,
            dict
        ):

            category = item.get(
                "category",
                "Unknown"
            )

            score = item.get(
                "score",
                0
            )

            try:
                confidence = round(
                    float(score) * 100
                )
            except:
                confidence = 0

            lines.append(
                f"- {category}: "
                f"{confidence}% confidence"
            )

        else:

            lines.append(
                f"- {item}"
            )

    lines.append("")

    lines.append(
        "EXPLANATIONS"
    )

    for explanation in report[
        "explanations"
    ]:

        lines.append(
            f"- {explanation}"
        )

    lines.append("")

    lines.append(
        "PAYMENT INFORMATION"
    )

    payment_info = report[
        "payment_information"
    ]

    lines.append(
        "UPI ID: "
        + str(
            payment_info.get(
                "upi_id",
                "Not detected"
            )
        )
    )

    lines.append(
        "Amount: "
        + str(
            payment_info.get(
                "amount",
                "Not detected"
            )
        )
    )

    lines.append("")

    lines.append(
        "URL / UPI INTELLIGENCE"
    )

    intelligence = report[
        "url_detection"
    ]

    lines.append(
        "URLs: "
        + (
            ", ".join(
                intelligence["urls"]
            )
            or "None"
        )
    )

    lines.append(
        "UPI IDs: "
        + (
            ", ".join(
                intelligence["upi_ids"]
            )
            or "None"
        )
    )

    lines.append(
        "Amounts: "
        + (
            ", ".join(
                intelligence["amounts"]
            )
            or "None"
        )
    )

    lines.append("")

    lines.append(
        "SAFETY RECOMMENDATION"
    )

    lines.append(
        get_risk_message(
            report["risk_level"]
        )
    )

    return "\n".join(lines)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title("🛡️ UPI SHIELD")

    st.caption(
        "Digital Payment Safety Platform"
    )

    st.divider()

    page = st.radio(
        "Navigation",
        [
            "🔍 Analyze Message",
            "📜 Analysis History",
            "📷 OCR Screenshot Scanner",
            "🛡️ Safety Center",
            "📄 Reports & Export",
            "ℹ️ About"
        ],
        label_visibility="collapsed"
    )

    st.divider()

    st.subheader(
        "System Status"
    )

    st.success(
        "🟢 Detector Online"
    )

    st.caption(
        "NLP analysis engine ready"
    )

    # OCR status
    if TESSERACT_AVAILABLE:

        st.success(
            "🟢 OCR Engine Online"
        )

        st.caption(
            "Tesseract OCR ready"
        )

    else:

        st.error(
            "🔴 OCR Engine Offline"
        )

        st.caption(
            "Tesseract OCR not found"
        )

    st.divider()

    st.caption(
        "UPI Shield"
    )

    st.caption(
        "Contextual Digital Payment "
        "Scam & Coercion Detector"
    )


# =========================================================
# HEADER
# =========================================================

st.title(
    "🛡️ UPI SHIELD"
)

st.subheader(
    "Contextual Digital Payment Scam & Coercion Detector"
)

st.write(
    "Detect suspicious payment requests, scam signals, "
    "UPI IDs and potentially dangerous links."
)

st.divider()


# =========================================================
# PAGE 1 — ANALYZE MESSAGE
# =========================================================

if page == "🔍 Analyze Message":

    st.header(
        "📩 Analyze a Message"
    )

    st.write(
        "Paste an SMS, WhatsApp message or payment request "
        "to perform a complete security analysis."
    )

    st.subheader(
        "⚡ Quick Demo"
    )

    demo1, demo2, demo3 = st.columns(3)

    with demo1:

        if st.button(
            "🚨 Electricity Scam",
            use_container_width=True
        ):

            st.session_state.message_input = (
                "URGENT! Your electricity connection will be "
                "disconnected in 30 minutes. Pay ₹4999 immediately "
                "to this UPI ID to avoid disconnection. "
                "Click https://upi-payment-verify.com"
            )

            st.session_state.analysis_result = None

    with demo2:

        if st.button(
            "🏦 Fake Bank Alert",
            use_container_width=True
        ):

            st.session_state.message_input = (
                "URGENT! Your bank account will be blocked today. "
                "Verify your KYC immediately by sending ₹1 to "
                "abc123@upi. Visit https://bank-verify.example.com"
            )

            st.session_state.analysis_result = None

    with demo3:

        if st.button(
            "🟢 Normal Message",
            use_container_width=True
        ):

            st.session_state.message_input = (
                "Your electricity bill of ₹850 is due on "
                "15 September. Please pay through the official "
                "electricity portal."
            )

            st.session_state.analysis_result = None

    st.write("")

    message = st.text_area(
        "Message",
        key="message_input",
        height=180,
        placeholder=(
            "Paste suspicious SMS / WhatsApp / "
            "payment message here..."
        )
    )

    if st.button(
        "🔍 ANALYZE MESSAGE",
        type="primary",
        use_container_width=True
    ):

        if not message.strip():

            st.warning(
                "⚠️ Please paste a message first."
            )

        else:

            with st.spinner(
                "🧠 AI is analyzing the message..."
            ):

                result = analyze_message(
                    message
                )

            intelligence = (
                extract_payment_intelligence(
                    message
                )
            )

            st.session_state.analysis_result = (
                result
            )

            history_item = {

                "time":
                    datetime.now().strftime(
                        "%d %b %Y, %I:%M %p"
                    ),

                "message":
                    message,

                "result":
                    result,

                "intelligence":
                    intelligence
            }

            st.session_state.analysis_history.insert(
                0,
                history_item
            )

            st.success(
                "✅ Message analyzed successfully."
            )

    result = (
        st.session_state.analysis_result
    )

    if result is not None:

        intelligence = (
            extract_payment_intelligence(
                message
            )
        )

        risk_score = result.get(
            "risk_score",
            0
        )

        risk_level = result.get(
            "risk_level",
            "LOW"
        )

        detected = result.get(
            "detected",
            []
        )

        explanations = result.get(
            "explanations",
            []
        )

        payment_info = result.get(
            "payment_info",
            {}
        )

        st.divider()

        st.header(
            "🚨 Threat Assessment"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "Risk Score",
                f"{risk_score}/100"
            )

        with col2:

            st.metric(
                "Risk Level",
                risk_level.upper()
            )

        with col3:

            st.metric(
                "Signals Detected",
                len(detected)
            )

        if risk_level.upper() == "HIGH":

            st.error(
                f"🚨 HIGH RISK\n\n"
                f"{risk_score}/100\n\n"
                "Strong scam or coercion indicators detected."
            )

        elif risk_level.upper() == "MEDIUM":

            st.warning(
                f"⚠️ MEDIUM RISK\n\n"
                f"{risk_score}/100\n\n"
                "Suspicious payment-related indicators detected."
            )

        else:

            st.success(
                f"🟢 LOW RISK\n\n"
                f"{risk_score}/100\n\n"
                "No strong scam pattern detected."
            )

        st.subheader(
            "📊 Threat Meter"
        )

        st.progress(
            max(
                0,
                min(
                    int(risk_score),
                    100
                )
            )
        )

        st.divider()

        st.header(
            "🔎 Detected Scam Signals"
        )

        if detected:

            for item in detected:

                if isinstance(
                    item,
                    dict
                ):

                    category = item.get(
                        "category",
                        "Unknown"
                    )

                    score = item.get(
                        "score",
                        0
                    )

                    try:

                        confidence = round(
                            float(score) * 100
                        )

                    except:

                        confidence = 0

                    with st.container(
                        border=True
                    ):

                        st.write(
                            f"⚠️ **{category}**"
                        )

                        st.progress(
                            max(
                                0,
                                min(
                                    confidence,
                                    100
                                )
                            )
                        )

                        st.caption(
                            f"Confidence: {confidence}%"
                        )

                else:

                    with st.container(
                        border=True
                    ):

                        st.write(
                            f"⚠️ {item}"
                        )

        else:

            st.success(
                "✅ No major scam signals detected."
            )

        st.divider()

        st.header(
            "🧠 Why was this message flagged?"
        )

        if explanations:

            for explanation in explanations:

                with st.container(
                    border=True
                ):

                    st.write(
                        explanation
                    )

        else:

            st.info(
                "No specific explanation available."
            )

        st.divider()

        st.header(
            "💳 Payment Intelligence"
        )

        p1, p2, p3 = st.columns(3)

        with p1:

            st.metric(
                "UPI IDs",
                len(
                    intelligence["upi_ids"]
                )
            )

        with p2:

            st.metric(
                "URLs",
                len(
                    intelligence["urls"]
                )
            )

        with p3:

            st.metric(
                "Amounts",
                len(
                    intelligence["amounts"]
                )
            )

        if intelligence["upi_ids"]:

            st.write(
                "**Detected UPI ID(s)**"
            )

            for upi in intelligence[
                "upi_ids"
            ]:

                st.code(
                    upi
                )

        if intelligence["urls"]:

            st.write(
                "**Detected URL(s)**"
            )

            for url in intelligence[
                "urls"
            ]:

                st.code(
                    url
                )

                st.warning(
                    "⚠️ Do not open suspicious payment links "
                    "until the sender and domain are verified."
                )

        if intelligence["amounts"]:

            st.write(
                "**Detected Amount(s)**"
            )

            st.write(
                ", ".join(
                    intelligence["amounts"]
                )
            )

        if payment_info:

            st.write(
                "**Detector Payment Information**"
            )

            pc1, pc2 = st.columns(2)

            with pc1:

                st.write(
                    "UPI ID:",
                    payment_info.get(
                        "upi_id",
                        "Not detected"
                    )
                )

            with pc2:

                st.write(
                    "Amount:",
                    payment_info.get(
                        "amount",
                        "Not detected"
                    )
                )

        st.divider()

        st.header(
            "🛡️ Safety Recommendation"
        )

        if risk_level.upper() == "HIGH":

            st.error(
                "🚨 DO NOT MAKE THE PAYMENT.\n\n"
                "Verify the sender using an official source."
            )

            st.warning(
                "🇮🇳 **हिंदी चेतावनी**\n\n"
                "इस संदेश में धोखाधड़ी के संकेत पाए गए हैं। "
                "तुरंत भुगतान न करें। आधिकारिक स्रोत से "
                "जानकारी सत्यापित करें।"
            )

        elif risk_level.upper() == "MEDIUM":

            st.warning(
                "⚠️ Be cautious. Verify the sender and "
                "payment request before taking action."
            )

            st.info(
                "🇮🇳 **हिंदी**\n\n"
                "भुगतान करने से पहले भेजने वाले और "
                "अनुरोध की पुष्टि करें।"
            )

        else:

            st.success(
                "🟢 No strong scam pattern detected. "
                "Still verify the sender before payment."
            )

            st.info(
                "🇮🇳 **हिंदी**\n\n"
                "भुगतान करने से पहले भेजने वाले की "
                "पुष्टि जरूर करें।"
            )


# =========================================================
# PAGE 2 — HISTORY
# =========================================================

elif page == "📜 Analysis History":

    st.header(
        "📜 Analysis History"
    )

    history = (
        st.session_state.analysis_history
    )

    if not history:

        st.info(
            "No analyses have been performed yet."
        )

    else:

        st.write(
            f"Total analyses: **{len(history)}**"
        )

        if st.button(
            "🗑️ Clear History"
        ):

            st.session_state.analysis_history = []

            st.rerun()

        st.divider()

        for item in history:

            result = item["result"]

            score = result.get(
                "risk_score",
                0
            )

            level = result.get(
                "risk_level",
                "LOW"
            )

            with st.expander(
                f"{item['time']} • "
                f"{level.upper()} • "
                f"{score}/100"
            ):

                st.write(
                    "**Message:**"
                )

                st.write(
                    item["message"]
                )

                h1, h2 = st.columns(2)

                with h1:

                    st.metric(
                        "Risk Score",
                        f"{score}/100"
                    )

                with h2:

                    st.metric(
                        "Risk Level",
                        level.upper()
                    )

                st.write(
                    "**Detected Signals:**"
                )

                detected = result.get(
                    "detected",
                    []
                )

                if detected:

                    for signal in detected:

                        if isinstance(
                            signal,
                            dict
                        ):

                            st.write(
                                "⚠️ "
                                + signal.get(
                                    "category",
                                    "Unknown"
                                )
                            )

                        else:

                            st.write(
                                "⚠️ "
                                + str(signal)
                            )

                else:

                    st.write(
                        "No major signals."
                    )


# =========================================================
# PAGE 3 — OCR SCREENSHOT SCANNER
# =========================================================

elif page == "📷 OCR Screenshot Scanner":

    st.header(
        "📷 OCR Screenshot Scanner"
    )

    st.write(
        "Upload a screenshot of an SMS, WhatsApp message "
        "or payment request. UPI Shield will extract the "
        "visible text and analyze it automatically."
    )

    st.divider()

    # -----------------------------------------------------
    # OCR ENGINE STATUS
    # -----------------------------------------------------

    if TESSERACT_AVAILABLE:

        st.success(
            "🟢 OCR Engine Ready — Tesseract is available."
        )

    else:

        st.error(
            "🔴 OCR Engine Not Found"
        )

        st.warning(
            "Install Tesseract OCR on your computer "
            "before using screenshot analysis."
        )

        st.code(
            "pip install pillow pytesseract"
        )

        st.info(
            "Note: pytesseract is only the Python wrapper. "
            "The Tesseract OCR application must also be installed."
        )

    # -----------------------------------------------------
    # UPLOAD
    # -----------------------------------------------------

    uploaded_file = st.file_uploader(
        "📤 Upload Screenshot",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp"
        ],
        help=(
            "Upload a clear screenshot containing "
            "SMS, WhatsApp or payment-related text."
        )
    )

    if uploaded_file:

        st.divider()

        image = Image.open(
            uploaded_file
        )

        # -------------------------------------------------
        # IMAGE PREVIEW
        # -------------------------------------------------

        st.subheader(
            "🖼️ Screenshot Preview"
        )

        st.image(
            image,
            caption="Uploaded Screenshot",
            use_container_width=True
        )

        st.write(
            f"Image size: **{image.width} × {image.height} pixels**"
        )

        # -------------------------------------------------
        # OCR BUTTON
        # -------------------------------------------------

        if st.button(
            "🔎 EXTRACT TEXT & ANALYZE",
            type="primary",
            use_container_width=True,
            disabled=not TESSERACT_AVAILABLE
        ):

            try:

                # -----------------------------------------
                # STEP 1 — OCR
                # -----------------------------------------

                with st.spinner(
                    "📷 Reading screenshot with OCR..."
                ):

                    extracted_text = (
                        extract_text_from_image(
                            image
                        )
                    )

                    ocr_confidence = (
                        get_ocr_confidence(
                            image
                        )
                    )

                if not extracted_text:

                    st.warning(
                        "⚠️ No readable text was detected."
                    )

                    st.info(
                        "Try uploading a clearer screenshot "
                        "with larger and sharper text."
                    )

                else:

                    # -------------------------------------
                    # SAVE OCR TEXT
                    # -------------------------------------

                    st.session_state.ocr_text = (
                        extracted_text
                    )

                    st.subheader(
                        "📝 Extracted Text"
                    )

                    st.text_area(
                        "OCR Result",
                        value=extracted_text,
                        height=220
                    )

                    st.metric(
                        "OCR Confidence",
                        f"{ocr_confidence}%"
                    )

                    # -------------------------------------
                    # PAYMENT INTELLIGENCE
                    # -------------------------------------

                    intelligence = (
                        extract_payment_intelligence(
                            extracted_text
                        )
                    )

                    # -------------------------------------
                    # ANALYZE OCR TEXT
                    # -------------------------------------

                    with st.spinner(
                        "🧠 Analyzing extracted message..."
                    ):

                        ocr_result = (
                            analyze_message(
                                extracted_text
                            )
                        )

                    st.session_state.ocr_result = (
                        ocr_result
                    )

                    st.session_state.ocr_intelligence = (
                        intelligence
                    )

                    # -------------------------------------
                    # SAVE OCR TO HISTORY
                    # -------------------------------------

                    history_item = {

                        "time":
                            datetime.now().strftime(
                                "%d %b %Y, %I:%M %p"
                            ),

                        "message":
                            extracted_text,

                        "result":
                            ocr_result,

                        "intelligence":
                            intelligence,

                        "source":
                            "OCR Screenshot"
                    }

                    st.session_state.analysis_history.insert(
                        0,
                        history_item
                    )

                    st.success(
                        "✅ Screenshot text extracted "
                        "and analyzed successfully."
                    )

            except Exception as error:

                st.error(
                    "❌ OCR processing failed."
                )

                st.write(
                    f"Error: {error}"
                )

                st.info(
                    "Make sure Tesseract OCR is installed "
                    "correctly and available on your system."
                )

        # -------------------------------------------------
        # DISPLAY STORED OCR RESULT
        # -------------------------------------------------

        if (
            st.session_state.ocr_result
            is not None
        ):

            ocr_result = (
                st.session_state.ocr_result
            )

            intelligence = (
                st.session_state.ocr_intelligence
            )

            st.divider()

            st.header(
                "🚨 OCR Threat Assessment"
            )

            score = ocr_result.get(
                "risk_score",
                0
            )

            level = ocr_result.get(
                "risk_level",
                "LOW"
            )

            detected = ocr_result.get(
                "detected",
                []
            )

            explanations = ocr_result.get(
                "explanations",
                []
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                st.metric(
                    "Risk Score",
                    f"{score}/100"
                )

            with c2:

                st.metric(
                    "Risk Level",
                    level.upper()
                )

            with c3:

                st.metric(
                    "Signals",
                    len(detected)
                )

            st.subheader(
                "📊 Threat Meter"
            )

            st.progress(
                max(
                    0,
                    min(
                        int(score),
                        100
                    )
                )
            )

            if level.upper() == "HIGH":

                st.error(
                    "🚨 HIGH RISK — "
                    "Do not make the requested payment."
                )

            elif level.upper() == "MEDIUM":

                st.warning(
                    "⚠️ MEDIUM RISK — "
                    "Verify the request carefully."
                )

            else:

                st.success(
                    "🟢 LOW RISK — "
                    "No strong scam pattern detected."
                )

            # ---------------------------------------------
            # SIGNALS
            # ---------------------------------------------

            st.divider()

            st.subheader(
                "🔎 Detected Scam Signals"
            )

            if detected:

                for signal in detected:

                    if isinstance(
                        signal,
                        dict
                    ):

                        category = signal.get(
                            "category",
                            "Unknown"
                        )

                        confidence = signal.get(
                            "score",
                            0
                        )

                        try:

                            confidence = round(
                                float(confidence) * 100
                            )

                        except:

                            confidence = 0

                        with st.container(
                            border=True
                        ):

                            st.write(
                                f"⚠️ **{category}**"
                            )

                            st.progress(
                                max(
                                    0,
                                    min(
                                        confidence,
                                        100
                                    )
                                )
                            )

                            st.caption(
                                f"Confidence: {confidence}%"
                            )

                    else:

                        st.write(
                            f"⚠️ {signal}"
                        )

            else:

                st.success(
                    "No major scam signals detected."
                )

            # ---------------------------------------------
            # WHY FLAGGED
            # ---------------------------------------------

            st.divider()

            st.subheader(
                "🧠 Why was this flagged?"
            )

            if explanations:

                for explanation in explanations:

                    with st.container(
                        border=True
                    ):

                        st.write(
                            explanation
                        )

            else:

                st.info(
                    "No specific explanation available."
                )

            # ---------------------------------------------
            # OCR PAYMENT INTELLIGENCE
            # ---------------------------------------------

            st.divider()

            st.subheader(
                "💳 Extracted Payment Intelligence"
            )

            i1, i2, i3 = st.columns(3)

            with i1:

                st.metric(
                    "UPI IDs",
                    len(
                        intelligence["upi_ids"]
                    )
                )

            with i2:

                st.metric(
                    "URLs",
                    len(
                        intelligence["urls"]
                    )
                )

            with i3:

                st.metric(
                    "Amounts",
                    len(
                        intelligence["amounts"]
                    )
                )

            if intelligence["upi_ids"]:

                st.write(
                    "**UPI IDs detected from screenshot:**"
                )

                for upi in intelligence[
                    "upi_ids"
                ]:

                    st.code(
                        upi
                    )

            if intelligence["urls"]:

                st.write(
                    "**URLs detected from screenshot:**"
                )

                for url in intelligence[
                    "urls"
                ]:

                    st.code(
                        url
                    )

                    st.warning(
                        "⚠️ Do not open this link until "
                        "the sender and domain are verified."
                    )

            if intelligence["amounts"]:

                st.write(
                    "**Amounts detected:**"
                )

                st.write(
                    ", ".join(
                        intelligence["amounts"]
                    )
                )

            # ---------------------------------------------
            # OCR SAFETY WARNING
            # ---------------------------------------------

            st.divider()

            st.subheader(
                "🛡️ Safety Recommendation"
            )

            if level.upper() == "HIGH":

                st.error(
                    "🚨 DO NOT MAKE THE PAYMENT."
                )

                st.warning(
                    "🇮🇳 इस संदेश में धोखाधड़ी के संकेत "
                    "पाए गए हैं। तुरंत भुगतान न करें। "
                    "आधिकारिक स्रोत से जानकारी सत्यापित करें।"
                )

            elif level.upper() == "MEDIUM":

                st.warning(
                    "⚠️ Verify the sender and payment "
                    "request before taking action."
                )

                st.info(
                    "🇮🇳 भुगतान करने से पहले भेजने वाले "
                    "और अनुरोध की पुष्टि करें।"
                )

            else:

                st.success(
                    "🟢 No strong scam pattern detected."
                )

                st.info(
                    "🇮🇳 भुगतान करने से पहले भेजने वाले "
                    "की पुष्टि जरूर करें।"
                )


# =========================================================
# PAGE 4 — SAFETY CENTER
# =========================================================

elif page == "🛡️ Safety Center":

    st.header(
        "🛡️ Digital Payment Safety Center"
    )

    st.write(
        "Simple rules to protect yourself from UPI "
        "and digital payment scams."
    )

    st.divider()

    st.subheader(
        "🔐 Before Making a Payment"
    )

    st.write(
        "✅ Verify the receiver's UPI ID."
    )

    st.write(
        "✅ Never pay because someone creates urgency."
    )

    st.write(
        "✅ Use official websites and apps."
    )

    st.write(
        "✅ Check the payment amount before confirming."
    )

    st.write(
        "✅ Never share your UPI PIN or OTP."
    )

    st.divider()

    st.subheader(
        "🚨 Common Scam Signals"
    )

    st.write(
        "⚠️ Threats of account blocking"
    )

    st.write(
        "⚠️ Electricity or service disconnection threats"
    )

    st.write(
        "⚠️ Lottery or prize claims"
    )

    st.write(
        "⚠️ Fake bank/KYC requests"
    )

    st.write(
        "⚠️ Requests to send money for verification"
    )

    st.write(
        "⚠️ Suspicious links"
    )

    st.write(
        "⚠️ Requests for OTP, PIN or credentials"
    )

    st.divider()

    st.subheader(
        "🆘 If You Already Paid"
    )

    st.write(
        "1. Contact your bank/payment provider immediately."
    )

    st.write(
        "2. Report the fraudulent transaction."
    )

    st.write(
        "3. Preserve screenshots and transaction details."
    )

    st.write(
        "4. Do not continue communicating with the scammer."
    )

    st.write(
        "5. Report the incident through appropriate "
        "official cybercrime channels."
    )

    st.divider()

    st.info(
        "🛡️ Remember: UPI payments require user authorization. "
        "Always verify the payment request before approving it."
    )


# =========================================================
# PAGE 5 — REPORTS & EXPORT
# =========================================================

elif page == "📄 Reports & Export":

    st.header(
        "📄 Reports & Export"
    )

    if not st.session_state.analysis_history:

        st.info(
            "Analyze at least one message to generate a report."
        )

    else:

        history = (
            st.session_state.analysis_history
        )

        options = []

        for item in history:

            result = item["result"]

            label = (
                f"{item['time']} | "
                f"{result.get('risk_level', 'LOW').upper()} | "
                f"{result.get('risk_score', 0)}/100"
            )

            options.append(
                label
            )

        selected = st.selectbox(
            "Select analysis",
            options
        )

        selected_index = options.index(
            selected
        )

        selected_item = history[
            selected_index
        ]

        report = create_report(
            selected_item["result"],
            selected_item["message"],
            selected_item["intelligence"]
        )

        st.subheader(
            "📋 Report Preview"
        )

        r1, r2, r3 = st.columns(3)

        with r1:

            st.metric(
                "Risk Score",
                f"{report['risk_score']}/100"
            )

        with r2:

            st.metric(
                "Risk Level",
                report["risk_level"].upper()
            )

        with r3:

            st.metric(
                "URLs Detected",
                len(
                    report[
                        "url_detection"
                    ]["urls"]
                )
            )

        st.divider()

        text_report = report_to_text(
            report
        )

        st.text_area(
            "Report",
            text_report,
            height=400
        )

        json_report = json.dumps(
            report,
            indent=4,
            ensure_ascii=False
        )

        download1, download2 = st.columns(2)

        with download1:

            st.download_button(
                "📄 Download TXT Report",
                data=text_report,
                file_name="upi_shield_report.txt",
                mime="text/plain",
                use_container_width=True
            )

        with download2:

            st.download_button(
                "📦 Download JSON Report",
                data=json_report,
                file_name="upi_shield_report.json",
                mime="application/json",
                use_container_width=True
            )


# =========================================================
# PAGE 6 — ABOUT
# =========================================================

elif page == "ℹ️ About":

    st.header(
        "ℹ️ About UPI Shield"
    )

    st.write(
        "UPI Shield is a contextual digital payment "
        "scam and coercion detection application."
    )

    st.divider()

    st.subheader(
        "🎯 Purpose"
    )

    st.write(
        "The application helps users identify suspicious "
        "payment messages before authorizing a transaction."
    )

    st.subheader(
        "🚀 Features"
    )

    features = [
        "NLP-based scam detection",
        "Risk score and risk level",
        "Scam signal explanations",
        "UPI ID detection",
        "Suspicious URL detection",
        "Payment amount detection",
        "Screenshot OCR",
        "Analysis history",
        "Report generation",
        "English + Hindi safety guidance"
    ]

    for feature in features:

        st.write(
            "✅ " + feature
        )

    st.divider()

    st.subheader(
        "⚙️ Technology"
    )

    st.write(
        "Python • Streamlit • NLP • Hugging Face • OCR"
    )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "🛡️ UPI Shield | AI-powered digital payment safety"
)